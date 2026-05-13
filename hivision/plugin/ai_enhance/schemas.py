from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .errors import AIEnhanceValidationError

ALLOWED_MODES = {"repair", "background_template", "outfit"}
ALLOWED_PROVIDERS = {"gpt-image-2"}


@dataclass
class AIEnhanceRequest:
    input_image_base64: str
    mode: str
    provider: str = "gpt-image-2"
    consent: bool = False
    prompt: Optional[str] = None
    template_name: Optional[str] = None
    return_base64: bool = True
    client_id: Optional[str] = None
    mask_base64: Optional[str] = None
    edit_region: Optional[Dict[str, Any]] = None

    def validate(self) -> "AIEnhanceRequest":
        if not self.input_image_base64 or not self.input_image_base64.strip():
            raise AIEnhanceValidationError("input_image_base64 is required")
        if self.mode not in ALLOWED_MODES:
            raise AIEnhanceValidationError(
                f"mode must be one of: {', '.join(sorted(ALLOWED_MODES))}"
            )
        if self.provider not in ALLOWED_PROVIDERS:
            raise AIEnhanceValidationError(
                f"provider must be one of: {', '.join(sorted(ALLOWED_PROVIDERS))}"
            )
        return self

    def to_safe_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["input_image_base64"] = "<redacted>"
        if data.get("mask_base64"):
            data["mask_base64"] = "<redacted>"
        return data


@dataclass
class AIEnhanceMetadata:
    fallback_used: bool
    fallback_reason: Optional[str]
    error_code: Optional[str]
    latency_ms: int
    provider: str
    mode: str
    ai_generated: bool
    validation_passed: bool = False
    validation_warnings: List[str] = field(default_factory=list)
    debug_input_path: Optional[str] = None
    debug_output_path: Optional[str] = None
    debug_metadata_path: Optional[str] = None
    request_id: Optional[str] = None
    estimated_cost: Optional[float] = None
    rate_limited: bool = False
    usage_logged: bool = False
    template_name: Optional[str] = None
    mask_edit: bool = False
    crop_edit: bool = False
    face_protected: bool = False
    color_guard_passed: Optional[bool] = None
    protected_region_delta: Optional[float] = None
    identity_guard_passed: Optional[bool] = None
    identity_guard_metrics: Dict[str, Any] = field(default_factory=dict)
    edit_region: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIEnhanceOutput:
    status: bool
    image_base64: Optional[str]
    metadata: AIEnhanceMetadata
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "image_base64": self.image_base64,
            "metadata": self.metadata.to_dict(),
            "message": self.message,
        }
