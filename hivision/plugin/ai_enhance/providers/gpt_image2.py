from __future__ import annotations

import os
from typing import Optional

import requests

from ..errors import AIEnhanceConfigError, AIEnhanceProviderError
from ..prompt_templates import render_prompt_template
from ..schemas import AIEnhanceOutput, AIEnhanceRequest
from .base import BaseAIEnhanceProvider

_DEFAULT_TIMEOUT = float(os.getenv("OPENAI_IMAGE_TIMEOUT", "30"))


class GPTImage2Provider(BaseAIEnhanceProvider):
    provider_name = "gpt-image-2"

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
        self.timeout = float(os.getenv("OPENAI_IMAGE_TIMEOUT", str(_DEFAULT_TIMEOUT)))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        if not self.is_configured():
            raise AIEnhanceConfigError()

        payload = {
            "model": self.model,
            "images": [
                {
                    "image_url": request.input_image_base64,
                }
            ],
            "prompt": self._build_prompt(request),
            "size": "1024x1024",
            "response_format": "b64_json",
        }
        if request.mask_base64:
            payload["mask"] = request.mask_base64
        if request.edit_region:
            payload["metadata"] = {
                "edit_region": request.edit_region,
                "mask_edit": bool(request.mask_base64),
                "crop_edit": request.edit_region.get("strategy") in {"crop_composite", "masked_crop_composite"},
                "face_protected": True,
            }

        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/images/edits",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise AIEnhanceProviderError("AI provider request timed out", error_code="PROVIDER_TIMEOUT") from exc
        except requests.RequestException as exc:
            raise AIEnhanceProviderError(f"AI provider request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._extract_error(response.text)
            raise AIEnhanceProviderError(
                f"AI provider returned HTTP {response.status_code}: {detail}",
                error_code="PROVIDER_HTTP_ERROR",
            )

        data = response.json()
        image_base64 = self._extract_image_base64(data)
        if not image_base64:
            raise AIEnhanceProviderError(
                "AI provider response did not contain image data",
                error_code="PROVIDER_EMPTY_RESPONSE",
            )

        return AIEnhanceOutput(
            status=True,
            image_base64=self._normalize_image_base64(image_base64),
            metadata=None,  # populated by service
            message="AI enhancement completed",
        )

    def _build_prompt(self, request: AIEnhanceRequest) -> str:
        return render_prompt_template(
            mode=request.mode,
            prompt_version=request.prompt_version,
            template_name=request.template_name,
            user_prompt=request.prompt,
        ).prompt

    @staticmethod
    def _normalize_image_base64(image_base64: str) -> str:
        if image_base64.startswith("data:image"):
            return image_base64
        return f"data:image/png;base64,{image_base64}"

    @staticmethod
    def _extract_image_base64(data: dict) -> Optional[str]:
        images = data.get("data") or []
        for item in images:
            if isinstance(item, dict):
                if item.get("b64_json"):
                    return item["b64_json"]
                if item.get("image_base64"):
                    return item["image_base64"]
        return None

    @staticmethod
    def _extract_error(text: str) -> str:
        return text.strip()[:300] if text else "unknown error"
