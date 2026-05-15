from concurrent.futures import ThreadPoolExecutor
import base64
import csv
import hashlib
import hmac
import json
import mimetypes
import os
from collections import Counter, defaultdict, deque
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, BackgroundTasks, Depends, Request, Response
from fastapi.responses import FileResponse
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError

from hivision import IDCreator
from hivision.error import FaceError
from hivision.creator.layout_calculator import (
    generate_layout_array,
    generate_layout_image,
)
from hivision.creator.choose_handler import choose_handler
from hivision.plugin.ai_enhance import AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.errors import AIEnhanceValidationError
from hivision.utils import (
    add_background,
    resize_image_to_kb,
    bytes_2_base64,
    base64_2_numpy,
    hex_to_rgb,
    add_watermark,
    save_image_dpi_to_bytes,
)
import numpy as np
import cv2
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.formparsers import MultiPartParser

# 设置Starlette表单字段大小限制。应用层仍会做二次校验，避免网关配置变化时失守。
MAX_UPLOAD_BYTES = int(os.environ.get("IDPHOTO_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.environ.get("IDPHOTO_MAX_IMAGE_PIXELS", str(24_000_000)))
RUNTIME_TTL_SECONDS = int(os.environ.get("IDPHOTO_RUNTIME_TTL_SECONDS", str(6 * 60 * 60)))
DOWNLOAD_TTL_SECONDS = int(os.environ.get("IDPHOTO_DOWNLOAD_TTL_SECONDS", str(min(RUNTIME_TTL_SECONDS, 30 * 60))))
APP_USERNAME = os.environ.get("IDPHOTO_APP_USERNAME", "")
APP_PASSWORD = os.environ.get("IDPHOTO_APP_PASSWORD", "")
APP_SESSION_SECRET_RAW = os.environ.get("IDPHOTO_APP_SESSION_SECRET", "")
APP_SESSION_COOKIE = "idphoto_ai_session"
APP_SESSION_TTL_SECONDS = int(os.environ.get("IDPHOTO_APP_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
RATE_LIMIT_UPLOADS_PER_MINUTE = int(os.environ.get("IDPHOTO_RATE_LIMIT_UPLOADS_PER_MINUTE", "10"))
RATE_LIMIT_TASKS_PER_MINUTE = int(os.environ.get("IDPHOTO_RATE_LIMIT_TASKS_PER_MINUTE", "10"))
RATE_LIMIT_LOGIN_PER_MINUTE = int(os.environ.get("IDPHOTO_RATE_LIMIT_LOGIN_PER_MINUTE", "10"))
AUDIT_IP_HASH_SECRET = os.environ.get("IDPHOTO_AUDIT_IP_HASH_SECRET") or APP_SESSION_SECRET_RAW or "idphoto-ai-audit-local"
SERVICE_PHASE = "5D"
ALLOWED_UPLOAD_TYPES: dict[str, set[str]] = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}
ALLOWED_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}

MultiPartParser.max_part_size = min(MAX_UPLOAD_BYTES, 20 * 1024 * 1024)
MultiPartParser.max_file_size = MAX_UPLOAD_BYTES

logger = logging.getLogger(__name__)

if APP_SESSION_SECRET_RAW:
    APP_SESSION_SECRET = APP_SESSION_SECRET_RAW.encode("utf-8")
else:
    APP_SESSION_SECRET = os.urandom(32)
    logger.warning("[API] IDPHOTO_APP_SESSION_SECRET is not set; using an ephemeral app session secret for this process.")

_download_secret = os.environ.get("IDPHOTO_DOWNLOAD_SIGNING_SECRET")
if _download_secret:
    DOWNLOAD_SIGNING_SECRET = _download_secret.encode("utf-8")
else:
    DOWNLOAD_SIGNING_SECRET = os.urandom(32)
    logger.warning("[API] IDPHOTO_DOWNLOAD_SIGNING_SECRET is not set; using an ephemeral download signing secret for this process.")

app = FastAPI()
creator = IDCreator()
ai_enhance_service = AIEnhanceService()

RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
RESULT_DIR = RUNTIME_DIR / "results"
for runtime_path in (UPLOAD_DIR, RESULT_DIR):
    runtime_path.mkdir(parents=True, exist_ok=True)

app.mount("/runtime/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="runtime_uploads")
app.mount("/runtime/results", StaticFiles(directory=str(RESULT_DIR)), name="runtime_results")

TaskStatus = Literal["queued", "processing", "succeeded", "failed", "expired"]
Platform = Literal["web", "mobileWeb", "wechatMiniapp"]
AiMode = Literal["none", "preview", "enhance"]


def utc_expires_at(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def utc_expires_at_seconds(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def ttl_hours() -> float:
    return round(RUNTIME_TTL_SECONDS / 3600, 2)


def public_runtime_url(kind: Literal["uploads", "results"], filename: str) -> str:
    return f"/runtime/{kind}/{filename}"


def error_detail(code: str, message: str, retryable: bool = True, trace_id: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if trace_id:
        error["traceId"] = trace_id
    return {"error": error}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_id(request: Request | None = None) -> str:
    if request:
        incoming = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        if incoming:
            return incoming[:80]
    return f"req_{uuid.uuid4().hex[:12]}"


def client_ip(request: Request | None) -> str:
    if not request:
        return "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def hash_ip(ip: str) -> str:
    digest = hmac.new(AUDIT_IP_HASH_SECRET.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"iphash_{digest[:16]}"


def session_fingerprint(request: Request | None) -> str:
    token = request.cookies.get(APP_SESSION_COOKIE) if request else None
    if not token:
        return "anonymous"
    digest = hmac.new(APP_SESSION_SECRET, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sess_{digest[:16]}"


def audit_user(session: dict[str, Any] | None = None, username: str | None = None) -> str | None:
    value = username or (str(session.get("sub")) if session else None)
    return value if value else None


def safe_error_code(exc: Exception | None) -> str | None:
    if not exc:
        return None
    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        error = detail.get("error") if isinstance(detail.get("error"), dict) else {}
        code = error.get("code")
        return str(code) if code else f"HTTP_{exc.status_code}"
    return exc.__class__.__name__


def log_event(event: str, request: Request | None = None, *, status: str = "ok", user: str | None = None, session: dict[str, Any] | None = None, route: str | None = None, request_id_value: str | None = None, task_id: str | None = None, upload_id: str | None = None, duration_ms: int | None = None, error_code: str | None = None, extra: dict[str, Any] | None = None) -> None:
    record: dict[str, Any] = {
        "ts": now_iso(),
        "event": event,
        "status": status,
        "requestId": request_id_value or request_id(request),
        "route": route or (getattr(request, "scope", {}).get("route").path if request and getattr(request, "scope", {}).get("route") else (request.url.path if request else None)),
        "ipHash": hash_ip(client_ip(request)),
        "sessionHash": session_fingerprint(request),
    }
    if audit_user(session, user):
        record["user"] = audit_user(session, user)
    if task_id:
        record["taskId"] = task_id
    if upload_id:
        record["uploadId"] = upload_id
    if duration_ms is not None:
        record["durationMs"] = duration_ms
    if error_code:
        record["errorCode"] = error_code
    if extra:
        for key, value in extra.items():
            if key not in {"password", "cookie", "authorization", "token", "url", "filename", "path"}:
                record[key] = value
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({k: v for k, v in record.items() if v is not None}, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        logger.exception("[API] failed to write audit event")


def rate_limit_key(request: Request, scope: str) -> tuple[str, str]:
    return (scope, f"{hash_ip(client_ip(request))}:{session_fingerprint(request)}")


def check_rate_limit(request: Request, scope: Literal["login", "upload", "task"], limit: int) -> None:
    if limit <= 0:
        return
    now = time.time()
    bucket = RATE_LIMITS[rate_limit_key(request, scope)]
    while bucket and bucket[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= limit:
        log_event("rate_limit_hit", request, status="blocked", route=request.url.path, error_code="RATE_LIMITED", extra={"scope": scope, "limit": limit, "windowSeconds": RATE_LIMIT_WINDOW_SECONDS})
        raise HTTPException(status_code=429, detail=error_detail("RATE_LIMITED", "Too many requests. Please retry later.", retryable=True))
    bucket.append(now)


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def iter_audit_events(since: float | None = None):
    if not AUDIT_LOG_FILE.exists():
        return
    with AUDIT_LOG_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
                if since is not None:
                    ts = datetime.fromisoformat(str(event.get("ts", "")).replace("Z", "+00:00")).timestamp()
                    if ts < since:
                        continue
                yield event
            except Exception:
                continue


def build_admin_stats() -> dict[str, Any]:
    now_ts = time.time()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    events_24h = list(iter_audit_events(now_ts - 24 * 60 * 60) or [])
    today_events = [event for event in events_24h if datetime.fromisoformat(str(event.get("ts", "")).replace("Z", "+00:00")).timestamp() >= today_start]

    def count(events: list[dict[str, Any]], name: str, status: str | None = None) -> int:
        return sum(1 for event in events if event.get("event") == name and (status is None or event.get("status") == status))

    error_codes = Counter(str(event.get("errorCode")) for event in events_24h if event.get("errorCode"))
    return {
        "phase": SERVICE_PHASE,
        "generatedAt": now_iso(),
        "today": {
            "logins": count(today_events, "login", "success"),
            "uploads": count(today_events, "upload", "success"),
            "tasksSucceeded": count(today_events, "task_complete", "success"),
            "tasksFailed": count(today_events, "task_complete", "failure"),
            "downloads": count(today_events, "download", "success"),
            "rateLimitHits": count(today_events, "rate_limit_hit"),
        },
        "last24h": {
            "logins": count(events_24h, "login", "success"),
            "uploads": count(events_24h, "upload", "success"),
            "tasksSucceeded": count(events_24h, "task_complete", "success"),
            "tasksFailed": count(events_24h, "task_complete", "failure"),
            "downloads": count(events_24h, "download", "success"),
            "rateLimitHits": count(events_24h, "rate_limit_hit"),
        },
        "runtime": {
            "uploadsBytes": directory_size_bytes(UPLOAD_DIR),
            "resultsBytes": directory_size_bytes(RESULT_DIR),
            "uploadsTracked": len(UPLOADS),
            "tasksTracked": len(TASKS),
        },
        "recentErrorCodesTop": [{"code": code, "count": value} for code, value in error_codes.most_common(8)],
        "rateLimits": {
            "uploadsPerMinute": RATE_LIMIT_UPLOADS_PER_MINUTE,
            "tasksPerMinute": RATE_LIMIT_TASKS_PER_MINUTE,
            "loginPerMinute": RATE_LIMIT_LOGIN_PER_MINUTE,
            "storage": "in-process",
        },
    }


def safe_suffix(filename: str | None, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if content_type in ALLOWED_UPLOAD_TYPES and suffix in ALLOWED_UPLOAD_TYPES[content_type]:
        return suffix
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"


def upload_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error_detail(code, message, retryable=True))


def sniff_magic(content: bytes, content_type: str) -> bool:
    if content_type == "image/webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return any(content.startswith(prefix) for prefix in ALLOWED_MAGIC_BYTES.get(content_type, ()))


def validate_upload_metadata(filename: str | None, content_type: str | None) -> str:
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type not in ALLOWED_UPLOAD_TYPES:
        raise upload_error(400, "INVALID_FILE_TYPE", "Only JPG, PNG, or WebP image uploads are supported.")
    suffix = Path(filename or "").suffix.lower()
    if not suffix or suffix not in ALLOWED_UPLOAD_TYPES[normalized_type]:
        allowed = ", ".join(sorted({ext for exts in ALLOWED_UPLOAD_TYPES.values() for ext in exts}))
        raise upload_error(400, "INVALID_FILE_EXTENSION", f"Unsupported file extension. Allowed extensions: {allowed}.")
    return normalized_type


def validate_upload_bytes(content: bytes, content_type: str) -> None:
    if not content:
        raise upload_error(400, "EMPTY_UPLOAD", "Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise upload_error(413, "FILE_TOO_LARGE", f"Uploaded file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.")
    if not sniff_magic(content, content_type):
        raise upload_error(400, "INVALID_IMAGE_BYTES", "Uploaded file content does not match the declared image type.")
    try:
        import io
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise upload_error(400, "INVALID_IMAGE_BYTES", "Uploaded file could not be decoded as a valid image.") from exc
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise upload_error(413, "IMAGE_TOO_LARGE", f"Image dimensions exceed the {MAX_IMAGE_PIXELS} pixel limit.")


DEFAULT_TEMPLATE_ID = "cn-id-1inch"
DEFAULT_BACKGROUND = "white"
DEFAULT_TEMPLATE_DPI = 300
DEFAULT_HEAD_MEASURE_RATIO = 0.2
DEFAULT_HEAD_HEIGHT_RATIO = 0.45
DEFAULT_TOP_DISTANCE_MAX = 0.12
DEFAULT_TOP_DISTANCE_MIN = 0.10
TEMPLATE_CSV_PATH = Path(__file__).resolve().parent / "demo" / "assets" / "size_list_CN.csv"
COMMON_TEMPLATE_LABELS = {"一寸", "二寸", "小一寸", "小二寸", "大一寸", "大二寸"}
LEGACY_TEMPLATE_ID_MAP = {
    "一寸": "cn-id-1inch",
    "二寸": "cn-id-2inch",
    "大一寸": "passport-visa",
}
TEMPLATE_PRINT_NOTES = {
    "一寸": "常用报名 / 简历 / 证件归档",
    "二寸": "考试 / 档案 / 纸质冲印",
    "大一寸": "护照、签证材料预检",
    "美国签证": "签证材料预检",
    "日本签证": "签证材料预检",
    "韩国签证": "签证材料预检",
    "社保卡": "制卡与归档参考",
    "电子驾驶证": "电子证照申领参考",
}


def pixels_to_mm(pixels: int, dpi: int = DEFAULT_TEMPLATE_DPI) -> float:
    return round((pixels / dpi) * 25.4, 1)


def format_template_size(height: int, width: int, dpi: int = DEFAULT_TEMPLATE_DPI) -> str:
    return f"{pixels_to_mm(width, dpi)} × {pixels_to_mm(height, dpi)} mm · {width} × {height} px"


def build_template_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    with TEMPLATE_CSV_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            label = str(row.get("Name") or "").strip()
            if not label:
                continue
            height = int(row["Height"])
            width = int(row["Width"])
            template_id = LEGACY_TEMPLATE_ID_MAP.get(label, f"cn-photo-{index:02d}")
            specs[template_id] = {
                "label": label,
                "size_mm": format_template_size(height, width),
                "height": height,
                "width": width,
                "dpi": DEFAULT_TEMPLATE_DPI,
                "head_measure_ratio": DEFAULT_HEAD_MEASURE_RATIO,
                "head_height_ratio": DEFAULT_HEAD_HEIGHT_RATIO,
                "top_distance_max": DEFAULT_TOP_DISTANCE_MAX,
                "top_distance_min": DEFAULT_TOP_DISTANCE_MIN,
                "common": label in COMMON_TEMPLATE_LABELS,
                "print_note": TEMPLATE_PRINT_NOTES.get(label, "官方结果由 Hivision IDCreator 渲染。"),
            }
    return specs


# Pixel dimensions are loaded from demo/assets/size_list_CN.csv and passed to
# IDCreator as (height, width). Web v2 now shares the full preset list instead
# of keeping a reduced hard-coded subset.
TEMPLATE_SPECS: dict[str, dict[str, Any]] = build_template_specs()

AI_PRO_SUPPORTED_MODES = {"ai_repair", "ai_blue_formal_id_photo", "executive_headshot"}
AI_PRO_MODE_TEMPLATE = {
    "ai_repair": "ai_repair_basic",
    "ai_blue_formal_id_photo": "ai_blue_formal_id_photo",
    "executive_headshot": "executive_headshot_apple_style",
}
PROMPT_TEMPLATE_REGISTRY: dict[str, dict[str, Any]] = {
    "executive_headshot_apple_style": {
        "id": "executive_headshot_apple_style",
        "version": "2026-05-phase1",
        "mode": "executive_headshot",
        "status": "mock",
        "creditCost": 3,
        "usageLabel": "non_official_portrait",
        "userParamsSchema": {"outfit": "string", "expression": "string", "style": "string", "retouchLevel": "low|medium|high"},
        "promptMetadata": {"styleFamily": "executive studio portrait", "officialUse": False, "warning": "AI 形象照 / 非正式证件用途"},
    },
    "ai_blue_formal_id_photo": {
        "id": "ai_blue_formal_id_photo",
        "version": "2026-05-phase1",
        "mode": "ai_blue_formal_id_photo",
        "status": "mock",
        "creditCost": 2,
        "usageLabel": "official_candidate",
        "userParamsSchema": {"backgroundColor": "blue", "outfit": "string", "expression": "string", "retouchLevel": "low|medium|high"},
        "promptMetadata": {"background": "blue", "outfitBaseline": "dark suit, white shirt", "cameraTexture": "Canon 5D-like", "warning": "AI 增强证件照候选，需按提交平台要求核验"},
    },
    "cn_blue_480x640_20_40kb": {
        "id": "cn_blue_480x640_20_40kb",
        "version": "2026-05-phase1",
        "mode": "ai_blue_formal_id_photo",
        "status": "spec_profile",
        "creditCost": 0,
        "usageLabel": "official_candidate",
        "userParamsSchema": {"outputSpec": "480x640", "backgroundColor": "blue"},
        "promptMetadata": {
            "specProfile": {"width": 480, "height": 640, "dpi": 300, "fileKbRange": [20, 40], "backgroundColor": "blue"},
            "qualityRules": ["single frontal face", "plain blue background", "verify platform file-size constraints"],
        },
    },
    "ai_repair_basic": {
        "id": "ai_repair_basic",
        "version": "2026-05-phase1",
        "mode": "ai_repair",
        "status": "mock",
        "creditCost": 1,
        "usageLabel": "preview_repair",
        "userParamsSchema": {"retouchLevel": "low|medium|high", "style": "natural"},
        "promptMetadata": {"operation": "local mock repair preview", "officialUse": False},
    },
}


# add_background() and save_image_dpi_to_bytes() both operate on RGB-like
# channel order in this project path despite the legacy parameter name being
# `bgr`. Keep the web presets aligned with demo/processor.py's HEX handling.
BACKGROUND_RGB: dict[str, tuple[int, int, int]] = {
    "white": (255, 255, 255),
    "blue": (98, 139, 206),
    "red": (215, 69, 50),
    "gray": (242, 240, 240),
}
BACKGROUND_BGR = BACKGROUND_RGB

LAYOUT_PAPER_SIZES: dict[str, dict[str, Any]] = {
    "six-inch": {"label": "六寸", "height": 1205, "width": 1795},
    "five-inch": {"label": "五寸", "height": 1051, "width": 1500},
    "a4": {"label": "A4", "height": 2479, "width": 3508},
}
DEFAULT_LAYOUT_PAPER_SIZE = "six-inch"

BACKGROUND_LABELS: dict[str, str] = {
    "white": "白底",
    "blue": "蓝底",
    "red": "红底",
    "gray": "灰底",
}

TASKS_FILE = RUNTIME_DIR / "tasks.json"
AUDIT_LOG_FILE = RUNTIME_DIR / "audit.jsonl"
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="idcreator-task")


def task_public_result(task_id: str, filename: str) -> str:
    return public_runtime_url("results", f"{task_id}/{filename}")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def auth_is_configured() -> bool:
    return bool(APP_USERNAME and APP_PASSWORD)


def build_session_token(username: str) -> str:
    expires_at_ts = int(time.time() + APP_SESSION_TTL_SECONDS)
    payload = {"sub": username, "exp": expires_at_ts}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(APP_SESSION_SECRET, payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(APP_SESSION_SECRET, payload_part.encode("ascii"), hashlib.sha256).digest()
        provided = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected, provided):
            return None
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    if payload.get("sub") != APP_USERNAME:
        return None
    return payload


def require_auth(request: Request) -> dict[str, Any]:
    if not auth_is_configured():
        raise HTTPException(status_code=503, detail=error_detail("AUTH_NOT_CONFIGURED", "Application login is not configured.", retryable=False))
    session = verify_session_token(request.cookies.get(APP_SESSION_COOKIE))
    if not session:
        raise HTTPException(status_code=401, detail=error_detail("AUTH_REQUIRED", "Login is required.", retryable=False))
    return session


def set_session_cookie(response: Response, username: str) -> None:
    response.set_cookie(
        key=APP_SESSION_COOKIE,
        value=build_session_token(username),
        max_age=APP_SESSION_TTL_SECONDS,
        httponly=True,
        secure=os.environ.get("IDPHOTO_APP_COOKIE_SECURE", "1") != "0",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=APP_SESSION_COOKIE,
        path="/",
        secure=os.environ.get("IDPHOTO_APP_COOKIE_SECURE", "1") != "0",
        httponly=True,
        samesite="lax",
    )


def result_relative_path(task_id: str, filename: str) -> str:
    return f"{task_id}/{Path(filename).name}"


def signed_download_url(task_id: str, filename: str, purpose: Literal["preview", "download"] = "download") -> tuple[str, str]:
    expires_at_ts = int(time.time() + min(DOWNLOAD_TTL_SECONDS, RUNTIME_TTL_SECONDS))
    payload = {
        "path": result_relative_path(task_id, filename),
        "purpose": purpose,
        "exp": expires_at_ts,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(DOWNLOAD_SIGNING_SECRET, payload_part.encode("ascii"), hashlib.sha256).digest()
    token = f"{payload_part}.{_b64url_encode(signature)}"
    return f"/api/downloads/{token}", datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()


def verify_download_token(token: str) -> dict[str, Any]:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(DOWNLOAD_SIGNING_SECRET, payload_part.encode("ascii"), hashlib.sha256).digest()
        provided = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected, provided):
            raise ValueError("bad signature")
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=403, detail=error_detail("INVALID_DOWNLOAD_TOKEN", "Download token is invalid or has been tampered with.", retryable=False)) from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=403, detail=error_detail("DOWNLOAD_TOKEN_EXPIRED", "Download token has expired.", retryable=False))
    if payload.get("purpose") not in {"preview", "download"} or not isinstance(payload.get("path"), str):
        raise HTTPException(status_code=403, detail=error_detail("INVALID_DOWNLOAD_TOKEN", "Download token payload is invalid.", retryable=False))
    return payload


def resolve_result_file(relative_path: str) -> Path:
    candidate = (RESULT_DIR / relative_path).resolve()
    result_root = RESULT_DIR.resolve()
    if candidate != result_root and result_root not in candidate.parents:
        raise HTTPException(status_code=403, detail=error_detail("INVALID_DOWNLOAD_PATH", "Download path is outside the result directory.", retryable=False))
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=error_detail("DOWNLOAD_FILE_NOT_FOUND", "Download file was not found or has expired.", retryable=True))
    return candidate


def build_result_file(task_id: str, lane: str, filename: str) -> dict[str, str]:
    download_url, expires_at = signed_download_url(task_id, filename, "download")
    preview_url, _ = signed_download_url(task_id, filename, "preview")
    safe_lane = "".join(char if char.isalnum() else "_" for char in lane)[:32] or "derived"
    return {
        "fileId": f"file_result_{safe_lane}_{task_id[-6:]}",
        "previewUrl": preview_url,
        "downloadUrl": download_url,
        "expiresAt": expires_at,
    }


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def cleanup_runtime(now: float | None = None, dry_run: bool = False) -> dict[str, int]:
    now = time.time() if now is None else now
    cutoff = now - RUNTIME_TTL_SECONDS
    removed_uploads = 0
    removed_results = 0
    expired_tasks = 0

    active_upload_ids = {task.get("uploadId") for task in TASKS.values() if task.get("status") in {"queued", "processing"}}
    active_task_ids = {task_id for task_id, task in TASKS.items() if task.get("status") in {"queued", "processing"}}

    for upload_id, upload in list(UPLOADS.items()):
        if upload_id in active_upload_ids:
            continue
        if float(upload.get("createdAt", 0)) < cutoff:
            if not dry_run:
                remove_path(Path(upload.get("path", "")))
                UPLOADS.pop(upload_id, None)
            removed_uploads += 1

    for upload_file in UPLOAD_DIR.iterdir():
        if upload_file.is_file() and upload_file.stat().st_mtime < cutoff:
            if not any(Path(upload.get("path", "")) == upload_file for upload in UPLOADS.values()):
                if not dry_run:
                    remove_path(upload_file)
                removed_uploads += 1

    for task_id, task in list(TASKS.items()):
        if task.get("status") in {"queued", "processing"}:
            continue
        if float(task.get("createdAt", 0)) < cutoff:
            if not dry_run:
                remove_path(RESULT_DIR / task_id)
                TASKS.pop(task_id, None)
            expired_tasks += 1
            removed_results += 1

    for result_dir in RESULT_DIR.iterdir():
        if result_dir.name in active_task_ids:
            continue
        if result_dir.stat().st_mtime < cutoff and result_dir.name not in TASKS:
            if not dry_run:
                remove_path(result_dir)
            removed_results += 1

    if (removed_uploads or removed_results or expired_tasks) and not dry_run:
        if "TASKS_FILE" in globals():
            persist_tasks()
        logger.info("[API] runtime cleanup removed uploads=%s results=%s tasks=%s", removed_uploads, removed_results, expired_tasks)
    return {"uploads": removed_uploads, "results": removed_results, "tasks": expired_tasks}


def persist_tasks() -> None:
    serializable = {task_id: {key: value for key, value in task.items() if key != "future"} for task_id, task in TASKS.items()}
    tmp = TASKS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TASKS_FILE)


def load_tasks() -> None:
    if not TASKS_FILE.exists():
        return
    try:
        stored = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        for task_id, task in stored.items():
            if task.get("status") in {"queued", "processing"}:
                task["status"] = "failed"
                task["error"] = {
                    "code": "TASK_INTERRUPTED",
                    "message": "Task was interrupted before completion. Please create a new task.",
                    "retryable": True,
                }
            TASKS[task_id] = task
    except Exception:
        logger.exception("[API] failed to load persisted tasks")


def supported_template_ids() -> list[str]:
    return list(TEMPLATE_SPECS.keys())


def supported_backgrounds() -> list[str]:
    return list(BACKGROUND_RGB.keys())


def supported_layout_paper_sizes() -> list[str]:
    return list(LAYOUT_PAPER_SIZES.keys())


def validate_template_id(template_id: str | None) -> str:
    template = template_id or DEFAULT_TEMPLATE_ID
    if template not in TEMPLATE_SPECS:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "UNSUPPORTED_TEMPLATE",
                f"Unsupported templateId '{template}'. Supported values: {', '.join(supported_template_ids())}.",
                retryable=True,
            ),
        )
    return template


def validate_background(background: Any) -> str:
    value = str(background or DEFAULT_BACKGROUND)
    if value == "custom":
        return value
    if value not in BACKGROUND_RGB:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "UNSUPPORTED_BACKGROUND",
                f"Unsupported background '{value}'. Supported values: {', '.join(supported_backgrounds())}.",
                retryable=True,
            ),
        )
    return value


def validate_layout_paper_size(value: Any) -> str:
    paper_size = str(value or DEFAULT_LAYOUT_PAPER_SIZE)
    aliases = {"six": "six-inch", "6inch": "six-inch", "5inch": "five-inch", "five": "five-inch"}
    paper_size = aliases.get(paper_size, paper_size)
    if paper_size not in LAYOUT_PAPER_SIZES:
        raise ValueError(f"Unsupported layoutPaperSize '{paper_size}'. Supported values: {', '.join(supported_layout_paper_sizes())}.")
    return paper_size


def normalize_plugin_flags(options: dict[str, Any]) -> set[str]:
    raw_flags = options.get("pluginFlags")
    flags: set[str] = set()
    if isinstance(raw_flags, (list, tuple, set)):
        flags.update(str(item) for item in raw_flags if item is not None)
    for key in ("faceAlign", "horizontalFlip", "layoutCropLine", "jpegFormat", "fiveInchPaper"):
        if options.get(key):
            flags.add(key)
    if options.get("layoutPaperSize") == "five-inch" or options.get("printLayoutSize") == "five-inch":
        flags.add("fiveInchPaper")
    return flags


def normalize_render_mode(value: Any) -> str:
    aliases = {
        "solid": "pure_color",
        "pure_color": "pure_color",
        "pureColor": "pure_color",
        "upDownGradientWhite": "updown_gradient",
        "updown_gradient": "updown_gradient",
        "updownGradient": "updown_gradient",
        "centerGradientWhite": "center_gradient",
        "center_gradient": "center_gradient",
        "centerGradient": "center_gradient",
    }
    mode = aliases.get(str(value or "solid"), None)
    if not mode:
        raise ValueError("renderMode must be solid, upDownGradientWhite, or centerGradientWhite.")
    return mode


def normalize_hex_color(value: Any) -> tuple[int, int, int]:
    color = str(value or "").strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in color):
        raise ValueError("customBackgroundHex must be a 3 or 6 digit HEX color.")
    return tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))


def normalize_rgb_color(value: Any) -> tuple[int, int, int]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    elif isinstance(value, dict):
        parts = [value.get("r"), value.get("g"), value.get("b")]
    else:
        raise ValueError("customBackgroundRgb must be an RGB array, object, or comma-separated string.")
    if len(parts) != 3:
        raise ValueError("customBackgroundRgb must contain exactly three channels.")
    channels = tuple(clamp_int(part, -1, 0, 255) for part in parts)
    return channels


def resolve_background_rgb(options: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
    background = validate_background(options.get("background", DEFAULT_BACKGROUND))
    if background == "custom" or options.get("customBackgroundEnabled"):
        if options.get("customBackgroundHex"):
            return "custom", normalize_hex_color(options.get("customBackgroundHex"))
        if options.get("customBackgroundRgb") is not None:
            return "custom", normalize_rgb_color(options.get("customBackgroundRgb"))
        raise ValueError("Custom background requires customBackgroundHex or customBackgroundRgb.")
    return background, BACKGROUND_RGB[background]


def normalize_image_kb_mode(value: Any) -> str:
    mode = str(value or "exact")
    aliases = {"pad": "exact", "maxNoPad": "max", "max-no-pad": "max"}
    mode = aliases.get(mode, mode)
    if mode not in {"exact", "max"}:
        raise ValueError("imageKbMode must be 'exact' or 'max'.")
    return mode


def normalize_template_options(template_id: str, options: dict[str, Any]) -> dict[str, Any]:
    template = validate_template_id(template_id)
    spec = dict(TEMPLATE_SPECS[template])
    user_spec = options.get("spec") if isinstance(options.get("spec"), dict) else {}
    aliases = {
        "height": "height",
        "width": "width",
        "dpi": "dpi",
        "head_measure_ratio": "head_measure_ratio",
        "headMeasureRatio": "head_measure_ratio",
        "head_height_ratio": "head_height_ratio",
        "headHeightRatio": "head_height_ratio",
        "top_distance_max": "top_distance_max",
        "topDistanceMax": "top_distance_max",
        "top_distance_min": "top_distance_min",
        "topDistanceMin": "top_distance_min",
    }
    # Only allow controlled numeric overrides, and keep invalid input noisy rather
    # than silently creating a wrong officialResult.
    for source in (options, user_spec):
        for source_key, target_key in aliases.items():
            if source_key in source and source[source_key] is not None:
                spec[target_key] = source[source_key]
    if options.get("topDistance") is not None and options.get("topDistanceMax") is None and options.get("top_distance_max") is None:
        spec["top_distance_max"] = options["topDistance"]
    try:
        spec["height"] = int(spec.get("height", 413))
        spec["width"] = int(spec.get("width", 295))
        spec["dpi"] = int(spec.get("dpi", DEFAULT_TEMPLATE_DPI))
        spec["head_measure_ratio"] = float(spec.get("head_measure_ratio", DEFAULT_HEAD_MEASURE_RATIO))
        spec["head_height_ratio"] = float(spec.get("head_height_ratio", DEFAULT_HEAD_HEIGHT_RATIO))
        spec["top_distance_max"] = float(spec.get("top_distance_max", DEFAULT_TOP_DISTANCE_MAX))
        spec["top_distance_min"] = float(spec.get("top_distance_min", spec["top_distance_max"] - 0.02))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric template spec for '{template}': {exc}") from exc
    if spec["height"] <= 0 or spec["width"] <= 0 or spec["dpi"] <= 0:
        raise ValueError(f"Invalid template dimensions for '{template}'.")
    if spec["top_distance_min"] > spec["top_distance_max"]:
        spec["top_distance_min"] = max(0.0, spec["top_distance_max"] - 0.02)
    spec["template_id"] = template
    return spec


def read_upload_image(upload_path: str) -> np.ndarray:
    image_bytes = Path(upload_path).read_bytes()
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Uploaded image could not be decoded.")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def write_png(image: np.ndarray, output_path: Path, dpi: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_image_dpi_to_bytes(image.astype(np.uint8), str(output_path), dpi=dpi)


def write_jpeg(image: np.ndarray, output_path: Path, dpi: int, quality: int = 95) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_image = Image.fromarray(image.astype(np.uint8))
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    pil_image.save(output_path, format="JPEG", quality=quality, dpi=(dpi, dpi))


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def make_layout_from_official(official_image: np.ndarray, spec: dict[str, Any], output_path: Path, dpi: int, *, crop_line: bool = False) -> None:
    paper_size = validate_layout_paper_size(spec.get("layoutPaperSize") or spec.get("printLayoutSize"))
    paper = LAYOUT_PAPER_SIZES[paper_size]
    layout_height = clamp_int(spec.get("layoutHeight"), int(paper["height"]), 200, 5000)
    layout_width = clamp_int(spec.get("layoutWidth"), int(paper["width"]), 200, 5000)
    typography_arr, typography_rotate = generate_layout_array(
        input_height=int(spec["height"]),
        input_width=int(spec["width"]),
        LAYOUT_HEIGHT=layout_height,
        LAYOUT_WIDTH=layout_width,
    )
    layout_image = generate_layout_image(
        official_image,
        typography_arr,
        typography_rotate,
        height=int(spec["height"]),
        width=int(spec["width"]),
        crop_line=crop_line,
        LAYOUT_HEIGHT=layout_height,
        LAYOUT_WIDTH=layout_width,
    )
    write_png(layout_image.astype(np.uint8), output_path, dpi)


def make_watermarked_from_official(official_image: np.ndarray, options: dict[str, Any], output_path: Path, dpi: int) -> None:
    text = str(options.get("watermarkText") or "仅供证件照使用")[:80]
    watermarked = add_watermark(
        image=official_image,
        text=text,
        color=str(options.get("watermarkTextColor") or "#8B8B1B"),
        size=clamp_int(options.get("watermarkTextSize"), 32, 8, 160),
        opacity=clamp_float(options.get("watermarkTextOpacity"), 0.35, 0.05, 1.0),
        angle=clamp_int(options.get("watermarkTextAngle"), 30, -90, 90),
        space=clamp_int(options.get("watermarkTextSpace"), 75, 10, 300),
    )
    write_png(watermarked.astype(np.uint8), output_path, dpi)


def make_compressed_from_official(official_image: np.ndarray, target_kb: Any, output_path: Path, dpi: int, *, mode: str = "exact") -> int:
    kb = clamp_int(target_kb, 0, 10, 1000)
    if kb <= 0:
        raise ValueError("imageKb must be a positive number between 10 and 1000.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(official_image.astype(np.uint8))
    if image.mode != "RGB":
        image = image.convert("RGB")
    if normalize_image_kb_mode(mode) == "exact":
        resize_image_to_kb(official_image.astype(np.uint8), str(output_path), kb, dpi=dpi)
        return kb

    import io
    best_bytes: bytes | None = None
    for quality in range(95, 0, -5):
        byte_stream = io.BytesIO()
        image.save(byte_stream, format="JPEG", quality=quality, dpi=(dpi, dpi))
        candidate = byte_stream.getvalue()
        best_bytes = candidate
        if len(candidate) <= kb * 1024:
            break
    output_path.write_bytes(best_bytes or b"")
    return kb


def _quality_issue(code: str, message: str, severity: str = "warning", metric: str | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message, "severity": severity}
    if metric:
        issue["metric"] = metric
    return issue


def _foreground_mask_from_alpha(image: np.ndarray) -> np.ndarray | None:
    if image is not None and image.ndim == 3 and image.shape[2] >= 4:
        return image[:, :, 3] > 10
    return None


def _sample_background_pixels(official_rgb: np.ndarray, transparent_standard: np.ndarray | None = None) -> np.ndarray:
    mask = _foreground_mask_from_alpha(transparent_standard) if transparent_standard is not None else None
    if mask is not None and (~mask).sum() >= 64:
        return official_rgb[:, :, :3][~mask]
    height, width = official_rgb.shape[:2]
    border = max(2, min(height, width) // 20)
    border_mask = np.zeros((height, width), dtype=bool)
    border_mask[:border, :] = True
    border_mask[-border:, :] = True
    border_mask[:, :border] = True
    border_mask[:, -border:] = True
    return official_rgb[:, :, :3][border_mask]


def build_quality_report(result: Any, official_rgb: np.ndarray, spec: dict[str, Any], background_rgb: tuple[int, int, int]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    suggestions: list[str] = []
    score = 100

    height, width = official_rgb.shape[:2]
    expected_height, expected_width = int(spec["height"]), int(spec["width"])
    dimensions_match = height == expected_height and width == expected_width
    aspect_delta = abs((width / max(1, height)) - (expected_width / max(1, expected_height)))
    metrics["dimensions"] = {
        "actual": {"width": width, "height": height},
        "expected": {"width": expected_width, "height": expected_height},
        "match": dimensions_match,
        "aspectDelta": round(aspect_delta, 6),
    }
    if not dimensions_match:
        errors.append(_quality_issue("OUTPUT_DIMENSION_MISMATCH", "输出尺寸与当前规格不一致。", "error", "dimensions"))
        suggestions.append("请重新生成，或检查所选规格的 width/height 参数。")
        score -= 30

    face = getattr(result, "face", None)
    face_rectangle = face.get("rectangle") if isinstance(face, dict) else None
    roll_angle = face.get("roll_angle") if isinstance(face, dict) else None
    metrics["face"] = {
        "count": 1 if face_rectangle is not None else None,
        "detector": "IDCreator",
        "rectangle": [round(float(v), 3) for v in face_rectangle] if face_rectangle is not None else None,
        "rollAngle": round(float(roll_angle), 3) if roll_angle is not None else None,
    }
    if face_rectangle is None:
        warnings.append(_quality_issue("FACE_METRIC_UNAVAILABLE", "人脸数量已由 IDCreator 主链路校验，但未返回可展示的人脸框指标。", "warning", "face"))
        score -= 5

    foreground_mask = _foreground_mask_from_alpha(getattr(result, "standard", None))
    if foreground_mask is not None and foreground_mask.any():
        ys, xs = np.where(foreground_mask)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        fg_width = max(1, x_max - x_min + 1)
        fg_height = max(1, y_max - y_min + 1)
        top_distance_ratio = y_min / max(1, height)
        horizontal_center_offset = ((x_min + x_max + 1) / 2 - width / 2) / max(1, width)
        foreground_height_ratio = fg_height / max(1, height)
        foreground_width_ratio = fg_width / max(1, width)
        metrics["composition"] = {
            "foregroundBox": {"x": x_min, "y": y_min, "width": fg_width, "height": fg_height},
            "topDistanceRatio": round(top_distance_ratio, 4),
            "horizontalCenterOffset": round(horizontal_center_offset, 4),
            "foregroundHeightRatio": round(foreground_height_ratio, 4),
            "foregroundWidthRatio": round(foreground_width_ratio, 4),
        }
        top_min = max(0.0, float(spec.get("top_distance_min", DEFAULT_TOP_DISTANCE_MIN)) - 0.035)
        top_max = min(0.35, float(spec.get("top_distance_max", DEFAULT_TOP_DISTANCE_MAX)) + 0.06)
        if top_distance_ratio < top_min or top_distance_ratio > top_max:
            warnings.append(_quality_issue("HEAD_TOP_DISTANCE_OUT_OF_RANGE", "头顶到照片顶部距离可能不在推荐范围内。", "warning", "composition.topDistanceRatio"))
            suggestions.append("可尝试调整 top_distance/top_distance_max 后重新生成。")
            score -= 10
        if abs(horizontal_center_offset) > 0.08:
            warnings.append(_quality_issue("SUBJECT_NOT_CENTERED", "人像水平居中偏差较大。", "warning", "composition.horizontalCenterOffset"))
            suggestions.append("建议使用更正面的原图，或开启人脸旋转对齐后重试。")
            score -= 8
        if foreground_height_ratio < 0.58 or foreground_height_ratio > 0.98:
            warnings.append(_quality_issue("HEAD_BODY_SCALE_CHECK", "人像占画面比例可能偏小或偏大。", "warning", "composition.foregroundHeightRatio"))
            suggestions.append("建议换一张清晰正面半身照，避免头肩过远或过近。")
            score -= 8
    else:
        metrics["composition"] = {"available": False}
        warnings.append(_quality_issue("COMPOSITION_METRIC_UNAVAILABLE", "无法从透明结果中提取人像轮廓，头部比例/居中指标已降级。", "warning", "composition"))
        suggestions.append("若预览看起来不居中，请换用边缘清晰、背景简单的原图。")
        score -= 6

    bg_pixels = _sample_background_pixels(official_rgb, getattr(result, "standard", None))
    if bg_pixels.size:
        mean_rgb = bg_pixels.astype(np.float32).mean(axis=0)
        target = np.array(background_rgb, dtype=np.float32)
        mean_delta = float(np.abs(mean_rgb - target).mean())
        max_delta = float(np.abs(mean_rgb - target).max())
        metrics["backgroundColor"] = {
            "targetRgb": [int(v) for v in background_rgb],
            "sampleMeanRgb": [round(float(v), 2) for v in mean_rgb],
            "meanDelta": round(mean_delta, 3),
            "maxChannelDelta": round(max_delta, 3),
        }
        if mean_delta > 18:
            warnings.append(_quality_issue("BACKGROUND_COLOR_DEVIATION", "背景色抽样与目标色存在明显偏差。", "warning", "backgroundColor.meanDelta"))
            suggestions.append("如使用自定义底色，请确认 HEX/RGB 输入正确；渐变模式下边缘抽样会自然接近白色。")
            score -= 8
    else:
        metrics["backgroundColor"] = {"available": False}
        warnings.append(_quality_issue("BACKGROUND_SAMPLE_UNAVAILABLE", "无法抽样背景色，背景合规指标已降级。", "warning", "backgroundColor"))
        score -= 4

    score = max(0, min(100, int(round(score))))
    passed = not errors and score >= 80
    if not suggestions and warnings:
        suggestions.append("请按提醒项检查预览；官方结果未被阻断，可下载后人工确认。")
    if not warnings and not errors:
        suggestions.append("当前结果通过自动预检；提交前仍建议按具体办事机构要求人工核对。")

    return {
        "score": score,
        "passed": passed,
        "metrics": metrics,
        "warnings": warnings,
        "errors": errors,
        "suggestions": suggestions,
    }


def add_task_warning(task: dict[str, Any], code: str, message: str) -> None:
    warning = {"code": code, "message": message}
    task.setdefault("warnings", []).append(warning)
    task["warning"] = warning


def make_ai_preview_from_official(official_image: np.ndarray, output_path: Path, dpi: int) -> None:
    # Local derived preview only: gentle brightness/contrast pass, no third-party AI call.
    preview = cv2.convertScaleAbs(official_image, alpha=1.02, beta=4)
    write_png(preview, output_path, dpi)



def normalize_ai_pro_request(ai_pro: Any) -> dict[str, Any]:
    requested_modes = [str(mode) for mode in (ai_pro.modes or []) if str(mode) in AI_PRO_SUPPORTED_MODES]
    if ai_pro.enabled and not requested_modes:
        requested_modes = ["ai_repair"]
    return {
        "enabled": bool(ai_pro.enabled),
        "modes": requested_modes,
        "promptParams": dict(ai_pro.promptParams or {}),
        "consentAccepted": bool(ai_pro.consentAccepted),
    }


def build_ai_pro_mock_results(task_id: str, free_result: dict[str, Any] | None, ai_pro: dict[str, Any], quality_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not ai_pro.get("enabled"):
        return []
    preview_url = (free_result or {}).get("previewUrl")
    results: list[dict[str, Any]] = []
    for mode in ai_pro.get("modes", []):
        template = PROMPT_TEMPLATE_REGISTRY[AI_PRO_MODE_TEMPLATE.get(mode, "ai_repair_basic")]
        metadata = dict(template.get("promptMetadata", {}))
        metadata["mockSource"] = "freeResult"
        metadata["selectedParams"] = ai_pro.get("promptParams", {})
        if mode == "ai_blue_formal_id_photo":
            metadata["specProfile"] = PROMPT_TEMPLATE_REGISTRY["cn_blue_480x640_20_40kb"]["promptMetadata"].get("specProfile")
            metadata["qualityRules"] = PROMPT_TEMPLATE_REGISTRY["cn_blue_480x640_20_40kb"]["promptMetadata"].get("qualityRules")
        results.append({
            "mode": mode,
            "status": "mock_completed",
            "imageUrl": preview_url,
            "previewUrl": preview_url,
            "usageLabel": template["usageLabel"],
            "promptTemplateId": template["id"],
            "templateVersion": template["version"],
            "paid": False,
            "qualityReport": {"source": "core_quality_report", "corePassed": bool((quality_report or {}).get("passed")), "mock": True},
            "promptMetadata": metadata,
            "mock": True,
        })
    return results

def run_idcreator_task(task_id: str) -> None:
    task = TASKS[task_id]
    task["status"] = "processing"
    task.setdefault("stages", {})["core"] = {"status": "processing"}
    persist_tasks()
    started = time.time()

    try:
        upload = UPLOADS.get(task["uploadId"])
        if not upload:
            raise FileNotFoundError("Upload handle was not found or has expired.")

        options = task.get("options", {})
        spec = normalize_template_options(task["templateId"], options)
        _, background_rgb = resolve_background_rgb(options)
        plugin_flags = normalize_plugin_flags(options)
        render_mode = normalize_render_mode(options.get("renderMode"))

        choose_handler(
            creator,
            task.get("options", {}).get("humanMattingModel", "hivision_modnet"),
            task.get("options", {}).get("faceDetectModel", "mtcnn"),
        )
        img = read_upload_image(upload["path"])
        result = creator(
            img,
            size=(spec["height"], spec["width"]),
            head_measure_ratio=spec["head_measure_ratio"],
            head_height_ratio=spec["head_height_ratio"],
            head_top_range=(spec["top_distance_max"], spec["top_distance_min"]),
            face_alignment=("faceAlign" in plugin_flags),
            whitening_strength=int(task.get("options", {}).get("whiteningStrength", 0)),
            brightness_strength=float(task.get("options", {}).get("brightnessStrength", 0)),
            contrast_strength=float(task.get("options", {}).get("contrastStrength", 0)),
            sharpen_strength=float(task.get("options", {}).get("sharpenStrength", 0)),
            saturation_strength=float(task.get("options", {}).get("saturationStrength", 0)),
            horizontal_flip=("horizontalFlip" in plugin_flags),
        )

        official_rgb = add_background(result.standard, bgr=background_rgb, mode=render_mode).astype(np.uint8)
        result_dir = RESULT_DIR / task_id
        jpeg_format = "jpegFormat" in plugin_flags
        official_name = "official_idcreator.jpg" if jpeg_format else "official_idcreator.png"
        if jpeg_format:
            write_jpeg(official_rgb, result_dir / official_name, spec["dpi"])
        else:
            write_png(official_rgb, result_dir / official_name, spec["dpi"])
        task["officialResult"] = build_result_file(task_id, "official", official_name)
        task["freeResult"] = task["officialResult"]
        task["qualityReport"] = build_quality_report(result, official_rgb, spec, background_rgb)
        task.setdefault("stages", {})["core"] = {"status": "completed", "engine": "IDCreator"}
        task.pop("warning", None)
        task.pop("warnings", None)

        if options.get("renderAiEnhancePreview"):
            try:
                ai_name = "ai_enhance_preview_derived.png"
                make_ai_preview_from_official(official_rgb, result_dir / ai_name, spec["dpi"])
                task["aiEnhanceResult"] = build_result_file(task_id, "ai", ai_name)
            except Exception as exc:
                logger.exception("[API] AI preview derivative failed: task_id=%s", task_id)
                add_task_warning(task, "AI_PREVIEW_FAILED", f"AI preview could not be generated: {exc}")

        if options.get("printLayoutEnabled"):
            try:
                layout_name = "layout_print.png"
                make_layout_from_official(
                    official_rgb,
                    {
                        **spec,
                        "layoutPaperSize": options.get("layoutPaperSize"),
                        "printLayoutSize": options.get("printLayoutSize"),
                        "layoutHeight": options.get("layoutHeight"),
                        "layoutWidth": options.get("layoutWidth"),
                    },
                    result_dir / layout_name,
                    spec["dpi"],
                    crop_line=("layoutCropLine" in plugin_flags),
                )
                task["layoutResult"] = build_result_file(task_id, "layout", layout_name)
            except Exception as exc:
                logger.exception("[API] print layout derivative failed: task_id=%s", task_id)
                add_task_warning(task, "LAYOUT_RESULT_FAILED", f"Print layout could not be generated: {exc}")

        if options.get("watermarkEnabled"):
            try:
                watermarked_name = "watermarked_official.png"
                make_watermarked_from_official(official_rgb, options, result_dir / watermarked_name, spec["dpi"])
                task["watermarkedResult"] = build_result_file(task_id, "watermarked", watermarked_name)
            except Exception as exc:
                logger.exception("[API] watermark derivative failed: task_id=%s", task_id)
                add_task_warning(task, "WATERMARK_RESULT_FAILED", f"Watermarked result could not be generated: {exc}")

        if options.get("imageKb") is not None:
            try:
                compressed_name = "official_compressed_kb.jpg"
                compressed_kb = make_compressed_from_official(official_rgb, options.get("imageKb"), result_dir / compressed_name, spec["dpi"], mode=str(options.get("imageKbMode") or "exact"))
                task["compressedResult"] = build_result_file(task_id, "compressed", compressed_name)
                task["compressedTargetKb"] = compressed_kb
            except Exception as exc:
                logger.exception("[API] target KB derivative failed: task_id=%s", task_id)
                add_task_warning(task, "COMPRESSED_RESULT_FAILED", f"Target KB result could not be generated: {exc}")

        ai_pro = task.get("aiPro") or {"enabled": False, "modes": [], "promptParams": {}, "consentAccepted": False}
        if ai_pro.get("enabled"):
            task["proResults"] = build_ai_pro_mock_results(task_id, task.get("freeResult"), ai_pro, task.get("qualityReport"))
            task.setdefault("stages", {})["aiPro"] = {"status": "mock_completed", "modes": ai_pro.get("modes", []), "paid": False}
        else:
            task["proResults"] = []
            task.setdefault("stages", {})["aiPro"] = {"status": "skipped"}

        task["status"] = "succeeded"
        task.pop("error", None)
    except FaceError as err:
        logger.exception("[API] IDCreator task failed: task_id=%s face_num=%s", task_id, getattr(err, "face_num", None))
        task.setdefault("stages", {})["core"] = {"status": "failed"}
        task.setdefault("stages", {})["core"] = {"status": "failed"}
        task["status"] = "failed"
        task["error"] = {
            "code": "FACE_DETECTION_FAILED",
            "message": "IDCreator could not detect exactly one valid face in the uploaded image.",
            "retryable": True,
            "traceId": task_id,
        }
    except Exception as exc:
        logger.exception("[API] IDCreator task failed: task_id=%s", task_id)
        task["status"] = "failed"
        task["error"] = {
            "code": "IDCREATOR_TASK_FAILED",
            "message": str(exc),
            "retryable": True,
            "traceId": task_id,
        }
    finally:
        persist_tasks()
        log_event(
            "task_complete",
            None,
            status="success" if task.get("status") == "succeeded" else "failure",
            task_id=task_id,
            upload_id=task.get("uploadId"),
            duration_ms=int((time.time() - started) * 1000),
            error_code=(task.get("error") or {}).get("code") if task.get("status") == "failed" else None,
            extra={"templateId": task.get("templateId"), "aiMode": task.get("aiMode")},
        )


def schedule_idcreator_task(background_tasks: BackgroundTasks, task_id: str) -> None:
    background_tasks.add_task(lambda: executor.submit(run_idcreator_task, task_id))


class ResultFile(BaseModel):
    fileId: str
    previewUrl: str
    downloadUrl: str
    expiresAt: str


class AiProRequest(BaseModel):
    enabled: bool = False
    modes: list[str] = Field(default_factory=list)
    promptParams: dict[str, Any] = Field(default_factory=dict)
    consentAccepted: bool = False


class AiProResult(BaseModel):
    mode: str
    status: str
    imageUrl: str | None = None
    previewUrl: str | None = None
    usageLabel: str
    promptTemplateId: str
    templateVersion: str
    paid: bool = False
    qualityReport: dict[str, Any] | None = None
    promptMetadata: dict[str, Any] = Field(default_factory=dict)
    mock: bool = True


class TaskCreateRequest(BaseModel):
    uploadId: str
    templateId: str
    platform: Platform = "web"
    aiMode: AiMode = "none"
    options: dict[str, Any] = Field(default_factory=dict)
    aiPro: AiProRequest = Field(default_factory=AiProRequest)


class LoginRequest(BaseModel):
    username: str
    password: str


class ProcessingTask(BaseModel):
    taskId: str
    status: TaskStatus
    uploadId: str
    templateId: str
    platform: Platform
    aiMode: AiMode
    options: dict[str, Any]
    officialResult: ResultFile | None = None
    aiEnhanceResult: ResultFile | None = None
    freeResult: ResultFile | None = None
    proResults: list[AiProResult] = Field(default_factory=list)
    stages: dict[str, Any] = Field(default_factory=dict)
    aiPro: AiProRequest | None = None
    layoutResult: ResultFile | None = None
    watermarkedResult: ResultFile | None = None
    compressedResult: ResultFile | None = None
    compressedTargetKb: int | None = None
    qualityReport: dict[str, Any] | None = None
    warning: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] | None = None
    error: dict[str, Any] | None = None


UPLOADS: dict[str, dict[str, Any]] = {}
TASKS: dict[str, dict[str, Any]] = {}
load_tasks()
if os.environ.get("IDPHOTO_SKIP_STARTUP_CLEANUP") != "1":
    cleanup_runtime()

# 添加 CORS 中间件 解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的请求来源
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=[
        "*"
    ],  # 允许的请求方法，例如：GET, POST 等，也可以指定 ["GET", "POST"]
    allow_headers=["*"],  # 允许的请求头，也可以指定具体的头部
)


@app.get("/api/health")
async def api_health():
    return {"status": "ok", "service": "hivisionidphotos-api", "phase": SERVICE_PHASE}


@app.post("/api/auth/login")
async def api_auth_login(payload: LoginRequest, response: Response, request: Request):
    check_rate_limit(request, "login", RATE_LIMIT_LOGIN_PER_MINUTE)
    started = time.time()
    if not auth_is_configured():
        log_event("login", request, status="failure", user=payload.username, duration_ms=int((time.time() - started) * 1000), error_code="AUTH_NOT_CONFIGURED")
        raise HTTPException(status_code=503, detail=error_detail("AUTH_NOT_CONFIGURED", "Application login is not configured.", retryable=False))
    if not (hmac.compare_digest(payload.username, APP_USERNAME) and hmac.compare_digest(payload.password, APP_PASSWORD)):
        log_event("login", request, status="failure", user=payload.username, duration_ms=int((time.time() - started) * 1000), error_code="INVALID_CREDENTIALS")
        raise HTTPException(status_code=401, detail=error_detail("INVALID_CREDENTIALS", "Username or password is incorrect.", retryable=False))
    set_session_cookie(response, APP_USERNAME)
    log_event("login", request, status="success", user=APP_USERNAME, duration_ms=int((time.time() - started) * 1000))
    return {"authenticated": True, "username": APP_USERNAME}


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    session = verify_session_token(request.cookies.get(APP_SESSION_COOKIE))
    return {"authenticated": bool(session), "username": APP_USERNAME if session else None}


@app.post("/api/auth/logout")
async def api_auth_logout(response: Response, request: Request):
    session = verify_session_token(request.cookies.get(APP_SESSION_COOKIE))
    log_event("logout", request, status="success", session=session)
    clear_session_cookie(response)
    return {"authenticated": False}


@app.get("/api/admin/stats")
async def api_admin_stats(_session: dict[str, Any] = Depends(require_auth)):
    return build_admin_stats()


@app.get("/api/templates")
async def api_templates(_session: dict[str, Any] = Depends(require_auth)):
    return [
        {
            "templateId": template_id,
            "label": spec["label"],
            "size": spec["size_mm"],
            "height": spec["height"],
            "width": spec["width"],
            "dpi": spec["dpi"],
            "common": spec.get("common", False),
            "headRange": "IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。",
            "printNote": spec.get("print_note", "官方结果由 Hivision IDCreator 渲染。"),
        }
        for template_id, spec in TEMPLATE_SPECS.items()
    ]


@app.get("/api/config")
async def api_config(_session: dict[str, Any] = Depends(require_auth)):
    return {
        "aiProTemplates": list(PROMPT_TEMPLATE_REGISTRY.values()),
        "consent": {
            "required": True,
            "title": "Photo processing consent",
            "body": "Your uploaded image is processed only for the selected ID photo task.",
        },
        "privacy": {
            "retentionHours": ttl_hours(),
            "deletionCopy": "Uploads and generated result files expire automatically after the configured TTL.",
        },
        "uploadLimits": {
            "maxBytes": MAX_UPLOAD_BYTES,
            "maxPixels": MAX_IMAGE_PIXELS,
            "allowedMimeTypes": sorted(ALLOWED_UPLOAD_TYPES.keys()),
            "allowedExtensions": sorted({ext for exts in ALLOWED_UPLOAD_TYPES.values() for ext in exts}),
        },
        "aiDisclaimer": "AI preview is optional, local-derived, and separate from official IDCreator output.",
        "copy": {"productName": "HivisionIDPhotos Studio", "uploadCta": "Select portrait"},
        "features": {"officialIdPhoto": True, "aiEnhancePreview": True, "wechatMiniappReady": True},
        "defaults": {"templateId": DEFAULT_TEMPLATE_ID, "background": DEFAULT_BACKGROUND},
        "supportedBackgrounds": [
            {"id": key, "label": BACKGROUND_LABELS[key]} for key in supported_backgrounds()
        ],
        "layoutPaperSizes": [
            {"id": key, "label": value["label"], "height": value["height"], "width": value["width"]}
            for key, value in LAYOUT_PAPER_SIZES.items()
        ],
    }


@app.post("/api/uploads")
async def api_create_upload(request: Request, file: UploadFile = File(...), _session: dict[str, Any] = Depends(require_auth)):
    check_rate_limit(request, "upload", RATE_LIMIT_UPLOADS_PER_MINUTE)
    started = time.time()
    upload_id: str | None = None
    try:
        cleanup_runtime()
        content_type = validate_upload_metadata(file.filename, file.content_type)
        content = await file.read()
        validate_upload_bytes(content, content_type)

        upload_id = f"upl_{uuid.uuid4().hex[:12]}"
        file_id = f"file_source_{uuid.uuid4().hex[:12]}"
        stored_name = f"{upload_id}{safe_suffix(file.filename, content_type)}"
        stored_path = UPLOAD_DIR / stored_name

        stored_path.write_bytes(content)

        expires_at = utc_expires_at_seconds(RUNTIME_TTL_SECONDS)
        UPLOADS[upload_id] = {
            "uploadId": upload_id,
            "fileId": file_id,
            "filename": file.filename or stored_name,
            "storedName": stored_name,
            "mimeType": content_type,
            "path": str(stored_path),
            "url": public_runtime_url("uploads", stored_name),
            "expiresAt": expires_at,
            "createdAt": time.time(),
        }

        log_event("upload", request, status="success", session=_session, upload_id=upload_id, duration_ms=int((time.time() - started) * 1000), extra={"mimeType": content_type, "bytes": len(content)})
        return {
            "uploadId": upload_id,
            "fileId": file_id,
            "filename": file.filename or stored_name,
            "mimeType": content_type,
            "url": public_runtime_url("uploads", stored_name),
            "expiresAt": expires_at,
        }
    except HTTPException as exc:
        log_event("upload", request, status="failure", session=_session, upload_id=upload_id, duration_ms=int((time.time() - started) * 1000), error_code=safe_error_code(exc))
        raise
    except Exception as exc:
        log_event("upload", request, status="failure", session=_session, upload_id=upload_id, duration_ms=int((time.time() - started) * 1000), error_code=exc.__class__.__name__)
        raise


@app.post("/api/tasks")
async def api_create_task(request: Request, payload: TaskCreateRequest, background_tasks: BackgroundTasks, _session: dict[str, Any] = Depends(require_auth)):
    check_rate_limit(request, "task", RATE_LIMIT_TASKS_PER_MINUTE)
    started = time.time()
    task_id: str | None = None
    try:
        cleanup_runtime()
        if payload.uploadId not in UPLOADS:
            raise HTTPException(status_code=404, detail=error_detail("UPLOAD_NOT_FOUND", "Upload handle was not found or has expired.", retryable=True))

        template_id = validate_template_id(payload.templateId)
        task_options = dict(payload.options)
        ai_pro = normalize_ai_pro_request(payload.aiPro)
        if ai_pro["enabled"] and not ai_pro["consentAccepted"]:
            raise HTTPException(status_code=400, detail=error_detail("AI_PRO_CONSENT_REQUIRED", "AI Pro requires explicit consent before mock generation.", retryable=False))
        background, background_rgb = resolve_background_rgb(task_options)
        normalize_render_mode(task_options.get("renderMode"))
        plugin_flags = normalize_plugin_flags(task_options)
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        render_ai = bool(payload.options.get("renderAiEnhancePreview", False)) or payload.aiMode in {"preview", "enhance"}
        if "fiveInchPaper" in plugin_flags and not task_options.get("layoutPaperSize") and not task_options.get("printLayoutSize"):
            task_options["layoutPaperSize"] = "five-inch"
            task_options["printLayoutSize"] = "five-inch"
        if task_options.get("printLayoutEnabled"):
            task_options["layoutPaperSize"] = validate_layout_paper_size(task_options.get("layoutPaperSize") or task_options.get("printLayoutSize"))
            task_options["printLayoutSize"] = task_options["layoutPaperSize"]
        if task_options.get("imageKb") is not None:
            task_options["imageKbMode"] = normalize_image_kb_mode(task_options.get("imageKbMode"))
        task_options.update({
            "background": background,
            "backgroundRgb": list(background_rgb),
            "renderMode": task_options.get("renderMode") or "solid",
            "pluginFlags": sorted(plugin_flags),
            "faceAlign": "faceAlign" in plugin_flags,
            "horizontalFlip": "horizontalFlip" in plugin_flags,
            "layoutCropLine": "layoutCropLine" in plugin_flags,
            "jpegFormat": "jpegFormat" in plugin_flags,
            "renderOfficialIdPhoto": True,
            "renderAiEnhancePreview": render_ai,
            "aiEnhancePreviewKind": "local-derived-preview" if render_ai else "none",
        })
        task = {
            "taskId": task_id,
            "status": "queued",
            "uploadId": payload.uploadId,
            "templateId": template_id,
            "platform": payload.platform,
            "aiMode": payload.aiMode,
            "options": task_options,
            "aiPro": ai_pro,
            "freeResult": None,
            "proResults": [],
            "stages": {"core": {"status": "queued"}, "aiPro": {"status": "queued" if ai_pro["enabled"] else "skipped"}},
            "createdAt": time.time(),
        }
        TASKS[task_id] = task
        persist_tasks()
        log_event("task_create", request, status="success", session=_session, task_id=task_id, upload_id=payload.uploadId, duration_ms=int((time.time() - started) * 1000), extra={"templateId": template_id, "aiMode": payload.aiMode})
        schedule_idcreator_task(background_tasks, task_id)
        return ProcessingTask(**{key: value for key, value in task.items() if key != "createdAt"})
    except HTTPException as exc:
        log_event("task_create", request, status="failure", session=_session, task_id=task_id, upload_id=payload.uploadId, duration_ms=int((time.time() - started) * 1000), error_code=safe_error_code(exc))
        raise
    except Exception as exc:
        log_event("task_create", request, status="failure", session=_session, task_id=task_id, upload_id=payload.uploadId, duration_ms=int((time.time() - started) * 1000), error_code=exc.__class__.__name__)
        raise


@app.get("/api/downloads/{token}")
async def api_download_result(request: Request, token: str, _session: dict[str, Any] = Depends(require_auth)):
    started = time.time()
    task_id: str | None = None
    try:
        cleanup_runtime()
        payload = verify_download_token(token)
        relative_path = str(payload["path"])
        task_id = relative_path.split("/", 1)[0] if "/" in relative_path else None
        path = resolve_result_file(relative_path)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        headers = {"Cache-Control": "private, no-store"}
        log_event("download", request, status="success", session=_session, route="/api/downloads/{token}", task_id=task_id, duration_ms=int((time.time() - started) * 1000), extra={"purpose": payload.get("purpose"), "bytes": path.stat().st_size})
        return FileResponse(path, media_type=media_type, filename=path.name if payload.get("purpose") == "download" else None, headers=headers)
    except HTTPException as exc:
        log_event("download", request, status="failure", session=_session, route="/api/downloads/{token}", task_id=task_id, duration_ms=int((time.time() - started) * 1000), error_code=safe_error_code(exc))
        raise
    except Exception as exc:
        log_event("download", request, status="failure", session=_session, route="/api/downloads/{token}", task_id=task_id, duration_ms=int((time.time() - started) * 1000), error_code=exc.__class__.__name__)
        raise


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str, _session: dict[str, Any] = Depends(require_auth)):
    cleanup_runtime()
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=error_detail("TASK_NOT_FOUND", "Task was not found or has expired.", retryable=True))

    return ProcessingTask(**{key: value for key, value in task.items() if key not in {"createdAt", "future"}})


# 证件照智能制作接口
@app.post("/idphoto")
async def idphoto_inference(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    height: int = Form(413),
    width: int = Form(295),
    human_matting_model: str = Form("hivision_modnet"),
    face_detect_model: str = Form("mtcnn"),
    hd: bool = Form(True),
    dpi: int = Form(300),
    face_align: bool = Form(False),
    whitening_strength: int = Form(0),
    head_measure_ratio: float = Form(0.2),
    head_height_ratio: float = Form(0.45),
    top_distance_max: float = Form(0.12),
    top_distance_min: float = Form(0.10),
    brightness_strength: float = Form(0),
    contrast_strength: float = Form(0),
    sharpen_strength: float = Form(0),
    saturation_strength: float = Form(0),
):  
    # 如果传入了base64，则直接使用base64解码
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    # 否则使用上传的图片
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # 将BGR转换为RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, human_matting_model, face_detect_model)

    # 将字符串转为元组
    size = (int(height), int(width))
    try:
        result = creator(
            img,
            size=size,
            head_measure_ratio=head_measure_ratio,
            head_height_ratio=head_height_ratio,
            head_top_range=(top_distance_max, top_distance_min),
            face_alignment=face_align,
            whitening_strength=whitening_strength,
            brightness_strength=brightness_strength,
            contrast_strength=contrast_strength,
            sharpen_strength=sharpen_strength,
            saturation_strength=saturation_strength,
        )
    except FaceError as err:
        logger.exception(
            "[API] idphoto failed: face_num=%s matting_model=%s face_detect_model=%s input_shape=%s size=%s",
            getattr(err, "face_num", None),
            human_matting_model,
            face_detect_model,
            getattr(img, "shape", None),
            size,
        )
        result_message = {"status": False, "face_num": getattr(err, "face_num", None)}
    # 如果检测到人脸数量等于1, 则返回标准证和高清照结果（png 4通道图像）
    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(result.standard, None, dpi)
        
        result_message = {
            "status": True,
            "image_base64_standard": bytes_2_base64(result_image_standard_bytes),
        }

        # 如果hd为True, 则增加高清照结果（png 4通道图像）
        if hd:
            result_image_hd_bytes = save_image_dpi_to_bytes(result.hd, None, dpi)
            result_message["image_base64_hd"] = bytes_2_base64(result_image_hd_bytes)

    return result_message


# 人像抠图接口
@app.post("/human_matting")
async def human_matting_inference(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    human_matting_model: str = Form("hivision_modnet"),
    dpi: int = Form(300),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, human_matting_model, None)

    try:
        result = creator(
            img,
            change_bg_only=True,
        )
    except FaceError:
        result_message = {"status": False}

    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.standard, cv2.COLOR_RGBA2BGRA), None, dpi)
        result_message = {
            "status": True,
            "image_base64": bytes_2_base64(result_image_standard_bytes),
        }
    return result_message


# AI 图像增强接口（独立于 /idphoto 主链路）
@app.post("/ai_enhance")
async def ai_enhance(
    input_image_base64: str = Form(...),
    mode: str = Form(...),
    provider: str = Form("gpt-image-2"),
    consent: bool = Form(False),
    prompt: str = Form(None),
    template_name: str = Form(None),
    return_base64: bool = Form(True),
    client_id: str = Form(None),
):
    try:
        request = AIEnhanceRequest(
            input_image_base64=input_image_base64,
            mode=mode,
            provider=provider,
            consent=consent,
            prompt=prompt,
            template_name=template_name,
            return_base64=return_base64,
            client_id=client_id,
        )
        return ai_enhance_service.enhance(request).to_dict()
    except AIEnhanceValidationError as exc:
        return {
            "status": False,
            "image_base64": None,
            "metadata": {
                "fallback_used": True,
                "fallback_reason": "validation_error",
                "error_code": exc.error_code,
                "latency_ms": 0,
                "provider": provider,
                "mode": mode,
                "ai_generated": False,
                "validation_passed": False,
                "validation_warnings": [],
                "debug_input_path": None,
                "debug_output_path": None,
                "debug_metadata_path": None,
                "request_id": None,
                "estimated_cost": None,
                "rate_limited": False,
                "usage_logged": False,
            },
            "message": exc.message,
        }


# 透明图像添加纯色背景接口
@app.post("/add_background")
async def photo_add_background(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    color: str = Form("000000"),
    kb: int = Form(None),
    dpi: int = Form(300),
    render: int = Form(0),
):
    render_choice = ["pure_color", "updown_gradient", "center_gradient"]

    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)

    color = hex_to_rgb(color)
    color = (color[2], color[1], color[0])

    result_image = add_background(
        img,
        bgr=color,
        mode=render_choice[render],
    ).astype(np.uint8)

    result_image = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
    if kb:
        result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
    else:
        result_image_bytes = save_image_dpi_to_bytes(result_image, None, dpi=dpi)

    result_messgae = {
        "status": True,
        "image_base64": bytes_2_base64(result_image_bytes),
    }

    return result_messgae


# 六寸排版照生成接口
@app.post("/generate_layout_photos")
async def generate_layout_photos(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    height: int = Form(413),
    width: int = Form(295),
    kb: int = Form(None),
    dpi: int = Form(300),
):
    # try:
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    size = (int(height), int(width))

    typography_arr, typography_rotate = generate_layout_array(
        input_height=size[0], input_width=size[1]
    )

    result_layout_image = generate_layout_image(
        img, typography_arr, typography_rotate, height=size[0], width=size[1]
    ).astype(np.uint8)

    result_layout_image = cv2.cvtColor(result_layout_image, cv2.COLOR_RGB2BGR)
    if kb:
        result_layout_image_bytes = resize_image_to_kb(
            result_layout_image, None, int(kb), dpi=dpi
        )
    else:
        result_layout_image_bytes = save_image_dpi_to_bytes(result_layout_image, None, dpi=dpi)
        
    result_layout_image_base64 = bytes_2_base64(result_layout_image_bytes)

    result_messgae = {
        "status": True,
        "image_base64": result_layout_image_base64,
    }

    return result_messgae


# 透明图像添加水印接口
@app.post("/watermark")
async def watermark(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    text: str = Form("Hello"),
    size: int = 20,
    opacity: float = 0.5,
    angle: int = 30,
    color: str = "#000000",
    space: int = 25,
    kb: int = Form(None),
    dpi: int = Form(300),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    try:
        result_image = add_watermark(img, text, size, opacity, angle, color, space)

        result_image = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        if kb:
            result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
        else:
            result_image_bytes = save_image_dpi_to_bytes(result_image, None, dpi=dpi)
        result_image_base64 = bytes_2_base64(result_image_bytes)

        result_messgae = {
            "status": True,
            "image_base64": result_image_base64,
        }
    except Exception as e:
        result_messgae = {
            "status": False,
            "error": str(e),
        }

    return result_messgae


# 设置照片KB值接口(RGB图)
@app.post("/set_kb")
async def set_kb(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    dpi: int = Form(300),
    kb: int = Form(50),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    try:
        result_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
        result_image_base64 = bytes_2_base64(result_image_bytes)

        result_messgae = {
            "status": True,
            "image_base64": result_image_base64,
        }
    except Exception as e:
        result_messgae = {
            "status": False,
            "error": e,
        }

    return result_messgae


# 证件照智能裁剪接口
@app.post("/idphoto_crop")
async def idphoto_crop_inference(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    height: int = Form(413),
    width: int = Form(295),
    face_detect_model: str = Form("mtcnn"),
    hd: bool = Form(True),
    dpi: int = Form(300),
    head_measure_ratio: float = Form(0.2),
    head_height_ratio: float = Form(0.45),
    top_distance_max: float = Form(0.12),
    top_distance_min: float = Form(0.10),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)  # 读取图像(4通道)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, face_detect_option=face_detect_model)

    # 将字符串转为元组
    size = (int(height), int(width))
    try:
        result = creator(
            img,
            size=size,
            head_measure_ratio=head_measure_ratio,
            head_height_ratio=head_height_ratio,
            head_top_range=(top_distance_max, top_distance_min),
            crop_only=True,
        )
    except FaceError:
        result_message = {"status": False}
    # 如果检测到人脸数量等于1, 则返回标准证和高清照结果（png 4通道图像）
    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.standard, cv2.COLOR_RGBA2BGRA), None, dpi)
        
        result_message = {
            "status": True,
            "image_base64_standard": bytes_2_base64(result_image_standard_bytes),
        }

        # 如果hd为True, 则增加高清照结果（png 4通道图像）
        if hd:
            result_image_hd_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.hd, cv2.COLOR_RGBA2BGRA), None, dpi)
            result_message["image_base64_hd"] = bytes_2_base64(result_image_hd_bytes)

    return result_message


if __name__ == "__main__":
    import uvicorn

    # 在8080端口运行推理服务
    uvicorn.run(app, host="0.0.0.0", port=8080)
