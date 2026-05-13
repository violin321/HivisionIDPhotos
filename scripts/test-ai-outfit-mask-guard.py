from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from hivision.plugin.ai_enhance import AIEnhanceOutput, AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.outfit_protection import (
    build_outfit_edit_plan,
    check_nested_photo_artifact,
    check_protected_region_color,
    composite_crop,
    crop_request_image,
)
from hivision.plugin.ai_enhance.schemas import AIEnhanceMetadata
from hivision.utils import base64_2_numpy, numpy_2_base64


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_portrait_base64() -> str:
    image = np.zeros((400, 300, 3), dtype=np.uint8)
    image[:, :] = (235, 235, 235)  # light background in BGR
    image[:224, 90:210] = (105, 145, 190)  # protected head/face-ish area
    image[224:, 40:260] = (40, 40, 40)  # clothing/shoulders
    return numpy_2_base64(image)


class CaptureOutfitProvider:
    provider_name = "gpt-image-2"

    def __init__(self, edit_bgr=(20, 60, 150)):
        self.last_request = None
        self.edit_bgr = edit_bgr

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        self.last_request = request
        crop = base64_2_numpy(request.input_image_base64)
        assert crop is not None
        edited = crop.copy()
        edited[:, :] = self.edit_bgr
        return AIEnhanceOutput(
            status=True,
            image_base64=numpy_2_base64(edited),
            metadata=AIEnhanceMetadata(
                fallback_used=False,
                fallback_reason=None,
                error_code=None,
                latency_ms=0,
                provider=request.provider,
                mode=request.mode,
                ai_generated=True,
            ),
            message="fake outfit crop output",
        )


def test_outfit_edit_plan_builds_crop_sized_mask() -> None:
    source = make_portrait_base64()
    plan = build_outfit_edit_plan(source)
    mask = base64_2_numpy(plan.mask_base64)
    assert_true(mask is not None, "mask should decode")
    x1, y1, x2, y2 = plan.crop_box
    assert_true(plan.crop_box[1] == y1, "crop should start at protected boundary")
    assert_true(mask.shape[:2] == (y2 - y1, x2 - x1), "mask must match crop size")
    assert_true(mask.min() == 0 and mask.max() == 255, "crop mask should protect non-clothing pixels")
    assert_true(mask[: max(1, mask.shape[0] // 20)].max() == 0, "top crop edge must stay protected")
    assert_true(mask[:, : max(1, mask.shape[1] // 25)].max() == 0, "crop side edge must stay protected")
    assert_true(plan.edit_region["protected_y_max"] == y1, "protected boundary should match crop start")
    assert_true(plan.edit_region["strategy"] == "masked_crop_composite", "outfit should use masked composite strategy")


def test_crop_composite_preserves_protected_region() -> None:
    source = make_portrait_base64()
    plan = build_outfit_edit_plan(source)
    crop_h = plan.crop_box[3] - plan.crop_box[1]
    crop_w = plan.crop_box[2] - plan.crop_box[0]
    edited_crop = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
    edited_crop[:, :] = (10, 80, 160)
    composited = composite_crop(source, numpy_2_base64(edited_crop), plan.crop_box)
    check = check_protected_region_color(source, composited, plan.edit_region)
    assert_true(check.passed is True, "crop composite should preserve protected color")
    assert_true(check.delta < 0.1, f"protected delta should be near zero, got {check.delta}")


def test_color_guard_detects_protected_change() -> None:
    source = make_portrait_base64()
    altered = base64_2_numpy(source)
    assert altered is not None
    altered[:224, :, 0] = np.clip(altered[:224, :, 0].astype(np.int16) + 60, 0, 255).astype(np.uint8)
    check = check_protected_region_color(source, numpy_2_base64(altered), {"protected_y_max": 224})
    assert_true(check.passed is False, "blue shift in protected region should fail")
    assert_true(
        check.error_code in {"FACE_COLOR_SHIFT_DETECTED", "PROTECTED_REGION_CHANGED"},
        f"unexpected color guard error: {check.error_code}",
    )


def test_service_sets_outfit_metadata_and_sends_crop_request() -> None:
    provider = CaptureOutfitProvider()
    service = AIEnhanceService(provider_map={"gpt-image-2": provider})
    output = service.enhance(
        AIEnhanceRequest(
            input_image_base64=make_portrait_base64(),
            mode="outfit",
            consent=True,
            template_name="business_suit_black",
            client_id="mask-guard-test",
        )
    )
    assert_true(output.status is True, "outfit crop/composite service path should pass")
    assert_true(provider.last_request is not None, "provider should be called")
    sent = base64_2_numpy(provider.last_request.input_image_base64)
    assert_true(sent.shape[0] < 400, "provider should receive lower crop, not full portrait")
    assert_true(provider.last_request.mask_base64 is not None, "request should carry mask_base64")
    sent_mask = base64_2_numpy(provider.last_request.mask_base64)
    assert_true(sent_mask is not None, "provider mask should decode")
    assert_true(sent_mask.shape[:2] == sent.shape[:2], "provider mask must match crop image size")
    assert_true(provider.last_request.edit_region["strategy"] == "masked_crop_composite", "request should carry edit region")
    assert_true(output.metadata.mask_edit is True, "metadata.mask_edit missing")
    assert_true(output.metadata.crop_edit is True, "metadata.crop_edit missing")
    assert_true(output.metadata.face_protected is True, "metadata.face_protected missing")
    assert_true(output.metadata.color_guard_passed is True, "metadata.color_guard_passed should be true")
    assert_true(output.metadata.protected_region_delta is not None, "protected region delta should be recorded")


def test_outfit_global_blue_cast_with_clean_protected_region_warns_not_fallback() -> None:
    provider = CaptureOutfitProvider(edit_bgr=(255, 20, 20))
    service = AIEnhanceService(provider_map={"gpt-image-2": provider})
    output = service.enhance(
        AIEnhanceRequest(
            input_image_base64=make_portrait_base64(),
            mode="outfit",
            consent=True,
            template_name="business_suit_navy",
            client_id="outfit-global-blue-test",
        )
    )
    assert_true(output.status is True, "outfit global blue cast should pass when protected color guard passes")
    assert_true(output.metadata.fallback_used is False, "outfit global blue cast should not fallback")
    assert_true(output.metadata.fallback_reason is None, "successful outfit should not carry fallback reason")
    assert_true(output.metadata.error_code is None, "successful outfit should not carry COLOR_CAST_DETECTED")
    assert_true(output.metadata.validation_passed is True, "downgraded outfit color cast should validate")
    assert_true(output.metadata.color_guard_passed is True, "protected color guard should pass")
    assert_true(output.metadata.protected_region_delta is not None, "protected region delta should be recorded")
    assert_true(output.metadata.protected_region_delta < 0.1, "protected region delta should stay near zero")
    assert_true(
        output.metadata.validation_warnings == []
        or any("blue_cast" in warning for warning in output.metadata.validation_warnings),
        "masked outfit composite should avoid fallback while preserving any color-cast warnings",
    )


def test_outfit_nested_photo_guard_blocks_embedded_card() -> None:
    source = make_portrait_base64()
    plan = build_outfit_edit_plan(source)
    crop_h = plan.crop_box[3] - plan.crop_box[1]
    crop_w = plan.crop_box[2] - plan.crop_box[0]
    suspicious = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
    suspicious[:, :] = (60, 70, 80)
    pad_x = max(12, crop_w // 7)
    pad_y = max(12, crop_h // 7)
    suspicious[pad_y : crop_h - pad_y, pad_x : crop_w - pad_x] = (248, 248, 248)
    check = check_nested_photo_artifact(
        crop_request_image(source, plan.crop_box),
        numpy_2_base64(suspicious),
    )
    assert_true(check.passed is False, "nested-photo guard should block embedded white card")
    assert_true(check.error_code == "OUTFIT_NESTED_PHOTO_DETECTED", f"unexpected nested-photo error: {check.error_code}")


def test_masked_composite_preserves_crop_background_and_edges() -> None:
    source = make_portrait_base64()
    plan = build_outfit_edit_plan(source)
    crop_h = plan.crop_box[3] - plan.crop_box[1]
    crop_w = plan.crop_box[2] - plan.crop_box[0]
    bad_full_crop = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
    bad_full_crop[:, :] = (245, 245, 245)
    composited = composite_crop(source, numpy_2_base64(bad_full_crop), plan.crop_box, plan.mask_base64)
    original = base64_2_numpy(source)
    result = base64_2_numpy(composited)
    assert_true(original is not None and result is not None, "images should decode")
    x1, y1, x2, y2 = plan.crop_box
    top_guard_h = max(1, crop_h // 20)
    side_guard_w = max(1, crop_w // 25)
    assert_true(
        np.abs(result[y1 : y1 + top_guard_h, x1:x2, :3].astype(np.int16) - original[y1 : y1 + top_guard_h, x1:x2, :3].astype(np.int16)).max() == 0,
        "masked composite should preserve crop top guard/background",
    )
    assert_true(
        np.abs(result[y1:y2, x1 : x1 + side_guard_w, :3].astype(np.int16) - original[y1:y2, x1 : x1 + side_guard_w, :3].astype(np.int16)).max() == 0,
        "masked composite should preserve crop side guard/background",
    )


def test_outfit_protected_region_change_still_fallbacks() -> None:
    source = make_portrait_base64()
    altered = base64_2_numpy(source)
    assert altered is not None
    altered[:224, :, 0] = np.clip(altered[:224, :, 0].astype(np.int16) + 60, 0, 255).astype(np.uint8)
    check = check_protected_region_color(source, numpy_2_base64(altered), {"protected_y_max": 224})
    assert_true(check.passed is False, "protected region color shift must remain a fallback condition")


def main() -> None:
    test_outfit_edit_plan_builds_crop_sized_mask()
    test_crop_composite_preserves_protected_region()
    test_color_guard_detects_protected_change()
    test_service_sets_outfit_metadata_and_sends_crop_request()
    test_outfit_global_blue_cast_with_clean_protected_region_warns_not_fallback()
    test_outfit_nested_photo_guard_blocks_embedded_card()
    test_masked_composite_preserves_crop_background_and_edges()
    test_outfit_protected_region_change_still_fallbacks()
    print("AI outfit mask/crop guard tests passed")


if __name__ == "__main__":
    main()
