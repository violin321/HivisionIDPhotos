from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import build_ai_pro_mock_results  # noqa: E402
from hivision.plugin.ai_pro.quality import evaluate_ai_pro_quality  # noqa: E402


MODE = "ai_blue_formal_id_photo"
TARGET_SPEC = {"width": 295, "height": 413, "dpi": 300}
BLUE_RGB = (98, 139, 206)
FREE_RESULT = {"fileId": "free_file", "previewUrl": "/free-preview", "downloadUrl": "/free-download"}
CORE_QUALITY = {"passed": True, "score": 95}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_solid(path: Path, rgb: tuple[int, int, int], size: tuple[int, int]) -> None:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, :] = np.array(rgb, dtype=np.uint8)
    Image.fromarray(arr).save(path)


def make_ai_pro() -> dict:
    return {
        "enabled": True,
        "modes": [MODE],
        "promptParams": {"backgroundColor": "blue", "outfit": "dark suit", "retouchLevel": "medium"},
        "consentAccepted": True,
    }


def make_options() -> dict:
    return {"background": "blue", "renderMode": "solid", "width": 295, "height": 413, "dpi": 300}


def test_square_candidate_fails_without_stretched_derivative() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        candidate = root / "provider_1024.png"
        write_solid(candidate, BLUE_RGB, (1024, 1024))
        report = evaluate_ai_pro_quality(
            ai_image_path=candidate,
            output_dir=root,
            task_id="task_square_fail",
            target_spec=TARGET_SPEC,
            background_rgb=BLUE_RGB,
            free_result=FREE_RESULT,
            core_quality_report=CORE_QUALITY,
        )
        assert_true(report["passed"] is False, "square provider output should fail the ID-photo aspect-ratio gate")
        assert_true(report["fallbackToFree"] is True, "aspect-ratio failure should mark fallbackToFree")
        assert_true(report["fallbackReason"] == "AI_PRO_ASPECT_RATIO_MISMATCH", "fallback reason should identify aspect ratio mismatch")
        assert_true(report["usableImagePath"] is None, "mismatched output must not emit a stretched derivative")
        assert_true(report["checks"]["dimensions"]["derivative"] is None, "dimension derivative metadata should stay empty")
        assert_true(not list(root.glob("ai_pro_quality_resized_*.png")), "no resized derivative should be created for mismatched ratios")


def test_same_ratio_candidate_resizes_with_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        candidate = root / "provider_590x826.png"
        write_solid(candidate, BLUE_RGB, (590, 826))
        report = evaluate_ai_pro_quality(
            ai_image_path=candidate,
            output_dir=root,
            task_id="task_resize_pass",
            target_spec=TARGET_SPEC,
            background_rgb=BLUE_RGB,
            free_result=FREE_RESULT,
            core_quality_report=CORE_QUALITY,
        )
        assert_true(report["passed"] is True, "same-ratio candidate should pass after proportional resize")
        assert_true(report["usableImagePath"].endswith(".png"), "usable resized derivative should be emitted")
        assert_true(report["checks"]["dimensions"]["derivative"]["resizeMode"] == "proportional", "resize should be marked proportional")
        assert_true(any(item["code"] == "AI_PRO_OUTPUT_RESIZED" for item in report["warnings"]), "resize should be a warning")


def test_background_deviation_fails_to_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        candidate = root / "wrong_bg.png"
        write_solid(candidate, (255, 0, 0), (295, 413))
        report = evaluate_ai_pro_quality(
            ai_image_path=candidate,
            output_dir=root,
            task_id="task_bad_bg",
            target_spec=TARGET_SPEC,
            background_rgb=BLUE_RGB,
            free_result=FREE_RESULT,
            core_quality_report=CORE_QUALITY,
        )
        assert_true(report["passed"] is False, "severe background drift should fail")
        assert_true(report["fallbackToFree"] is True, "failed gate should mark fallbackToFree")
        assert_true(report["fallbackReason"] == "AI_PRO_BACKGROUND_COLOR_FAILED", "fallback reason should be auditable")


def test_fallback_result_metadata_contains_quality_status() -> None:
    fallback = build_ai_pro_mock_results(
        "task_quality_failed",
        FREE_RESULT,
        make_ai_pro(),
        CORE_QUALITY,
        template_id="cn-id-1inch",
        options=make_options(),
        mode_status={MODE: {"status": "quality_failed", "resultStatus": "quality_failed", "metadata": {"qualityGateStatus": "quality_failed", "fallbackToFree": True}}},
    )[0]
    assert_true(fallback["status"] == "quality_failed", "result status should reflect quality failure")
    assert_true(fallback["fallbackToFree"] is True, "result should expose fallbackToFree")
    assert_true(fallback["promptMetadata"]["qualityGateStatus"] == "quality_failed", "metadata should include quality gate status")
    assert_true(fallback["previewUrl"] == FREE_RESULT["previewUrl"], "fallback preview should use Free result")
    assert_true(fallback["downloadUrl"] == FREE_RESULT["downloadUrl"], "fallback download should use Free result")


def test_free_result_is_unchanged_by_ai_pro_failure() -> None:
    free_before = dict(FREE_RESULT)
    fallback = build_ai_pro_mock_results(
        "task_quality_failed",
        FREE_RESULT,
        make_ai_pro(),
        CORE_QUALITY,
        template_id="cn-id-1inch",
        options=make_options(),
        mode_status={MODE: {"status": "quality_failed", "resultStatus": "quality_failed", "metadata": {"qualityGateStatus": "quality_failed", "fallbackToFree": True}}},
    )[0]
    assert_true(FREE_RESULT == free_before, "Free Core result object should not be mutated")
    assert_true(fallback["previewUrl"] == free_before["previewUrl"], "AI Pro fallback should reference Free Core without altering it")


def main() -> None:
    test_square_candidate_fails_without_stretched_derivative()
    test_same_ratio_candidate_resizes_with_warning()
    test_background_deviation_fails_to_fallback()
    test_fallback_result_metadata_contains_quality_status()
    test_free_result_is_unchanged_by_ai_pro_failure()
    print("AI Pro quality gate tests passed")


if __name__ == "__main__":
    main()
