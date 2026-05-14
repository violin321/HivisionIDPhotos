from concurrent.futures import ThreadPoolExecutor
import json
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, BackgroundTasks
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

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

# 设置Starlette表单字段大小限制
MultiPartParser.max_part_size = 10 * 1024 * 1024  # 10MB
# 设置Starlette文件上传大小限制
MultiPartParser.max_file_size = 20 * 1024 * 1024   # 20MB

logger = logging.getLogger(__name__)

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


def public_runtime_url(kind: Literal["uploads", "results"], filename: str) -> str:
    return f"/runtime/{kind}/{filename}"


def safe_suffix(filename: str | None, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"


TEMPLATE_SPECS: dict[str, dict[str, Any]] = {
    "cn-id-1inch": {"height": 413, "width": 295, "head_measure_ratio": 0.2, "head_height_ratio": 0.45},
    "cn-id-2inch": {"height": 579, "width": 413, "head_measure_ratio": 0.2, "head_height_ratio": 0.45},
    "passport-visa": {"height": 567, "width": 390, "head_measure_ratio": 0.2, "head_height_ratio": 0.45},
}

BACKGROUND_BGR: dict[str, tuple[int, int, int]] = {
    "white": (255, 255, 255),
    "blue": (255, 120, 67),
    "red": (49, 49, 209),
    "gray": (238, 238, 238),
}

TASKS_FILE = RUNTIME_DIR / "tasks.json"
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="idcreator-task")


def task_public_result(task_id: str, filename: str) -> str:
    return public_runtime_url("results", f"{task_id}/{filename}")


def build_result_file(task_id: str, lane: Literal["official", "ai"], filename: str) -> dict[str, str]:
    url = task_public_result(task_id, filename)
    return {
        "fileId": f"file_result_{lane}_{task_id[-6:]}",
        "previewUrl": url,
        "downloadUrl": url,
        "expiresAt": utc_expires_at(90),
    }


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


def normalize_template_options(template_id: str, options: dict[str, Any]) -> dict[str, Any]:
    spec = dict(TEMPLATE_SPECS.get(template_id, TEMPLATE_SPECS["cn-id-1inch"]))
    user_spec = options.get("spec") if isinstance(options.get("spec"), dict) else {}
    for source in (options, user_spec):
        for key in ("height", "width", "dpi", "head_measure_ratio", "head_height_ratio", "top_distance_max", "top_distance_min"):
            if key in source and source[key] is not None:
                spec[key] = source[key]
    spec["height"] = int(spec.get("height", 413))
    spec["width"] = int(spec.get("width", 295))
    spec["dpi"] = int(spec.get("dpi", 300))
    spec["head_measure_ratio"] = float(spec.get("head_measure_ratio", 0.2))
    spec["head_height_ratio"] = float(spec.get("head_height_ratio", 0.45))
    spec["top_distance_max"] = float(spec.get("top_distance_max", 0.12))
    spec["top_distance_min"] = float(spec.get("top_distance_min", 0.10))
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


def make_ai_preview_from_official(official_image: np.ndarray, output_path: Path, dpi: int) -> None:
    # Local derived preview only: gentle brightness/contrast pass, no third-party AI call.
    preview = cv2.convertScaleAbs(official_image, alpha=1.02, beta=4)
    write_png(preview, output_path, dpi)


def run_idcreator_task(task_id: str) -> None:
    task = TASKS[task_id]
    task["status"] = "processing"
    persist_tasks()

    try:
        upload = UPLOADS.get(task["uploadId"])
        if not upload:
            raise FileNotFoundError("Upload handle was not found or has expired.")

        spec = normalize_template_options(task["templateId"], task.get("options", {}))
        background_key = str(task.get("options", {}).get("background", "white"))
        background_bgr = BACKGROUND_BGR.get(background_key, BACKGROUND_BGR["white"])

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
            face_alignment=bool(task.get("options", {}).get("faceAlign", False)),
            whitening_strength=int(task.get("options", {}).get("whiteningStrength", 0)),
            brightness_strength=float(task.get("options", {}).get("brightnessStrength", 0)),
            contrast_strength=float(task.get("options", {}).get("contrastStrength", 0)),
            sharpen_strength=float(task.get("options", {}).get("sharpenStrength", 0)),
            saturation_strength=float(task.get("options", {}).get("saturationStrength", 0)),
        )

        official_rgb = add_background(result.standard, bgr=background_bgr, mode="pure_color").astype(np.uint8)
        result_dir = RESULT_DIR / task_id
        official_name = "official_idcreator.png"
        write_png(official_rgb, result_dir / official_name, spec["dpi"])
        task["officialResult"] = build_result_file(task_id, "official", official_name)

        if task.get("options", {}).get("renderAiEnhancePreview"):
            ai_name = "ai_enhance_preview_derived.png"
            make_ai_preview_from_official(official_rgb, result_dir / ai_name, spec["dpi"])
            task["aiEnhanceResult"] = build_result_file(task_id, "ai", ai_name)

        task["status"] = "succeeded"
        task.pop("error", None)
    except FaceError as err:
        logger.exception("[API] IDCreator task failed: task_id=%s face_num=%s", task_id, getattr(err, "face_num", None))
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


def schedule_idcreator_task(background_tasks: BackgroundTasks, task_id: str) -> None:
    background_tasks.add_task(lambda: executor.submit(run_idcreator_task, task_id))


class ResultFile(BaseModel):
    fileId: str
    previewUrl: str
    downloadUrl: str
    expiresAt: str


class TaskCreateRequest(BaseModel):
    uploadId: str
    templateId: str
    platform: Platform = "web"
    aiMode: AiMode = "none"
    options: dict[str, Any] = Field(default_factory=dict)


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
    error: dict[str, Any] | None = None


UPLOADS: dict[str, dict[str, Any]] = {}
TASKS: dict[str, dict[str, Any]] = {}
load_tasks()

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
    return {"status": "ok", "service": "hivisionidphotos-api", "phase": "3"}


@app.post("/api/uploads")
async def api_create_upload(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_FILE_TYPE", "message": "Only image uploads are supported.", "retryable": True}})

    upload_id = f"upl_{uuid.uuid4().hex[:12]}"
    file_id = f"file_source_{uuid.uuid4().hex[:12]}"
    stored_name = f"{upload_id}{safe_suffix(file.filename, file.content_type)}"
    stored_path = UPLOAD_DIR / stored_name

    with stored_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    expires_at = utc_expires_at(24 * 60)
    UPLOADS[upload_id] = {
        "uploadId": upload_id,
        "fileId": file_id,
        "filename": file.filename or stored_name,
        "storedName": stored_name,
        "mimeType": file.content_type,
        "path": str(stored_path),
        "url": public_runtime_url("uploads", stored_name),
        "expiresAt": expires_at,
        "createdAt": time.time(),
    }

    return {
        "uploadId": upload_id,
        "fileId": file_id,
        "filename": file.filename or stored_name,
        "mimeType": file.content_type,
        "url": public_runtime_url("uploads", stored_name),
        "expiresAt": expires_at,
    }


@app.post("/api/tasks")
async def api_create_task(payload: TaskCreateRequest, background_tasks: BackgroundTasks):
    if payload.uploadId not in UPLOADS:
        raise HTTPException(status_code=404, detail={"error": {"code": "UPLOAD_NOT_FOUND", "message": "Upload handle was not found or has expired.", "retryable": True}})

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    background = payload.options.get("background", "white")
    render_ai = bool(payload.options.get("renderAiEnhancePreview", False)) or payload.aiMode in {"preview", "enhance"}
    task_options = dict(payload.options)
    task_options.update({
        "background": background,
        "renderOfficialIdPhoto": True,
        "renderAiEnhancePreview": render_ai,
        "aiEnhancePreviewKind": "local-derived-preview" if render_ai else "none",
    })
    task = {
        "taskId": task_id,
        "status": "queued",
        "uploadId": payload.uploadId,
        "templateId": payload.templateId,
        "platform": payload.platform,
        "aiMode": payload.aiMode,
        "options": task_options,
        "createdAt": time.time(),
    }
    TASKS[task_id] = task
    persist_tasks()
    schedule_idcreator_task(background_tasks, task_id)
    return ProcessingTask(**{key: value for key, value in task.items() if key != "createdAt"})


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": {"code": "TASK_NOT_FOUND", "message": "Task was not found or has expired.", "retryable": True}})

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
