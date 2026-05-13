from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Optional

from .errors import AIEnhanceConfigError, AIEnhanceConsentError, AIEnhanceProviderError
from .identity_guard import validate_identity_structure_guard
from .outfit_protection import (
    build_outfit_edit_plan,
    check_nested_photo_artifact,
    check_protected_region_color,
    composite_crop,
    crop_request_image,
)
from .prompt_templates import render_prompt_template
from .providers import GPTImage2Provider
from .rate_limit import RATE_LIMITER
from .schemas import AIEnhanceMetadata, AIEnhanceOutput, AIEnhanceRequest
from .usage import USAGE_LOGGER
from .validator import validate_ai_enhance_image


class AIEnhanceService:
    def __init__(self, provider_map: Optional[dict] = None, rate_limiter=None, usage_logger=None):
        self.provider_map = provider_map or {
            "gpt-image-2": GPTImage2Provider(),
        }
        self.rate_limiter = rate_limiter or RATE_LIMITER
        self.usage_logger = usage_logger or USAGE_LOGGER

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        request.validate()
        prompt_template = render_prompt_template(
            mode=request.mode,
            prompt_version=request.prompt_version,
            template_name=request.template_name,
            user_prompt=request.prompt,
        )
        started_at = time.time()
        request_id = uuid.uuid4().hex
        estimated_cost = self.usage_logger.estimated_cost()
        debug_paths = self._init_debug_paths(request)
        self._save_debug_base64(debug_paths.get("input"), request.input_image_base64)

        rate_limit_key = self.rate_limiter.build_key(request.provider, request.mode, request.client_id)
        decision = self.rate_limiter.acquire(rate_limit_key)
        if not decision.allowed:
            return self._fallback_output(
                request=request,
                message=decision.message or "AI enhancement request rejected by rate limiter.",
                fallback_reason="rate_limited",
                error_code=decision.error_code or "RATE_LIMITED",
                started_at=started_at,
                debug_paths=debug_paths,
                request_id=request_id,
                estimated_cost=estimated_cost,
                rate_limited=True,
            )

        try:
            if not request.consent:
                return self._fallback_output(
                    request=request,
                    message="AI enhancement skipped because consent=false; image was not uploaded.",
                    fallback_reason="consent_missing",
                    error_code=AIEnhanceConsentError().error_code,
                    started_at=started_at,
                    debug_paths=debug_paths,
                    request_id=request_id,
                    estimated_cost=estimated_cost,
                )

            provider = self.provider_map[request.provider]
            if hasattr(provider, "is_configured") and not provider.is_configured():
                return self._fallback_output(
                    request=request,
                    message="AI enhancement skipped because provider is not configured.",
                    fallback_reason="provider_not_configured",
                    error_code=AIEnhanceConfigError().error_code,
                    started_at=started_at,
                    debug_paths=debug_paths,
                    request_id=request_id,
                    estimated_cost=estimated_cost,
                )

            provider_request = request
            outfit_plan = None
            mask_edit = False
            crop_edit = False
            face_protected = False
            protected_region_delta = None
            color_guard_passed = None
            identity_guard_passed = None
            identity_guard_metrics = {}
            if request.mode == "outfit":
                try:
                    outfit_plan = build_outfit_edit_plan(request.input_image_base64)
                    provider_request = replace(
                        request,
                        input_image_base64=crop_request_image(request.input_image_base64, outfit_plan.crop_box),
                        mask_base64=outfit_plan.mask_base64,
                        edit_region=outfit_plan.edit_region,
                    )
                    crop_edit = True
                    mask_edit = True
                    face_protected = True
                except Exception:
                    # Fail open to the existing provider path, but leave metadata
                    # explicit that crop/mask protection was not applied.
                    provider_request = request

            try:
                output = provider.enhance(provider_request)
            except (AIEnhanceConfigError, AIEnhanceProviderError) as exc:
                return self._fallback_output(
                    request=request,
                    message=f"AI enhancement fallback used: {exc.message}",
                    fallback_reason="provider_error",
                    error_code=exc.error_code,
                    started_at=started_at,
                    debug_paths=debug_paths,
                    request_id=request_id,
                    estimated_cost=estimated_cost,
                    mask_edit=mask_edit,
                    crop_edit=crop_edit,
                    face_protected=face_protected,
                    edit_region=outfit_plan.edit_region if outfit_plan else None,
                )

            if outfit_plan and output.image_base64:
                try:
                    nested_photo_guard = check_nested_photo_artifact(
                        provider_request.input_image_base64,
                        output.image_base64,
                    )
                    if not nested_photo_guard.passed:
                        return self._fallback_output(
                            request=request,
                            message=(
                                "AI outfit fallback used because edited crop looked like an embedded photo/card: "
                                f"{nested_photo_guard.message or nested_photo_guard.error_code}"
                            ),
                            fallback_reason="validation_failed",
                            error_code=nested_photo_guard.error_code or "OUTFIT_NESTED_PHOTO_GUARD_FAILED",
                            started_at=started_at,
                            debug_paths=debug_paths,
                            validation_passed=False,
                            request_id=request_id,
                            estimated_cost=estimated_cost,
                            mask_edit=mask_edit,
                            crop_edit=crop_edit,
                            face_protected=face_protected,
                            color_guard_passed=False,
                            protected_region_delta=nested_photo_guard.delta,
                            edit_region=outfit_plan.edit_region,
                        )

                    output.image_base64 = composite_crop(
                        request.input_image_base64,
                        output.image_base64,
                        outfit_plan.crop_box,
                        outfit_plan.mask_base64,
                    )
                    color_guard = check_protected_region_color(
                        request.input_image_base64,
                        output.image_base64,
                        outfit_plan.edit_region,
                    )
                    protected_region_delta = color_guard.delta
                    color_guard_passed = color_guard.passed
                    if not color_guard.passed:
                        return self._fallback_output(
                            request=request,
                            message=(
                                "AI outfit fallback used because protected face/upper region failed color guard: "
                                f"{color_guard.message or color_guard.error_code}"
                            ),
                            fallback_reason="validation_failed",
                            error_code=color_guard.error_code or "OUTFIT_COLOR_GUARD_FAILED",
                            started_at=started_at,
                            debug_paths=debug_paths,
                            validation_warnings=list(color_guard.warnings),
                            validation_passed=False,
                            request_id=request_id,
                            estimated_cost=estimated_cost,
                            mask_edit=mask_edit,
                            crop_edit=crop_edit,
                            face_protected=face_protected,
                            color_guard_passed=False,
                            protected_region_delta=protected_region_delta,
                            edit_region=outfit_plan.edit_region,
                        )
                except Exception as exc:
                    return self._fallback_output(
                        request=request,
                        message=f"AI outfit fallback used because crop composite/color guard failed: {exc}",
                        fallback_reason="validation_failed",
                        error_code="OUTFIT_COLOR_GUARD_FAILED",
                        started_at=started_at,
                        debug_paths=debug_paths,
                        validation_passed=False,
                        request_id=request_id,
                        estimated_cost=estimated_cost,
                        mask_edit=mask_edit,
                        crop_edit=crop_edit,
                        face_protected=face_protected,
                        color_guard_passed=False,
                        edit_region=outfit_plan.edit_region,
                    )

            validation = validate_ai_enhance_image(output.image_base64 or "")
            identity_guard = validate_identity_structure_guard(
                request.input_image_base64,
                output.image_base64 or "",
                request.mode,
                outfit_plan.edit_region if outfit_plan else request.edit_region,
            )
            identity_guard_passed = identity_guard.passed
            identity_guard_metrics = identity_guard.metrics
            identity_warnings = [f"identity_guard:{warning}" for warning in identity_guard.warnings]
            validation.warnings.extend(identity_warnings)
            for metric_key, metric_value in sorted(identity_guard_metrics.items()):
                validation.warnings.append(f"identity_guard_metric:{metric_key}={metric_value}")
            if outfit_plan and color_guard_passed and protected_region_delta is not None:
                color_guard_warning = f"protected_region_delta:{protected_region_delta:.2f}"
                if color_guard_warning not in validation.warnings:
                    validation.warnings.extend([color_guard_warning])
                if validation.error_code == "COLOR_CAST_DETECTED":
                    global_cast_warning = "global_blue_cast_warning:" + (validation.message or validation.error_code)
                    if global_cast_warning not in validation.warnings:
                        validation.warnings.append(global_cast_warning)
                    validation.passed = True
                    validation.error_code = None
                    validation.message = None
            self._save_debug_base64(debug_paths.get("output"), output.image_base64)

            if not validation.passed:
                return self._fallback_output(
                    request=request,
                    message=(
                        "AI enhancement fallback used because provider output failed validation: "
                        f"{validation.message or validation.error_code}"
                    ),
                    fallback_reason="validation_failed",
                    error_code=validation.error_code or "VALIDATION_FAILED",
                    started_at=started_at,
                    debug_paths=debug_paths,
                    validation_warnings=validation.warnings,
                    validation_passed=False,
                    request_id=request_id,
                    estimated_cost=estimated_cost,
                    mask_edit=mask_edit,
                    crop_edit=crop_edit,
                    face_protected=face_protected,
                    color_guard_passed=color_guard_passed,
                    protected_region_delta=protected_region_delta,
                    identity_guard_passed=identity_guard_passed,
                    identity_guard_metrics=identity_guard_metrics,
                    edit_region=outfit_plan.edit_region if outfit_plan else request.edit_region,
                )

            if not identity_guard.passed:
                return self._fallback_output(
                    request=request,
                    message=(
                        "AI enhancement fallback used because identity/structure guard failed: "
                        f"{identity_guard.message or identity_guard.error_code}"
                    ),
                    fallback_reason="validation_failed",
                    error_code=identity_guard.error_code or "IDENTITY_GUARD_FAILED",
                    started_at=started_at,
                    debug_paths=debug_paths,
                    validation_warnings=validation.warnings,
                    validation_passed=False,
                    request_id=request_id,
                    estimated_cost=estimated_cost,
                    mask_edit=mask_edit,
                    crop_edit=crop_edit,
                    face_protected=face_protected or request.mode in {"repair", "background_template"},
                    color_guard_passed=color_guard_passed,
                    protected_region_delta=protected_region_delta,
                    identity_guard_passed=False,
                    identity_guard_metrics=identity_guard_metrics,
                    edit_region=outfit_plan.edit_region if outfit_plan else request.edit_region,
                )

            output.metadata = AIEnhanceMetadata(
                fallback_used=False,
                fallback_reason=None,
                error_code=None,
                latency_ms=self._latency_ms(started_at),
                provider=request.provider,
                mode=request.mode,
                ai_generated=True,
                validation_passed=True,
                validation_warnings=validation.warnings,
                debug_input_path=debug_paths.get("input"),
                debug_output_path=debug_paths.get("output"),
                debug_metadata_path=debug_paths.get("metadata"),
                request_id=request_id,
                estimated_cost=estimated_cost,
                rate_limited=False,
                usage_logged=False,
                template_name=request.template_name if request.mode in {"background_template", "outfit"} else None,
                prompt_template_key=prompt_template.key,
                prompt_template_version=prompt_template.version,
                prompt_template_hash=prompt_template.hash,
                mask_edit=mask_edit,
                crop_edit=crop_edit,
                face_protected=face_protected or request.mode in {"repair", "background_template"},
                color_guard_passed=color_guard_passed,
                protected_region_delta=protected_region_delta,
                identity_guard_passed=identity_guard_passed,
                identity_guard_metrics=identity_guard_metrics,
                edit_region=outfit_plan.edit_region if outfit_plan else request.edit_region,
            )
            self._save_debug_metadata(debug_paths.get("metadata"), request, output)
            output.metadata.usage_logged = self._log_usage(output)
            return output
        finally:
            self.rate_limiter.release(rate_limit_key)

    def _fallback_output(
        self,
        request: AIEnhanceRequest,
        message: str,
        fallback_reason: str,
        error_code: str,
        started_at: float,
        debug_paths: Optional[dict] = None,
        validation_warnings: Optional[list] = None,
        validation_passed: bool = False,
        request_id: Optional[str] = None,
        estimated_cost: Optional[float] = None,
        rate_limited: bool = False,
        mask_edit: bool = False,
        crop_edit: bool = False,
        face_protected: bool = False,
        color_guard_passed: Optional[bool] = None,
        protected_region_delta: Optional[float] = None,
        identity_guard_passed: Optional[bool] = None,
        identity_guard_metrics: Optional[dict] = None,
        edit_region: Optional[dict] = None,
    ) -> AIEnhanceOutput:
        prompt_template = render_prompt_template(
            mode=request.mode,
            prompt_version=request.prompt_version,
            template_name=request.template_name,
            user_prompt=request.prompt,
        )
        output = AIEnhanceOutput(
            status=False,
            image_base64=request.input_image_base64 if request.return_base64 else None,
            metadata=AIEnhanceMetadata(
                fallback_used=True,
                fallback_reason=fallback_reason,
                error_code=error_code,
                latency_ms=self._latency_ms(started_at),
                provider=request.provider,
                mode=request.mode,
                ai_generated=False,
                validation_passed=validation_passed,
                validation_warnings=validation_warnings or [],
                debug_input_path=(debug_paths or {}).get("input"),
                debug_output_path=(debug_paths or {}).get("output"),
                debug_metadata_path=(debug_paths or {}).get("metadata"),
                request_id=request_id,
                estimated_cost=estimated_cost,
                rate_limited=rate_limited,
                usage_logged=False,
                template_name=request.template_name if request.mode in {"background_template", "outfit"} else None,
                prompt_template_key=prompt_template.key,
                prompt_template_version=prompt_template.version,
                prompt_template_hash=prompt_template.hash,
                mask_edit=mask_edit,
                crop_edit=crop_edit,
                face_protected=face_protected,
                color_guard_passed=color_guard_passed,
                protected_region_delta=protected_region_delta,
                identity_guard_passed=identity_guard_passed,
                identity_guard_metrics=identity_guard_metrics or {},
                edit_region=edit_region,
            ),
            message=message,
        )
        self._save_debug_metadata((debug_paths or {}).get("metadata"), request, output)
        output.metadata.usage_logged = self._log_usage(output)
        return output

    def _log_usage(self, output: AIEnhanceOutput) -> bool:
        metadata = output.metadata
        return self.usage_logger.append(
            {
                "request_id": metadata.request_id,
                "provider": metadata.provider,
                "mode": metadata.mode,
                "status": output.status,
                "fallback_reason": metadata.fallback_reason,
                "error_code": metadata.error_code,
                "latency_ms": metadata.latency_ms,
                "validation_passed": metadata.validation_passed,
                "estimated_cost": metadata.estimated_cost,
                "rate_limited": metadata.rate_limited,
                "template_name": metadata.template_name,
                "prompt_template_key": metadata.prompt_template_key,
                "prompt_template_version": metadata.prompt_template_version,
                "prompt_template_hash": metadata.prompt_template_hash,
                "mask_edit": metadata.mask_edit,
                "crop_edit": metadata.crop_edit,
                "face_protected": metadata.face_protected,
                "color_guard_passed": metadata.color_guard_passed,
                "protected_region_delta": metadata.protected_region_delta,
                "identity_guard_passed": metadata.identity_guard_passed,
                "identity_guard_metrics": metadata.identity_guard_metrics,
            }
        )

    @staticmethod
    def _latency_ms(started_at: float) -> int:
        return int((time.time() - started_at) * 1000)

    @staticmethod
    def _debug_enabled() -> bool:
        value = os.getenv("AI_ENHANCE_DEBUG_SAVE", "0").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def _init_debug_paths(self, request: AIEnhanceRequest) -> dict:
        if not self._debug_enabled():
            return {"input": None, "output": None, "metadata": None}

        base_dir = Path(os.getenv("AI_ENHANCE_DEBUG_DIR", "/tmp/hivision-ai-enhance-debug"))
        run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{request.mode}-{uuid.uuid4().hex[:8]}"
        run_dir = base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return {
            "input": str(run_dir / "input.png"),
            "output": str(run_dir / "output.png"),
            "metadata": str(run_dir / "metadata.json"),
        }

    @staticmethod
    def _split_data_url(image_base64: str) -> tuple[str, str]:
        if image_base64.startswith("data:image") and "," in image_base64:
            header, payload = image_base64.split(",", 1)
            if "image/jpeg" in header:
                return ".jpg", payload
            if "image/webp" in header:
                return ".webp", payload
            return ".png", payload
        return ".png", image_base64

    def _save_debug_base64(self, target_path: Optional[str], image_base64: Optional[str]) -> None:
        if not target_path or not image_base64:
            return
        suffix, payload = self._split_data_url(image_base64)
        real_path = Path(target_path)
        if real_path.suffix != suffix:
            real_path = real_path.with_suffix(suffix)
        raw = self._decode_base64_bytes(payload)
        real_path.write_bytes(raw)

    @staticmethod
    def _decode_base64_bytes(payload: str) -> bytes:
        import base64

        return base64.b64decode(payload)

    def _save_debug_metadata(
        self,
        target_path: Optional[str],
        request: AIEnhanceRequest,
        output: AIEnhanceOutput,
    ) -> None:
        if not target_path:
            return
        payload = {
            "request": request.to_safe_dict(),
            "output": {
                "status": output.status,
                "message": output.message,
                "metadata": output.metadata.to_dict(),
            },
        }
        Path(target_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
