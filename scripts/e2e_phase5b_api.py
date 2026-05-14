#!/usr/bin/env python3
"""Phase 5B API e2e: upload -> task -> signed result download.

Supports Basic Auth protected endpoints via BASIC_AUTH_USER/BASIC_AUTH_PASSWORD
without printing secrets.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urljoin

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; idphoto-ai-e2e/5B; +https://idphoto-ai.violinai.qzz.io)",
    "Accept": "application/json, text/plain, */*",
}


def auth_header() -> dict[str, str]:
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


def http_request(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, expect_status: set[int] | None = None) -> tuple[int, dict[str, str], bytes]:
    all_headers = {**DEFAULT_HEADERS, **auth_header(), **(headers or {})}
    req = request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with request.urlopen(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except error.HTTPError as exc:
        body = exc.read()
        if expect_status and exc.code in expect_status:
            return exc.code, dict(exc.headers), body
        raise RuntimeError(f"{method} {redact_url(url)} failed: HTTP {exc.code} {body.decode('utf-8', errors='replace')}") from exc


def http_json(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, expect_status: set[int] | None = None) -> tuple[int, dict]:
    status, _headers, body = http_request(method, url, data, headers, expect_status=expect_status)
    return status, json.loads(body.decode("utf-8")) if body else {}


def multipart_upload(url: str, image_path: Path) -> tuple[int, dict]:
    boundary = f"----phase5b{int(time.time() * 1000)}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return http_json("POST", url, bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def tamper_url(url: str) -> str:
    if url.endswith("A"):
        return url[:-1] + "B"
    return url[:-1] + "A"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5B signed download e2e.")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--template", default="cn-id-1inch")
    parser.add_argument("--background", default="white")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")

    _, health = http_json("GET", f"{base_url}/api/health")
    _, upload = multipart_upload(f"{base_url}/api/uploads", image_path)
    _, task = http_json(
        "POST",
        f"{base_url}/api/tasks",
        json.dumps({"uploadId": upload["uploadId"], "templateId": args.template, "platform": "web", "aiMode": "preview", "options": {"background": args.background, "renderAiEnhancePreview": True}}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, task = http_json("GET", f"{base_url}/api/tasks/{task['taskId']}")
        if task["status"] in {"succeeded", "failed", "expired"}:
            break
        time.sleep(2)

    if task["status"] != "succeeded":
        raise SystemExit(f"task did not succeed: {json.dumps(task, ensure_ascii=False)}")

    result = task.get("officialResult") or {}
    download_url = result.get("downloadUrl")
    if not download_url or not download_url.startswith("/api/downloads/"):
        raise SystemExit(f"officialResult.downloadUrl is not a signed API URL: {json.dumps(result, ensure_ascii=False)}")

    signed_url = absolute_url(base_url, download_url)
    status, headers, body = http_request("GET", signed_url)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    content_type = normalized_headers.get("content-type", "")
    cache_control = normalized_headers.get("cache-control", "")
    if status != 200 or not content_type.startswith("image/") or not body:
        raise SystemExit(f"signed download failed: status={status} contentType={content_type!r} bytes={len(body)}")
    if "no-store" not in cache_control:
        raise SystemExit(f"signed download missing no-store cache policy: {cache_control!r}")

    tampered_status, _headers, _body = http_request("GET", tamper_url(signed_url), expect_status={403, 404})
    if tampered_status not in {403, 404}:
        raise SystemExit(f"tampered token unexpectedly returned HTTP {tampered_status}")

    print(json.dumps({"ok": True, "baseUrl": redact_url(base_url), "basicAuth": bool(auth_header()), "health": health, "uploadId": upload["uploadId"], "taskId": task["taskId"], "download": {"status": status, "contentType": content_type, "bytes": len(body), "cacheControl": cache_control}, "tamperedStatus": tampered_status, "officialResult": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
