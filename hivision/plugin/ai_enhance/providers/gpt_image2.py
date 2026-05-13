from __future__ import annotations

import os
from typing import Optional

import requests

from ..errors import AIEnhanceConfigError, AIEnhanceProviderError
from ..schemas import AIEnhanceOutput, AIEnhanceRequest
from .base import BaseAIEnhanceProvider

_DEFAULT_TIMEOUT = float(os.getenv("OPENAI_IMAGE_TIMEOUT", "30"))

_BACKGROUND_TEMPLATE_PROMPTS = {
    "clean_blue": "Use a clean, official ID-photo blue background: smooth, even, studio-style, no texture, no shadows, and no color spill on the person.",
    "clean_white": "Use a clean white ID-photo background: neutral, evenly lit, no gray cast, no texture, and preserve clear separation from hair and clothing.",
    "clean_gray": "Use a clean light-gray studio ID-photo background: subtle neutral gray, even lighting, no texture, and no tint spill onto skin or clothes.",
    "resume_soft": "Use a soft professional resume portrait background: very light neutral blue-gray, minimal gradient, corporate and restrained, no decorative elements.",
    "linkedin_clean": "Use a clean professional LinkedIn-style studio background: neutral light gray-blue, polished but conservative, no bokeh, props, logos, or decorative elements.",
}

_OUTFIT_TEMPLATE_PROMPTS = {
    "business_suit_black": "Change only the visible upper-body clothing to a conservative black business suit jacket with a simple light shirt. Keep it neat, realistic, and understated.",
    "business_suit_navy": "Change only the visible upper-body clothing to a conservative navy business suit jacket with a simple light shirt. Keep it neat, realistic, and understated.",
    "white_shirt": "Change only the visible upper-body clothing to a clean plain white business shirt. Keep it professional, realistic, and understated.",
    "business_casual": "Change only the visible upper-body clothing to conservative business-casual attire, such as a simple blazer or neat collared shirt. Keep it professional and restrained.",
}


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
        mode_prompt = {
            "repair": (
                "Lightly repair this ID photo while preserving identity exactly. Keep the original face shape, facial features,"
                " age, skin texture, hairstyle, expression, pose, clothing, crop, and background color. Correct unnatural color"
                " cast on the face and restore natural human skin tone under neutral studio lighting. The blue/red/white ID-photo"
                " background must not spill onto or tint the skin. Do not beautify, reshape, relight dramatically, change clothes,"
                " change the background, add accessories, or alter identity."
            ),
            "background_template": (
                "Refine only the ID-photo background/template area while preserving the same person exactly. Keep natural human"
                " skin tone under neutral studio lighting, and prevent the background color from tinting the face, hair, ears, neck,"
                " or clothes. Preserve facial features, age, hairstyle, expression, pose, clothing category, crop, and identity."
                " Do not beautify, reshape, add accessories, or alter identity."
            ),
            "outfit": (
                "Replace only the visible upper-body clothing. Do not generate a new headshot, avatar image, sample card, photo frame, embedded image,"
                " nested photo, document layout, or any picture-in-picture composition. Keep the same person, identity, face, hair, ears, upper neck, skin tone,"
                " expression, pose, shoulder line, crop, camera angle, background, and lighting exactly unchanged. Preserve the existing framing and continue the"
                " original background naturally around the edited clothes. Do not add accessories, logos, jewelry, props, text, borders, cards, or decorative elements."
                " Do not beautify, reshape, relight dramatically, change the background, or alter any non-clothing pixels unless needed for seamless clothing edges."
            ),
        }[request.mode]

        optional_parts = []
        if request.mode == "background_template" and request.template_name:
            template_prompt = _BACKGROUND_TEMPLATE_PROMPTS.get(
                request.template_name,
                f"Use the named background template '{request.template_name}' as a conservative ID-photo background reference.",
            )
            optional_parts.append(f"Target background template: {request.template_name}. {template_prompt}")
            optional_parts.append(
                "Hard constraints: keep identity unchanged, keep natural skin tone, do not let the background color contaminate the person, do not alter the face, and do not add accessories."
            )
        if request.mode == "outfit" and request.template_name:
            template_prompt = _OUTFIT_TEMPLATE_PROMPTS.get(
                request.template_name,
                f"Use the named outfit template '{request.template_name}' as a conservative professional upper-body clothing reference.",
            )
            optional_parts.append(f"Target outfit template: {request.template_name}. {template_prompt}")
            optional_parts.append(
                "Hard constraints: replace clothing only inside the provided clothing mask. Keep face, hair, ears, upper neck, shoulder line, crop, and background unchanged. Do not create a new headshot, avatar image, sample card, border, frame, or embedded image."
            )
        if request.prompt:
            optional_parts.append(f"Additional user instruction: {request.prompt.strip()}")

        return " ".join([mode_prompt] + optional_parts)

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
