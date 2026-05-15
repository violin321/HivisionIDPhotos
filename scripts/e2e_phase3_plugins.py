#!/usr/bin/env python3
"""E2E coverage for Phase 3 render modes, custom colors, and remaining plugins."""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


def request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None, cookie: str | None = None) -> tuple[dict[str, Any], str | None]:
    req_headers = {"User-Agent": "idphoto-e2e/phase3", **dict(headers or {})}
    if cookie:
        req_headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with OPENER.open(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8")), response.headers.get("Set-Cookie")


def login(base_url: str) -> str | None:
    username = os.environ.get("IDPHOTO_APP_USERNAME")
    password = os.environ.get("IDPHOTO_APP_PASSWORD")
    if not username or not password:
        return None
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    _, set_cookie = request_json(f"{base_url}/api/auth/login", method="POST", data=body, headers={"Content-Type": "application/json"})
    return set_cookie.split(";", 1)[0] if set_cookie else None


def multipart_upload(base_url: str, image_path: Path, cookie: str | None) -> dict[str, Any]:
    boundary = f"----idphoto-e2e-phase3-{int(time.time() * 1000)}"
    body = b"\r\n".join([
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"'.encode(),
        b"Content-Type: image/jpeg",
        b"",
        image_path.read_bytes(),
        f"--{boundary}--".encode(),
        b"",
    ])
    result, _ = request_json(f"{base_url}/api/uploads", method="POST", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, cookie=cookie)
    return result


def create_task(base_url: str, cookie: str | None, upload_id: str, options: dict[str, Any]) -> dict[str, Any]:
    payload = {"uploadId": upload_id, "templateId": "cn-id-1inch", "platform": "web", "aiMode": "none", "options": {"background": "blue", "renderOfficialIdPhoto": True, "renderAiEnhancePreview": False, **options}}
    result, _ = request_json(f"{base_url}/api/tasks", method="POST", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, cookie=cookie)
    return result


def poll_task(base_url: str, cookie: str | None, task_id: str) -> dict[str, Any]:
    for _ in range(50):
        result, _ = request_json(f"{base_url}/api/tasks/{task_id}", cookie=cookie)
        if result.get("status") in {"succeeded", "failed", "expired"}:
            return result
        time.sleep(0.75)
    raise TimeoutError(f"task {task_id} did not finish")


def fetch(base_url: str, path: str, cookie: str | None) -> tuple[bytes, str]:
    headers = {"User-Agent": "idphoto-e2e/phase3"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(urllib.parse.urljoin(base_url, path), headers=headers)
    with OPENER.open(req, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {path} returned {response.status}")
        return response.read(), response.headers.get("Content-Type", "")


def sample(path: Path) -> tuple[int, int, tuple[int, int, int]]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return rgb.width, rgb.height, rgb.getpixel((5, 5))


def image_diff_bytes(a: bytes, b: bytes) -> float:
    from io import BytesIO
    with Image.open(BytesIO(a)).convert("RGB") as img_a, Image.open(BytesIO(b)).convert("RGB") as img_b:
        diff = ImageChops.difference(img_a, img_b)
        hist = diff.histogram()
        sq = sum(value * ((idx % 256) ** 2) for idx, value in enumerate(hist))
        return (sq / float(img_a.size[0] * img_a.size[1] * 3)) ** 0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("IDPHOTO_E2E_BASE_URL", "http://127.0.0.1:7860"))
    parser.add_argument("--image", default="demo/images/test0.jpg")
    parser.add_argument("--out-dir", default=".runtime/e2e_phase3_plugins")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cookie = login(base_url)
    upload = multipart_upload(base_url, Path(args.image), cookie)
    summary: dict[str, Any] = {"tasks": {}}

    render_modes = ["solid", "upDownGradientWhite", "centerGradientWhite"]
    for mode in render_modes:
        task = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], {"renderMode": mode})["taskId"])
        if task.get("status") != "succeeded":
            raise SystemExit(f"renderMode {mode} failed: {task}")
        data, ctype = fetch(base_url, task["officialResult"]["downloadUrl"], cookie)
        path = out_dir / f"render_{mode}.png"
        path.write_bytes(data)
        summary["tasks"][f"render_{mode}"] = {"taskId": task["taskId"], "bytes": len(data), "contentType": ctype, "sample": sample(path)}

    for label, opts, expected in [
        ("custom_hex", {"background": "custom", "customBackgroundHex": "#336699"}, (51, 102, 153)),
        ("custom_rgb", {"background": "custom", "customBackgroundRgb": [12, 200, 90]}, (12, 200, 90)),
    ]:
        task = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], opts)["taskId"])
        if task.get("status") != "succeeded":
            raise SystemExit(f"{label} failed: {task}")
        data, _ = fetch(base_url, task["officialResult"]["downloadUrl"], cookie)
        path = out_dir / f"{label}.png"
        path.write_bytes(data)
        _, _, actual = sample(path)
        if any(abs(a - e) > 8 for a, e in zip(actual, expected)):
            raise SystemExit(f"{label} sample {actual} not close to {expected}")
        summary["tasks"][label] = {"taskId": task["taskId"], "sample": actual, "expected": expected}

    jpeg_task = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], {"jpegFormat": True, "pluginFlags": ["jpegFormat"]})["taskId"])
    data, ctype = fetch(base_url, jpeg_task["officialResult"]["downloadUrl"], cookie)
    if not data.startswith(b"\xff\xd8") or "jpeg" not in ctype.lower():
        raise SystemExit(f"jpegFormat did not return JPEG: contentType={ctype} bytes={data[:4]!r}")
    (out_dir / "jpeg_format.jpg").write_bytes(data)
    summary["tasks"]["jpegFormat"] = {"taskId": jpeg_task["taskId"], "bytes": len(data), "contentType": ctype}

    normal = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], {"background": "white"})["taskId"])
    flipped = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], {"background": "white", "horizontalFlip": True, "pluginFlags": ["horizontalFlip"]})["taskId"])
    normal_bytes, _ = fetch(base_url, normal["officialResult"]["downloadUrl"], cookie)
    flipped_bytes, _ = fetch(base_url, flipped["officialResult"]["downloadUrl"], cookie)
    diff = image_diff_bytes(normal_bytes, flipped_bytes)
    if diff < 1.0:
        raise SystemExit(f"horizontalFlip output too similar: diff={diff}")
    summary["tasks"]["horizontalFlip"] = {"normalTaskId": normal["taskId"], "flippedTaskId": flipped["taskId"], "rmse": diff}

    layout_task = poll_task(base_url, cookie, create_task(base_url, cookie, upload["uploadId"], {"printLayoutEnabled": True, "layoutPaperSize": "five-inch", "layoutCropLine": True, "pluginFlags": ["layoutCropLine", "fiveInchPaper"]})["taskId"])
    if not layout_task.get("layoutResult"):
        raise SystemExit(f"layoutCropLine task missing layoutResult: {layout_task}")
    layout_bytes, _ = fetch(base_url, layout_task["layoutResult"]["downloadUrl"], cookie)
    (out_dir / "layout_crop_line.png").write_bytes(layout_bytes)
    summary["tasks"]["layoutCropLine"] = {"taskId": layout_task["taskId"], "bytes": len(layout_bytes)}

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=list))


if __name__ == "__main__":
    main()
