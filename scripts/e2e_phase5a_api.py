#!/usr/bin/env python3
"""Phase 5A API e2e and upload hardening checks.

Supports local and public Basic Auth protected endpoints without printing secrets.

Usage:
  API_BASE_URL=http://127.0.0.1:18084 .venv/bin/python scripts/e2e_phase5a_api.py
  API_BASE_URL=https://idphoto-ai.example.com BASIC_AUTH_USER=... BASIC_AUTH_PASSWORD=... \
    .venv/bin/python scripts/e2e_phase5a_api.py
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

SENSITIVE_HEADER_NAMES = {"authorization"}
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; idphoto-ai-e2e/5A; +https://idphoto-ai.violinai.qzz.io)",
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
    return url.replace(os.environ.get("BASIC_AUTH_PASSWORD", "\0"), "***")


def http_json(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None, *, expect_status: set[int] | None = None) -> tuple[int, dict]:
    all_headers = {**DEFAULT_HEADERS, **auth_header(), **(headers or {})}
    req = request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if expect_status and exc.code in expect_status:
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}
        raise RuntimeError(f"{method} {redact_url(url)} failed: HTTP {exc.code} {body}") from exc


def multipart_upload(url: str, image_path: Path, *, content_type: str = "image/jpeg", field_name: str = "file", expect_status: set[int] | None = None) -> tuple[int, dict]:
    boundary = f"----phase5a{int(time.time() * 1000)}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return http_json("POST", url, bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"}, expect_status=expect_status)


def expect_bad_upload(base_url: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        text_file = Path(tmp) / "not-image.txt"
        text_file.write_text("not an image", encoding="utf-8")
        status, body = multipart_upload(f"{base_url}/api/uploads", text_file, content_type="text/plain", expect_status={400, 413, 415, 422})
        if status < 400:
            raise SystemExit(f"text/plain upload unexpectedly succeeded: {body}")
    return {"status": status, "errorCode": body.get("detail", {}).get("error", {}).get("code") or body.get("error", {}).get("code")}


def expect_oversize_upload(base_url: str, max_bytes: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        big_file = Path(tmp) / "too-large.jpg"
        big_file.write_bytes(b"\xff\xd8\xff" + (b"0" * max_bytes))
        status, body = multipart_upload(f"{base_url}/api/uploads", big_file, content_type="image/jpeg", expect_status={400, 413, 415, 422})
        if status < 400:
            raise SystemExit("oversize upload unexpectedly succeeded")
    return {"status": status, "errorCode": body.get("detail", {}).get("error", {}).get("code") or body.get("error", {}).get("code")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5A upload -> task -> poll -> officialResult e2e.")
    parser.add_argument("--base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--template", default="cn-id-1inch")
    parser.add_argument("--background", default="white")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--skip-negative", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")

    _, health = http_json("GET", f"{base_url}/api/health")
    _, config = http_json("GET", f"{base_url}/api/config")
    _, templates = http_json("GET", f"{base_url}/api/templates")
    template_ids = {item["templateId"] for item in templates}
    if args.template not in template_ids:
        raise SystemExit(f"template {args.template!r} missing from /api/templates: {sorted(template_ids)}")

    negative = None
    oversize = None
    if not args.skip_negative:
        negative = expect_bad_upload(base_url)
        max_bytes = int(config.get("uploadLimits", {}).get("maxBytes", 20 * 1024 * 1024))
        oversize = expect_oversize_upload(base_url, max_bytes)

    _, upload = multipart_upload(f"{base_url}/api/uploads", image_path)
    _, task = http_json(
        "POST",
        f"{base_url}/api/tasks",
        json.dumps(
            {
                "uploadId": upload["uploadId"],
                "templateId": args.template,
                "platform": "web",
                "aiMode": "preview",
                "options": {"background": args.background, "renderAiEnhancePreview": True},
            }
        ).encode("utf-8"),
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
    if not task.get("officialResult", {}).get("previewUrl") or not task.get("officialResult", {}).get("downloadUrl"):
        raise SystemExit(f"officialResult missing preview/download URL: {json.dumps(task, ensure_ascii=False)}")
    if task.get("aiEnhanceResult") and task["options"].get("aiEnhancePreviewKind") != "local-derived-preview":
        raise SystemExit("AI preview result was not labelled local-derived-preview")

    print(
        json.dumps(
            {
                "ok": True,
                "baseUrl": redact_url(base_url),
                "basicAuth": bool(auth_header()),
                "health": health,
                "uploadLimits": config.get("uploadLimits"),
                "negativeUpload": negative,
                "oversizeUpload": oversize,
                "uploadId": upload["uploadId"],
                "taskId": task["taskId"],
                "officialResult": task["officialResult"],
                "aiEnhanceResultKind": task["options"].get("aiEnhancePreviewKind"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
