from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import build_ai_pro_mock_results  # noqa: E402
import hivision.plugin.ai_pro.quality as quality_module  # noqa: E402
from hivision.plugin.ai_pro.quality import evaluate_ai_pro_quality  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "ai_pro_regression" / "manifest.json"
MODE = "ai_blue_formal_id_photo"
FREE_RESULT = {"fileId": "free_fixture", "previewUrl": "/free-fixture-preview", "downloadUrl": "/free-fixture-download"}
CORE_QUALITY = {"passed": True, "score": 96}


def assert_true(condition: bool, message: str, payload: Any | None = None) -> None:
    if not condition:
        if payload is not None:
            message = f"{message}\npayload={json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        raise AssertionError(message)


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def write_fixture_image(path: Path, rgb: tuple[int, int, int], size: tuple[int, int]) -> None:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, :] = np.array(rgb, dtype=np.uint8)
    # Add a small center patch so the fixture is not a degenerate single-color file;
    # edge sampling still reflects the requested background.
    h, w = arr.shape[:2]
    arr[h // 3 : h // 3 + max(8, h // 12), w // 3 : w // 3 + max(8, w // 12)] = np.clip(np.array(rgb, dtype=np.int16) - 18, 0, 255)
    Image.fromarray(arr).save(path, format="PNG")


def make_ai_pro() -> dict[str, Any]:
    return {
        "enabled": True,
        "modes": [MODE],
        "promptParams": {"backgroundColor": "blue", "outfit": "dark suit", "retouchLevel": "medium"},
        "consentAccepted": True,
    }


def make_options() -> dict[str, Any]:
    return {"background": "blue", "renderMode": "solid", "width": 295, "height": 413, "dpi": 300}


def assert_fallback_result_uses_free_core(report: dict[str, Any], expected_reason: str) -> None:
    result = build_ai_pro_mock_results(
        "task_fixture_fallback",
        FREE_RESULT,
        make_ai_pro(),
        CORE_QUALITY,
        template_id="cn-id-1inch",
        options=make_options(),
        mode_status={
            MODE: {
                "status": "quality_failed",
                "resultStatus": "quality_failed",
                "metadata": {
                    "qualityGateStatus": "quality_failed",
                    "fallbackToFree": True,
                    "fallbackReason": report.get("fallbackReason"),
                },
            }
        },
    )[0]
    assert_true(result["fallbackToFree"] is True, "AI Pro fallback result should be marked fallbackToFree", result)
    assert_true(result["previewUrl"] == FREE_RESULT["previewUrl"], "fallback preview should reuse Free Core", result)
    assert_true(result["downloadUrl"] == FREE_RESULT["downloadUrl"], "fallback download should reuse Free Core", result)
    assert_true(result["qualityGate"]["fallbackReason"] == expected_reason, "fallback reason should be exposed in result qualityGate", result)
    assert_true(result["promptMetadata"]["fallbackReason"] == expected_reason, "fallback reason should be auditable in promptMetadata", result)


def run_background_pass_fixture(tmp: Path, manifest: dict[str, Any]) -> None:
    target_spec = manifest["targetSpec"]
    blue_rgb = tuple(manifest["targetBackgroundRgb"])
    source = tmp / "blue_pass_source.png"
    candidate = tmp / "blue_pass_candidate.png"
    write_fixture_image(source, blue_rgb, (target_spec["width"], target_spec["height"]))
    write_fixture_image(candidate, blue_rgb, (target_spec["width"], target_spec["height"]))

    report = evaluate_ai_pro_quality(
        ai_image_path=candidate,
        source_image_path=source,
        output_dir=tmp,
        task_id="fixture_bg_pass",
        target_spec=target_spec,
        background_rgb=blue_rgb,
        free_result=FREE_RESULT,
        core_quality_report=CORE_QUALITY,
    )
    assert_true(report["passed"] is True, "matching synthetic blue background should pass", report)
    assert_true(report["fallbackToFree"] is False, "passing fixture should not fallback", report)
    assert_true(report["fallbackReason"] is None, "passing fixture should not carry fallback reason", report)
    assert_true(report["checks"]["backgroundColor"]["meanDelta"] <= 1.0, "background mean delta should be near zero", report)
    assert_true(report["checks"]["identity"]["status"] == "unavailable", "synthetic no-face identity check should warn as unavailable", report)
    assert_true(any(item["code"] == "AI_PRO_IDENTITY_CHECK_UNAVAILABLE" for item in report["warnings"]), "identity unavailable warning should be auditable", report)


def run_background_fallback_fixture(tmp: Path, manifest: dict[str, Any]) -> None:
    target_spec = manifest["targetSpec"]
    blue_rgb = tuple(manifest["targetBackgroundRgb"])
    candidate = tmp / "red_background_candidate.png"
    write_fixture_image(candidate, (255, 0, 0), (target_spec["width"], target_spec["height"]))

    report = evaluate_ai_pro_quality(
        ai_image_path=candidate,
        output_dir=tmp,
        task_id="fixture_bg_fail",
        target_spec=target_spec,
        background_rgb=blue_rgb,
        free_result=FREE_RESULT,
        core_quality_report=CORE_QUALITY,
    )
    assert_true(report["passed"] is False, "severe background drift should fail", report)
    assert_true(report["fallbackToFree"] is True, "background failure should fallback", report)
    assert_true(report["fallbackReason"] == "AI_PRO_BACKGROUND_COLOR_FAILED", "background failure reason should be stable", report)
    assert_fallback_result_uses_free_core(report, "AI_PRO_BACKGROUND_COLOR_FAILED")


def run_identity_drift_fallback_fixture(tmp: Path, manifest: dict[str, Any]) -> None:
    target_spec = manifest["targetSpec"]
    blue_rgb = tuple(manifest["targetBackgroundRgb"])
    source_rgb = (10, 20, 30)
    source = tmp / "identity_source.png"
    candidate = tmp / "identity_candidate.png"
    write_fixture_image(source, source_rgb, (target_spec["width"], target_spec["height"]))
    write_fixture_image(candidate, blue_rgb, (target_spec["width"], target_spec["height"]))

    original_detector = quality_module._detect_face_count

    def fake_detector(image_rgb: np.ndarray):
        first_pixel = tuple(int(v) for v in image_rgb[0, 0, :3])
        if first_pixel == blue_rgb:
            return 1, "fixture_detector", [[150, 170, 70, 90]]
        return 1, "fixture_detector", [[90, 100, 110, 140]]

    quality_module._detect_face_count = fake_detector
    try:
        report = evaluate_ai_pro_quality(
            ai_image_path=candidate,
            source_image_path=source,
            output_dir=tmp,
            task_id="fixture_identity_fail",
            target_spec=target_spec,
            background_rgb=blue_rgb,
            free_result=FREE_RESULT,
            core_quality_report=CORE_QUALITY,
        )
    finally:
        quality_module._detect_face_count = original_detector

    assert_true(report["passed"] is False, "mocked face geometry drift should fail", report)
    assert_true(report["fallbackToFree"] is True, "identity drift should fallback", report)
    assert_true(report["fallbackReason"] == "AI_PRO_IDENTITY_DRIFT_FAILED", "identity fallback reason should be stable", report)
    assert_true(report["checks"]["identity"]["status"] == "failed", "identity check should be failed", report)
    assert_fallback_result_uses_free_core(report, "AI_PRO_IDENTITY_DRIFT_FAILED")


def main() -> None:
    manifest = load_manifest()
    case_ids = {case["id"] for case in manifest.get("cases", [])}
    assert_true(
        {"blue_background_pass_identity_unavailable", "red_background_fails_fallback", "identity_drift_fails_fallback"}.issubset(case_ids),
        "AI Pro regression manifest is missing required cases",
        manifest,
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        run_background_pass_fixture(tmp, manifest)
        run_background_fallback_fixture(tmp, manifest)
        run_identity_drift_fallback_fixture(tmp, manifest)
    print("AI Pro regression fixtures passed: cases=3")


if __name__ == "__main__":
    main()
