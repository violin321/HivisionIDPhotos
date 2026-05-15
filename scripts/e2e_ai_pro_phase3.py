#!/usr/bin/env python3
"""Phase 3 AI Pro smoke checks.

Covers request schema behavior without requiring provider credentials. It never
prints provider secrets and expects no-key fallback for AI Pro unless the server
is explicitly configured with credentials.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib import error, request

DEFAULT_HEADERS = {"User-Agent": "idphoto-ai-pro-phase3-smoke/1.0", "Accept": "application/json, text/plain, */*"}


def app_cookie(base_url: str) -> str:
    user = os.environ.get("IDPHOTO_APP_USERNAME")
    password = os.environ.get("IDPHOTO_APP_PASSWORD")
    if not user or not password:
        raise SystemExit("IDPHOTO_APP_USERNAME and IDPHOTO_APP_PASSWORD are required for API smoke checks")
    body = json.dumps({"username": user, "password": password}).encode("utf-8")
    status, headers, _ = http_request("POST", f"{base_url}/api/auth/login", body, {"Content-Type": "application/json"})
    if status != 200:
        raise SystemExit(f"login failed with HTTP {status}")
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    cookie = normalized_headers.get("set-cookie", "").split(";", 1)[0]
    if not cookie:
        raise SystemExit("login did not return a session cookie")
    return cookie


def basic_auth_header() -> dict[str, str]:
    user = os.environ.get("BASIC_AUTH_USER")
    password = os.environ.get("BASIC_AUTH_PASSWORD")
    if not user and not password:
        return {}
    if not user or not password:
        raise SystemExit("BASIC_AUTH_USER and BASIC_AUTH_PASSWORD must be set together")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def http_request(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, cookie: str = "", expect_status: set[int] | None = None) -> tuple[int, dict[str, str], bytes]:
    all_headers = {**DEFAULT_HEADERS, **basic_auth_header(), **(headers or {})}
    if cookie:
        all_headers["Cookie"] = cookie
    req = request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with request.urlopen(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except error.HTTPError as exc:
        body = exc.read()
        if expect_status and exc.code in expect_status:
            return exc.code, dict(exc.headers), body
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {body.decode('utf-8', errors='replace')}") from exc


def http_json(method: str, url: str, data: dict | None = None, *, cookie: str = "", expect_status: set[int] | None = None) -> tuple[int, dict]:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    status, _headers, raw = http_request(method, url, body, headers, cookie=cookie, expect_status=expect_status)
    return status, json.loads(raw.decode("utf-8")) if raw else {}


def upload_image(base_url: str, image_path: Path, cookie: str) -> dict:
    boundary = f"----phase3aipro{int(time.time() * 1000)}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    _status, upload = http_json("POST", f"{base_url}/api/uploads", None, cookie=cookie)
    return upload


def multipart_upload(base_url: str, image_path: Path, cookie: str) -> dict:
    boundary = f"----phase3aipro{int(time.time() * 1000)}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode())
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    status, _headers, raw = http_request("POST", f"{base_url}/api/uploads", bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"}, cookie=cookie)
    if status != 200:
        raise SystemExit(f"upload failed with HTTP {status}")
    return json.loads(raw.decode("utf-8"))


def create_task(base_url: str, upload_id: str, cookie: str, *, ai_pro: dict | None) -> dict:
    payload = {"uploadId": upload_id, "templateId": "cn-id-1inch", "platform": "web", "aiMode": "none", "options": {"background": "blue"}}
    if ai_pro is not None:
        payload["aiPro"] = ai_pro
    _status, task = http_json("POST", f"{base_url}/api/tasks", payload, cookie=cookie)
    return task


def assert_real_provider_result(task: dict, pro: dict) -> None:
    metadata = pro.get("promptMetadata") or {}
    failures = []
    if pro.get("status") != "completed":
        failures.append(f"status={pro.get('status')!r}")
    if pro.get("mock") is not False or metadata.get("mock") is not False:
        failures.append(f"mock pro={pro.get('mock')!r} metadata={metadata.get('mock')!r}")
    if metadata.get("fallback") is not False:
        failures.append(f"fallback={metadata.get('fallback')!r}")
    if metadata.get("providerStatus") != "configured":
        failures.append(f"providerStatus={metadata.get('providerStatus')!r}")
    if not pro.get("previewUrl") or not pro.get("downloadUrl"):
        failures.append("missing previewUrl/downloadUrl")
    if failures:
        raise SystemExit(f"real provider invariant failed: {', '.join(failures)} taskId={task.get('taskId')}")


def wait_task(base_url: str, task_id: str, cookie: str, timeout: float) -> dict:
    deadline = time.time() + timeout
    task = {}
    while time.time() < deadline:
        _status, task = http_json("GET", f"{base_url}/api/tasks/{task_id}", cookie=cookie)
        if task.get("status") in {"succeeded", "failed", "expired"}:
            return task
        time.sleep(2)
    raise SystemExit(f"task timed out: {task_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 3 AI Pro smoke checks")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--mode", default="ai_blue_formal_id_photo", choices=["ai_blue_formal_id_photo"], help="AI Pro mode to request for the provider smoke path")
    parser.add_argument("--expect-real-provider", action="store_true", help="Require AI Pro provider output instead of fallback/mock metadata")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")
    cookie = app_cookie(base_url)

    # no-AI path still succeeds and returns no proResults.
    upload = multipart_upload(base_url, image_path, cookie)
    task = wait_task(base_url, create_task(base_url, upload["uploadId"], cookie, ai_pro=None)["taskId"], cookie, args.timeout)
    if task.get("status") != "succeeded" or task.get("proResults"):
        raise SystemExit(f"no-AI task invariant failed: {json.dumps(task, ensure_ascii=False)}")

    # consent missing is rejected before any AI work is scheduled.
    upload = multipart_upload(base_url, image_path, cookie)
    status, body = http_json("POST", f"{base_url}/api/tasks", {
        "uploadId": upload["uploadId"], "templateId": "cn-id-1inch", "platform": "web", "aiMode": "none", "options": {"background": "blue"},
        "aiPro": {"enabled": True, "modes": ["ai_blue_formal_id_photo"], "promptParams": {}, "consentAccepted": False},
    }, cookie=cookie, expect_status={400})
    error_body = body.get("error") or body.get("detail", {}).get("error", {})
    if status != 400 or error_body.get("code") != "AI_PRO_CONSENT_REQUIRED":
        raise SystemExit(f"consent check failed: HTTP {status} {json.dumps(body, ensure_ascii=False)}")

    # no-key fallback remains a successful core task with explicit AI Pro metadata.
    upload = multipart_upload(base_url, image_path, cookie)
    task = wait_task(base_url, create_task(base_url, upload["uploadId"], cookie, ai_pro={
        "enabled": True,
        "modes": [args.mode],
        "promptParams": {"backgroundColor": "blue", "outfit": "深色西装/白衬衫", "retouchLevel": "medium"},
        "consentAccepted": True,
    })["taskId"], cookie, args.timeout)
    if task.get("status") != "succeeded" or not task.get("freeResult"):
        raise SystemExit(f"AI Pro fallback broke freeResult: {json.dumps(task, ensure_ascii=False)}")
    pro = (task.get("proResults") or [None])[0]
    if not pro or pro.get("mode") != "ai_blue_formal_id_photo":
        raise SystemExit(f"missing AI Pro result: {json.dumps(task, ensure_ascii=False)}")
    metadata = pro.get("promptMetadata") or {}
    if "finalPromptHash" not in metadata or "inputSource" not in metadata:
        raise SystemExit(f"AI Pro metadata incomplete: {json.dumps(pro, ensure_ascii=False)}")
    if args.expect_real_provider:
        assert_real_provider_result(task, pro)

    print(json.dumps({
        "ok": True,
        "baseUrl": base_url,
        "noAiTaskId": task["taskId"],
        "aiProTaskId": task["taskId"],
        "aiProStatus": pro.get("status"),
        "providerStatus": metadata.get("providerStatus"),
        "provider": metadata.get("provider"),
        "model": metadata.get("model"),
        "mock": pro.get("mock"),
        "fallback": metadata.get("fallback"),
        "inputSource": metadata.get("inputSource"),
        "finalPromptHash": metadata.get("finalPromptHash"),
        "previewUrl": pro.get("previewUrl"),
        "downloadUrl": pro.get("downloadUrl"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
