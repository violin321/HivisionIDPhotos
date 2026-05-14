#!/usr/bin/env python3
"""Phase 5C API e2e: app login + protected upload/task/signed download flow.

Supports a Basic Auth wrapped deployment via BASIC_AUTH_USER/BASIC_AUTH_PASSWORD
without printing secrets or cookies.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib import error, request
from urllib.parse import urljoin

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; idphoto-ai-e2e/5C; +https://idphoto-ai.violinai.qzz.io)",
    "Accept": "application/json, text/plain, */*",
}


def basic_auth_header() -> dict[str, str]:
    user = os.environ.get("BASIC_AUTH_USER")
    password = os.environ.get("BASIC_AUTH_PASSWORD")
    if not user and not password:
        return {}
    if not user or not password:
        raise SystemExit("BASIC_AUTH_USER and BASIC_AUTH_PASSWORD must be set together")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def redact_url(url: str) -> str:
    password = os.environ.get("BASIC_AUTH_PASSWORD")
    return url.replace(password, "***") if password else url


def absolute_url(base_url: str, maybe_relative: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", maybe_relative.lstrip("/"))


class Client:
    def __init__(self) -> None:
        self.cookies = CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookies))

    def http_request(self, method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, expect_status: set[int] | None = None) -> tuple[int, dict[str, str], bytes]:
        all_headers = {**DEFAULT_HEADERS, **basic_auth_header(), **(headers or {})}
        req = request.Request(url, data=data, headers=all_headers, method=method)
        try:
            with self.opener.open(req, timeout=180) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except error.HTTPError as exc:
            body = exc.read()
            if expect_status and exc.code in expect_status:
                return exc.code, dict(exc.headers), body
            raise RuntimeError(f"{method} {redact_url(url)} failed: HTTP {exc.code} {body.decode('utf-8', errors='replace')}") from exc

    def http_json(self, method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, expect_status: set[int] | None = None) -> tuple[int, dict]:
        status, _headers, body = self.http_request(method, url, data, headers, expect_status=expect_status)
        return status, json.loads(body.decode("utf-8")) if body else {}

    def multipart_upload(self, url: str, image_path: Path) -> tuple[int, dict]:
        boundary = f"----phase5c{int(time.time() * 1000)}"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
        body.extend(image_path.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        return self.http_json("POST", url, bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def require_credentials() -> tuple[str, str]:
    user = os.environ.get("IDPHOTO_APP_USERNAME")
    password = os.environ.get("IDPHOTO_APP_PASSWORD")
    if not user or not password:
        raise SystemExit("IDPHOTO_APP_USERNAME and IDPHOTO_APP_PASSWORD are required for Phase 5C auth e2e")
    return user, password


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5C app auth e2e.")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--template", default="cn-id-1inch")
    parser.add_argument("--background", default="white")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    app_user, app_password = require_credentials()
    base_url = args.base_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")

    client = Client()
    _, health = client.http_json("GET", f"{base_url}/api/health")

    blocked_status, _body = client.http_json("GET", f"{base_url}/api/templates", expect_status={401, 403, 503})
    if blocked_status not in {401, 403}:
        raise SystemExit(f"unauthenticated protected API returned HTTP {blocked_status}, expected 401/403")

    _, login_body = client.http_json(
        "POST",
        f"{base_url}/api/auth/login",
        json.dumps({"username": app_user, "password": app_password}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    if not login_body.get("authenticated"):
        raise SystemExit("login did not return authenticated=true")
    if not any(cookie.name == "idphoto_ai_session" for cookie in client.cookies):
        raise SystemExit("login did not set idphoto_ai_session cookie")

    _, me = client.http_json("GET", f"{base_url}/api/auth/me")
    if not me.get("authenticated"):
        raise SystemExit("/api/auth/me did not confirm authenticated session")

    _, templates = client.http_json("GET", f"{base_url}/api/templates")
    if not isinstance(templates, list) or not templates:
        raise SystemExit("templates response is empty after login")

    _, upload = client.multipart_upload(f"{base_url}/api/uploads", image_path)
    _, task = client.http_json(
        "POST",
        f"{base_url}/api/tasks",
        json.dumps({"uploadId": upload["uploadId"], "templateId": args.template, "platform": "web", "aiMode": "preview", "options": {"background": args.background, "renderAiEnhancePreview": True}}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, task = client.http_json("GET", f"{base_url}/api/tasks/{task['taskId']}")
        if task["status"] in {"succeeded", "failed", "expired"}:
            break
        time.sleep(2)

    if task["status"] != "succeeded":
        raise SystemExit(f"task did not succeed: {json.dumps(task, ensure_ascii=False)}")

    result = task.get("officialResult") or {}
    download_url = result.get("downloadUrl")
    if not download_url or not download_url.startswith("/api/downloads/"):
        raise SystemExit(f"officialResult.downloadUrl is not a signed API URL: {json.dumps(result, ensure_ascii=False)}")

    status, headers, body = client.http_request("GET", absolute_url(base_url, download_url))
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    content_type = normalized_headers.get("content-type", "")
    if status != 200 or not content_type.startswith("image/") or not body:
        raise SystemExit(f"signed download failed: status={status} contentType={content_type!r} bytes={len(body)}")

    _, logout_body = client.http_json("POST", f"{base_url}/api/auth/logout")
    if logout_body.get("authenticated") is not False:
        raise SystemExit("logout did not return authenticated=false")

    blocked_after_logout, _body = client.http_json("GET", f"{base_url}/api/templates", expect_status={401, 403})
    if blocked_after_logout not in {401, 403}:
        raise SystemExit(f"post-logout protected API returned HTTP {blocked_after_logout}, expected 401/403")

    print(json.dumps({
        "ok": True,
        "baseUrl": redact_url(base_url),
        "basicAuth": bool(basic_auth_header()),
        "health": health,
        "unauthenticatedStatus": blocked_status,
        "postLogoutStatus": blocked_after_logout,
        "uploadId": upload["uploadId"],
        "taskId": task["taskId"],
        "download": {"status": status, "contentType": content_type, "bytes": len(body)},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
