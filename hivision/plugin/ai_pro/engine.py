from __future__ import annotations

import base64
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

_PROVIDER_SIZES: tuple[tuple[str, float], ...] = (
    ("1024x1536", 1024 / 1536),
    ("1536x1024", 1536 / 1024),
    ("1024x1024", 1.0),
)


def _normalize_image_size(value: str | None) -> str:
    size = (value or "").strip().lower()
    if not size:
        return ""
    if size == "auto":
        return "auto"
    if "x" in size:
        width, height = size.split("x", 1)
        if width.isdigit() and height.isdigit() and int(width) > 0 and int(height) > 0:
            return f"{int(width)}x{int(height)}"
    return "auto"


def _normalize_image_size_policy(value: str | None) -> str:
    policy = (value or "auto").strip().lower()
    return policy if policy in {"auto", "match-aspect"} else "auto"


def _match_aspect_size(target_spec: dict[str, Any] | None) -> str | None:
    if not target_spec:
        return None
    try:
        width = float(target_spec.get("width") or 0)
        height = float(target_spec.get("height") or 0)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    target_ratio = width / height
    return min(_PROVIDER_SIZES, key=lambda item: abs(item[1] - target_ratio))[0]


def _provider_aspect_ratio(size: str) -> float | None:
    normalized = _normalize_image_size(size)
    if not normalized or normalized == "auto" or "x" not in normalized:
        return None
    width, height = normalized.split("x", 1)
    return round(int(width) / int(height), 6) if int(height) else None


@dataclass(frozen=True)
class AIProEngineConfig:
    provider: str = "mock"
    api_base: str = ""
    api_key: str = ""
    model: str = "gpt-image-2"
    timeout_seconds: float = 45.0
    retry_count: int = 0
    image_size: str = "auto"
    image_size_policy: str = "auto"

    @classmethod
    def from_env(cls) -> "AIProEngineConfig":
        provider = os.getenv("AI_PRO_PROVIDER") or os.getenv("GPT_IMAGE_PROVIDER") or "mock"
        api_key = os.getenv("GPT_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        api_base = os.getenv("GPT_IMAGE_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model = os.getenv("GPT_IMAGE_MODEL") or os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-2"
        timeout = float(os.getenv("AI_PRO_TIMEOUT_SECONDS") or os.getenv("GPT_IMAGE_TIMEOUT") or os.getenv("OPENAI_IMAGE_TIMEOUT") or "45")
        retry = max(0, min(1, int(os.getenv("AI_PRO_RETRY_COUNT") or "0")))
        image_size = _normalize_image_size(os.getenv("GPT_IMAGE_SIZE") or "auto")
        image_size_policy = _normalize_image_size_policy(os.getenv("GPT_IMAGE_SIZE_POLICY") or "auto")
        if not api_key:
            provider = "mock"
        return cls(provider=provider, api_base=api_base, api_key=api_key, model=model, timeout_seconds=timeout, retry_count=retry, image_size=image_size, image_size_policy=image_size_policy)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.provider != "mock")


@dataclass
class AIProEngineResult:
    status: str
    image_path: Path | None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIProEngine:
    """Minimal AI Pro provider adapter.

    Secrets are read only from environment and never exposed in metadata.
    The concrete provider payload is intentionally OpenAI-compatible but configurable;
    if credentials are absent or a provider call fails, callers can keep the free core result.
    """

    def __init__(self, config: AIProEngineConfig | None = None):
        self.config = config or AIProEngineConfig.from_env()

    def run_blue_formal_id_photo(self, *, input_path: Path, output_dir: Path, final_prompt: str, template_id: str, template_version: str, provider_size: str | None = None, target_spec: dict[str, Any] | None = None) -> AIProEngineResult:
        return self.run_image_edit(
            input_path=input_path,
            output_dir=output_dir,
            final_prompt=final_prompt,
            template_id=template_id,
            template_version=template_version,
            mode="ai_blue_formal_id_photo",
            output_filename="ai_blue_formal_id_photo.png",
            provider_size=provider_size,
            target_spec=target_spec,
        )

    def run_social_photo(self, *, input_path: Path, output_dir: Path, final_prompt: str, template_id: str, template_version: str, provider_size: str | None = None, target_spec: dict[str, Any] | None = None) -> AIProEngineResult:
        return self.run_image_edit(
            input_path=input_path,
            output_dir=output_dir,
            final_prompt=final_prompt,
            template_id=template_id,
            template_version=template_version,
            mode="social_photo",
            output_filename=f"social_photo_{template_id}.png",
            provider_size=provider_size,
            target_spec=target_spec or {"width": 1024, "height": 1024, "dpi": 300},
        )

    def run_image_edit(self, *, input_path: Path, output_dir: Path, final_prompt: str, template_id: str, template_version: str, mode: str, output_filename: str, provider_size: str | None = None, target_spec: dict[str, Any] | None = None) -> AIProEngineResult:
        started = time.time()
        prompt_hash = hashlib.sha256(final_prompt.encode("utf-8")).hexdigest()[:16]
        resolved_provider_size = self.resolve_provider_size(provider_size=provider_size, target_spec=target_spec, mode=mode)
        base_metadata: dict[str, Any] = {
            "mode": mode,
            "provider": self.config.provider if self.config.configured else "mock",
            "providerStatus": "configured" if self.config.configured else "no_credentials",
            "model": self.config.model,
            "templateId": template_id,
            "templateVersion": template_version,
            "inputSource": "freeResult",
            "mock": not self.config.configured,
            "fallback": not self.config.configured,
            "finalPromptHash": prompt_hash,
            "providerSizePolicy": self.config.image_size_policy,
            "providerSizeRequested": resolved_provider_size,
            "providerAspectRatioRequested": _provider_aspect_ratio(resolved_provider_size),
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        if not self.config.configured:
            base_metadata.update({"errorCode": "NO_CREDENTIALS", "durationMs": int((time.time() - started) * 1000)})
            return AIProEngineResult(status="no_credentials", image_path=None, metadata=base_metadata)

        last_error: str | None = None
        for attempt in range(self.config.retry_count + 1):
            try:
                image_b64 = self._call_provider(input_path=input_path, prompt=final_prompt, provider_size=resolved_provider_size)
                output_path = output_dir / output_filename
                output_path.write_bytes(base64.b64decode(self._strip_data_url(image_b64)))
                output_dimensions = self._image_dimensions(output_path)
                if output_dimensions:
                    width, height = output_dimensions
                    base_metadata.update({
                        "providerSizeUsed": [width, height],
                        "providerOutputSize": [width, height],
                        "providerAspectRatio": round(width / height, 6) if height else None,
                    })
                base_metadata.update({"mock": False, "fallback": False, "durationMs": int((time.time() - started) * 1000)})
                return AIProEngineResult(status="completed", image_path=output_path, metadata=base_metadata)
            except requests.Timeout:
                last_error = "PROVIDER_TIMEOUT"
            except requests.RequestException:
                last_error = "PROVIDER_HTTP_ERROR"
            except Exception:
                last_error = "PROVIDER_RESPONSE_ERROR"
            if attempt < self.config.retry_count:
                time.sleep(0.5)

        base_metadata.update({"providerStatus": "error", "fallback": True, "errorCode": last_error or "PROVIDER_ERROR", "durationMs": int((time.time() - started) * 1000)})
        return AIProEngineResult(status="fallback", image_path=None, metadata=base_metadata)

    def resolve_provider_size(self, *, provider_size: str | None = None, target_spec: dict[str, Any] | None = None, mode: str | None = None) -> str:
        explicit_size = _normalize_image_size(provider_size or "")
        if explicit_size:
            return explicit_size
        if self.config.image_size and self.config.image_size != "auto":
            return self.config.image_size
        # social_photo has a product-level 1:1 output contract; even with the
        # global provider-size policy left at safe default "auto", request the
        # nearest square provider size. Keep ID-photo default unchanged.
        if mode == "social_photo":
            return _match_aspect_size(target_spec or {"width": 1024, "height": 1024}) or "1024x1024"
        if self.config.image_size_policy == "match-aspect":
            return _match_aspect_size(target_spec) or "auto"
        return "auto"

    def _call_provider(self, *, input_path: Path, prompt: str, provider_size: str) -> str:
        with input_path.open("rb") as image_file:
            response = requests.post(
                f"{self.config.api_base.rstrip('/')}/images/edits",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                data={
                    "model": self.config.model,
                    "prompt": prompt,
                    "size": provider_size,
                    "response_format": "b64_json",
                },
                files={"image": (input_path.name, image_file, self._mime_type(input_path))},
                timeout=self.config.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        for item in data.get("data") or []:
            if isinstance(item, dict):
                if item.get("b64_json"):
                    return str(item["b64_json"])
                if item.get("image_base64"):
                    return str(item["image_base64"])
                if item.get("url"):
                    return self._download_image_b64(str(item["url"]))
        raise ValueError("provider response did not include image data")

    def _download_image_b64(self, url: str) -> str:
        response = requests.get(url, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")

    @staticmethod
    def _image_dimensions(path: Path) -> tuple[int, int] | None:
        try:
            with Image.open(path) as image:
                return int(image.width), int(image.height)
        except (OSError, UnidentifiedImageError):
            return None

    @staticmethod
    def _mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"

    @staticmethod
    def _to_data_url(path: Path) -> str:
        suffix = path.suffix.lower()
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

    @staticmethod
    def _strip_data_url(value: str) -> str:
        return value.split(",", 1)[1] if value.startswith("data:image") and "," in value else value
