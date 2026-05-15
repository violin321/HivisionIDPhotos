#!/usr/bin/env python3
"""Minimal Phase 4 API contract/e2e check.

Usage:
  API_BASE_URL=http://127.0.0.1:8000 ./scripts/e2e_phase4_api.py
  ./scripts/e2e_phase4_api.py --base-url http://127.0.0.1:8000 --image demo/images/test0.jpg
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib import request, error


def http_json(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {body}") from exc


def multipart_upload(url: str, image_path: Path) -> dict:
    boundary = f"----phase4{int(time.time() * 1000)}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n".encode()
    )
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return http_json("POST", url, bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run upload -> task -> poll -> officialResult contract check.")
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

    health = http_json("GET", f"{base_url}/api/health")
    templates = http_json("GET", f"{base_url}/api/templates")
    template_ids = {item["templateId"] for item in templates}
    if args.template not in template_ids:
        raise SystemExit(f"template {args.template!r} missing from /api/templates: {sorted(template_ids)}")

    upload = multipart_upload(f"{base_url}/api/uploads", image_path)
    task = http_json(
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
        task = http_json("GET", f"{base_url}/api/tasks/{task['taskId']}")
        if task["status"] in {"succeeded", "failed", "expired"}:
            break
        time.sleep(2)

    if task["status"] != "succeeded":
        raise SystemExit(f"task did not succeed: {json.dumps(task, ensure_ascii=False)}")
    if not task.get("officialResult", {}).get("previewUrl") or not task.get("officialResult", {}).get("downloadUrl"):
        raise SystemExit(f"officialResult missing preview/download URL: {json.dumps(task, ensure_ascii=False)}")
    if task.get("aiEnhanceResult") and task["options"].get("aiEnhancePreviewKind") != "local-derived-preview":
        raise SystemExit("AI preview result was not labelled local-derived-preview")

    print(json.dumps({"ok": True, "health": health, "uploadId": upload["uploadId"], "taskId": task["taskId"], "officialResult": task["officialResult"], "aiEnhanceResult": task.get("aiEnhanceResult")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
