#!/usr/bin/env python3
"""E2E coverage for Web task background colors and Phase 2 plugin options."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import http.cookiejar
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

EXPECTED_RGB = {
    "white": (255, 255, 255),
    "blue": (98, 139, 206),
    "red": (215, 69, 50),
    "gray": (242, 240, 240),
}


COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


def request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None, cookie: str | None = None) -> tuple[dict[str, Any], str | None]:
    req_headers = {"User-Agent": "idphoto-e2e/phase2", **dict(headers or {})}
    if cookie:
        req_headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with OPENER.open(req, timeout=60) as response:
        body = response.read().decode("utf-8")
        set_cookie = response.headers.get("Set-Cookie")
        return json.loads(body), set_cookie


def login(base_url: str) -> str | None:
    username = os.environ.get("IDPHOTO_APP_USERNAME")
    password = os.environ.get("IDPHOTO_APP_PASSWORD")
    if not username or not password:
        return None
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    _, set_cookie = request_json(
        f"{base_url}/api/auth/login",
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    return set_cookie.split(";", 1)[0] if set_cookie else None


def multipart_upload(base_url: str, image_path: Path, cookie: str | None) -> dict[str, Any]:
    boundary = f"----idphoto-e2e-{int(time.time() * 1000)}"
    content = image_path.read_bytes()
    body = b"\r\n".join([
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"'.encode(),
        b"Content-Type: image/jpeg",
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ])
    result, _ = request_json(
        f"{base_url}/api/uploads",
        method="POST",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        cookie=cookie,
    )
    return result


def create_task(base_url: str, cookie: str | None, upload_id: str, background: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "uploadId": upload_id,
        "templateId": "cn-id-1inch",
        "platform": "web",
        "aiMode": "none",
        "options": {"background": background, "renderOfficialIdPhoto": True, "renderAiEnhancePreview": False, **(options or {})},
    }
    result, _ = request_json(
        f"{base_url}/api/tasks",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        cookie=cookie,
    )
    return result


def poll_task(base_url: str, cookie: str | None, task_id: str) -> dict[str, Any]:
    for _ in range(40):
        result, _ = request_json(f"{base_url}/api/tasks/{task_id}", cookie=cookie)
        if result.get("status") in {"succeeded", "failed", "expired"}:
            return result
        time.sleep(0.75)
    raise TimeoutError(f"task {task_id} did not finish")


def fetch_bytes(base_url: str, path: str, cookie: str | None) -> bytes:
    url = urllib.parse.urljoin(base_url, path)
    headers = {"User-Agent": "idphoto-e2e/phase2"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with OPENER.open(req, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {path} returned {response.status}")
        return response.read()


def save_and_sample(image_bytes: bytes, out_path: Path) -> tuple[int, int, tuple[int, int, int]]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    with Image.open(out_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        sample = rgb.getpixel((5, 5))
        return width, height, sample


def close_rgb(actual: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = 8) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("IDPHOTO_E2E_BASE_URL", "http://127.0.0.1:7860"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--out-dir", default=".runtime/e2e_phase2_plugins")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    out_dir = Path(args.out_dir)
    cookie = login(base_url)
    upload = multipart_upload(base_url, Path(args.image), cookie)

    summary: dict[str, Any] = {"backgrounds": {}, "phase2": {}}
    for background in EXPECTED_RGB:
        task = create_task(base_url, cookie, upload["uploadId"], background)
        task = poll_task(base_url, cookie, task["taskId"])
        if task.get("status") != "succeeded":
            raise SystemExit(f"{background} task failed: {task}")
        result = task["officialResult"]
        data = fetch_bytes(base_url, result["downloadUrl"], cookie)
        width, height, sample = save_and_sample(data, out_dir / f"official_{background}.png")
        if not close_rgb(sample, EXPECTED_RGB[background]):
            raise SystemExit(f"{background} sample {sample} not close to expected {EXPECTED_RGB[background]}")
        summary["backgrounds"][background] = {"taskId": task["taskId"], "size": [width, height], "sampleTopLeftRgb": sample, "downloadBytes": len(data)}

    phase2_options = {
        "printLayoutEnabled": True,
        "layoutPaperSize": "a4",
        "printLayoutSize": "a4",
        "imageKb": 80,
        "imageKbMode": "max",
        "watermarkEnabled": True,
        "watermarkText": "E2E",
        "watermarkTextColor": "#8B8B1B",
        "watermarkTextSize": 28,
        "watermarkTextOpacity": 0.28,
        "watermarkTextAngle": 25,
        "watermarkTextSpace": 64,
    }
    task = create_task(base_url, cookie, upload["uploadId"], "blue", phase2_options)
    task = poll_task(base_url, cookie, task["taskId"])
    if task.get("status") != "succeeded":
        raise SystemExit(f"phase2 task failed: {task}")
    for key in ["officialResult", "layoutResult", "compressedResult", "watermarkedResult"]:
        result = task.get(key)
        if not result:
            raise SystemExit(f"phase2 task missing {key}: {task}")
        data = fetch_bytes(base_url, result["downloadUrl"], cookie)
        suffix = ".jpg" if key == "compressedResult" else ".png"
        output = out_dir / f"phase2_{key}{suffix}"
        output.write_bytes(data)
        summary["phase2"][key] = {"bytes": len(data), "path": str(output)}
        if key == "compressedResult" and len(data) > phase2_options["imageKb"] * 1024:
            raise SystemExit(f"compressedResult exceeds max KB: {len(data)} bytes")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
