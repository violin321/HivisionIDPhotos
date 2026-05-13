from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from hivision.plugin.ai_enhance import AIEnhanceOutput, AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.schemas import AIEnhanceMetadata
from hivision.utils import base64_2_numpy, numpy_2_base64

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "ai_regression" / "manifest.json"


class EchoProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        image = base64_2_numpy(request.input_image_base64)
        if image is None:
            image = np.zeros((512, 512, 3), dtype=np.uint8)
        # A tiny brightness adjustment exercises the full guarded success path
        # while preserving identity/structure.
        edited = np.clip(image.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        return _output(request, edited, "echo regression provider")


class FaceTamperProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        image = base64_2_numpy(request.input_image_base64)
        if image is None:
            image = np.zeros((512, 512, 3), dtype=np.uint8)
        edited = image.copy()
        h, w = edited.shape[:2]
        edited[: max(1, int(h * 0.55)), max(0, int(w * 0.25)) : min(w, int(w * 0.75))] = (230, 230, 250)
        return _output(request, edited, "tamper regression provider")


class OutfitBadCropProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        crop = base64_2_numpy(request.input_image_base64)
        if crop is None:
            crop = np.zeros((256, 256, 3), dtype=np.uint8)
        edited = crop.copy()
        edited[:, :] = (255, 255, 255)
        return _output(request, edited, "bad outfit crop provider")


def _output(request: AIEnhanceRequest, image: np.ndarray, message: str) -> AIEnhanceOutput:
    return AIEnhanceOutput(
        status=True,
        image_base64=numpy_2_base64(image),
        metadata=AIEnhanceMetadata(
            fallback_used=False,
            fallback_reason=None,
            error_code=None,
            latency_ms=0,
            provider=request.provider,
            mode=request.mode,
            ai_generated=True,
        ),
        message=message,
    )


def _read_image_base64(path: Path) -> str:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode {path}")
    h, w = image.shape[:2]
    scale = min(1.0, 768.0 / float(max(h, w)))
    if scale < 1.0:
        image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    if min(image.shape[:2]) < 128:
        image = cv2.resize(image, (256, 256), interpolation=cv2.INTER_CUBIC)
    return numpy_2_base64(image)


def _iter_samples() -> Iterable[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return manifest.get("samples", [])


def _metadata_debug(output: AIEnhanceOutput) -> str:
    metadata = output.metadata
    payload = {
        "status": output.status,
        "message": output.message,
        "fallback_reason": metadata.fallback_reason,
        "error_code": metadata.error_code,
        "identity_guard_passed": metadata.identity_guard_passed,
        "identity_guard_metrics": metadata.identity_guard_metrics,
        "validation_passed": metadata.validation_passed,
        "validation_warnings": metadata.validation_warnings,
        "mask_edit": metadata.mask_edit,
        "crop_edit": metadata.crop_edit,
        "face_protected": metadata.face_protected,
        "edit_region": metadata.edit_region,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def assert_true(condition: bool, message: str, output: AIEnhanceOutput | None = None) -> None:
    if not condition:
        if output is not None:
            message = f"{message}\nmetadata={_metadata_debug(output)}"
        raise AssertionError(message)


def main() -> None:
    passed = 0
    skipped = 0
    for sample in _iter_samples():
        raw_path = Path(sample["path"])
        path = raw_path if raw_path.is_absolute() else ROOT / raw_path
        if not path.exists():
            print(f"SKIP {sample['id']}: missing {path}")
            skipped += 1
            continue
        try:
            input_b64 = _read_image_base64(path)
        except Exception as exc:
            print(f"SKIP {sample['id']}: {exc}")
            skipped += 1
            continue

        sample_modes = list(dict.fromkeys([*sample.get("modes", ["repair"]), "social_photo"]))
        for mode in sample_modes:
            service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
            template_name = "regression_template" if mode in {"background_template", "outfit"} else "resume_clean" if mode == "social_photo" else None
            output = service.enhance(AIEnhanceRequest(input_image_base64=input_b64, mode=mode, consent=True, template_name=template_name, client_id="ai-regression"))
            assert_true(output.status is True, f"{sample['id']} {mode} should pass basic guarded generation", output)
            assert_true(output.metadata.identity_guard_passed is True, f"{sample['id']} {mode} identity guard should pass", output)
            assert_true("protected_mean_delta" in output.metadata.identity_guard_metrics, f"{sample['id']} {mode} missing identity metrics", output)
            passed += 1

        for mode in ("repair", "background_template", "social_photo"):
            service = AIEnhanceService(provider_map={"gpt-image-2": FaceTamperProvider()})
            template_name = "regression_template" if mode == "background_template" else "resume_clean" if mode == "social_photo" else None
            output = service.enhance(AIEnhanceRequest(input_image_base64=input_b64, mode=mode, consent=True, template_name=template_name, client_id="ai-regression-tamper"))
            assert_true(output.status is False, f"{sample['id']} {mode} tamper should fallback", output)
            assert_true(output.metadata.identity_guard_passed is False, f"{sample['id']} {mode} should record guard failure", output)
            assert_true(output.metadata.error_code in {"IDENTITY_PROTECTED_REGION_CHANGED", "IDENTITY_STRUCTURE_CHANGED", "IDENTITY_FACE_COLOR_SHIFT", "AI_OUTPUT_MODIFIED_TOO_MUCH", "BACKGROUND_SPILL_DETECTED"}, f"{sample['id']} {mode} unexpected error {output.metadata.error_code}", output)
            passed += 1

        service = AIEnhanceService(provider_map={"gpt-image-2": OutfitBadCropProvider()})
        output = service.enhance(AIEnhanceRequest(input_image_base64=input_b64, mode="outfit", consent=True, template_name="business_suit_black", client_id="ai-regression-outfit"))
        # The crop/mask path should either reject suspicious outfit output or composite it safely.
        if output.status is False:
            assert_true(output.metadata.error_code is not None, f"{sample['id']} outfit fallback should carry error code", output)
        else:
            assert_true(output.metadata.mask_edit is True and output.metadata.face_protected is True, f"{sample['id']} outfit success should be masked/protected", output)
            assert_true(output.metadata.identity_guard_passed is True, f"{sample['id']} outfit safe composite should pass identity guard", output)
        passed += 1

    print(f"AI regression suite passed: checks={passed}, skipped_samples={skipped}")


if __name__ == "__main__":
    main()
