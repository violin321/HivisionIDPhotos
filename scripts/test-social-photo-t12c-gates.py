from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import build_ai_pro_results, normalize_ai_pro_request  # noqa: E402
import deploy_api  # noqa: E402
import hivision.plugin.ai_pro.quality as quality_module  # noqa: E402
from hivision.plugin.ai_pro.engine import AIProEngine, AIProEngineConfig  # noqa: E402
from hivision.plugin.ai_pro.quality import evaluate_ai_pro_quality  # noqa: E402

FREE_RESULT = {"fileId": "free_social", "previewUrl": "/free-social-preview", "downloadUrl": "/free-social-download"}
CORE_QUALITY = {"passed": True, "score": 96}


def assert_true(condition: bool, message: str, payload: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{message}: {payload!r}" if payload is not None else message)


def write_social_candidate(path: Path, *, size: tuple[int, int] = (1024, 1024)) -> None:
    width, height = size
    y, x = np.ogrid[:height, :width]
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :] = np.array([216, 222, 230], dtype=np.uint8)
    # Photo-like low-cost texture so realism heuristic has enough variation.
    arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.int16) + ((x + y) % 97) - 32, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1].astype(np.int16) + ((2 * x + y) % 89) - 28, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2].astype(np.int16) + ((x + 2 * y) % 83) - 26, 0, 255)
    stripe = ((x // 18 + y // 23) % 2) == 0
    arr[stripe] = np.clip(arr[stripe].astype(np.int16) + np.array([12, -8, 10], dtype=np.int16), 0, 255)
    cx, cy = width // 2, height // 2
    face = ((x - cx) ** 2 / (width * 0.16) ** 2 + (y - int(height * 0.42)) ** 2 / (height * 0.20) ** 2) <= 1
    torso = ((x - cx) ** 2 / (width * 0.30) ** 2 + (y - int(height * 0.76)) ** 2 / (height * 0.24) ** 2) <= 1
    arr[torso] = np.array([42, 58, 80], dtype=np.uint8)
    arr[face] = np.array([190, 145, 118], dtype=np.uint8)
    Image.fromarray(arr).save(path)


def make_social_request(style: str = "professional_social") -> dict:
    raw = SimpleNamespace(enabled=True, modes=["social_photo"], promptParams={"socialStyle": style, "outputRatio": "1:1"}, consentAccepted=True)
    return normalize_ai_pro_request(raw)


def test_social_photo_quality_gate_exposes_audit_fields_warning_only() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        candidate = tmp / "social.png"
        write_social_candidate(candidate)
        original_detector = quality_module._detect_face_count

        def fake_detector(image_rgb: np.ndarray):
            return 1, "fixture_detector", [[360, 210, 300, 380]]

        quality_module._detect_face_count = fake_detector
        try:
            report = evaluate_ai_pro_quality(
                ai_image_path=candidate,
                source_image_path=candidate,
                output_dir=tmp,
                task_id="task_social_gate",
                target_spec={"width": 1024, "height": 1024, "dpi": 300},
                background_rgb=None,
                free_result=FREE_RESULT,
                core_quality_report=CORE_QUALITY,
                mode="social_photo",
                social_style="professional_social",
            )
        finally:
            quality_module._detect_face_count = original_detector

    assert_true(report["passed"] is True, "valid social_photo fixture should pass", report)
    assert_true(report["checks"]["backgroundColor"]["skipped"] is True, "social_photo should not enforce official background", report)
    assert_true(report["checks"]["composition"]["status"] == "passed", "composition audit should pass with centered face", report)
    assert_true(report["checks"]["realism"]["status"] == "passed", "realism audit should pass textured fixture", report)
    assert_true(report["checks"]["socialPhoto"]["notForOfficialDocument"] is True, "social guard should be explicit", report)


def test_social_photo_composition_and_realism_warnings_do_not_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        candidate = tmp / "flat.png"
        Image.new("RGB", (1024, 1024), (230, 230, 230)).save(candidate)
        report = evaluate_ai_pro_quality(
            ai_image_path=candidate,
            output_dir=tmp,
            task_id="task_social_warning",
            target_spec={"width": 1024, "height": 1024, "dpi": 300},
            background_rgb=None,
            free_result=FREE_RESULT,
            core_quality_report=CORE_QUALITY,
            mode="social_photo",
            social_style="friendly_social",
        )

    warning_codes = {item["code"] for item in report["warnings"]}
    assert_true(report["passed"] is True, "v1 social composition/realism findings should be warning-only", report)
    assert_true(report["fallbackToFree"] is False, "warning-only social gate should not fallback", report)
    assert_true("SOCIAL_PHOTO_COMPOSITION_WARNING" in warning_codes, "composition warning code should be stable", report)
    assert_true("SOCIAL_PHOTO_REALISM_WARNING" in warning_codes, "realism warning code should be stable", report)


def test_social_photo_real_provider_path_uses_square_size_and_quality_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        result_dir = tmp / "task_social_real"
        result_dir.mkdir()
        input_path = result_dir / "official_idcreator.png"
        Image.new("RGB", (295, 413), (255, 255, 255)).save(input_path)
        provider_output = tmp / "provider_social.png"
        write_social_candidate(provider_output)
        output_b64 = base64.b64encode(provider_output.read_bytes()).decode("ascii")
        captured: dict[str, str] = {}

        class CaptureEngine(AIProEngine):
            def _call_provider(self, *, input_path: Path, prompt: str, provider_size: str) -> str:  # type: ignore[override]
                captured["provider_size"] = provider_size
                return output_b64

        original_engine = deploy_api.ai_pro_engine
        original_result_dir = deploy_api.RESULT_DIR
        deploy_api.ai_pro_engine = CaptureEngine(AIProEngineConfig(provider="metapi", api_base="http://provider.test/v1", api_key="key"))
        deploy_api.RESULT_DIR = tmp
        try:
            results, stage = build_ai_pro_results(
                "task_social_real",
                result_dir,
                make_social_request("professional_social"),
                FREE_RESULT,
                CORE_QUALITY,
                options={"background": "white", "width": 295, "height": 413, "dpi": 300},
            )
        finally:
            deploy_api.ai_pro_engine = original_engine
            deploy_api.RESULT_DIR = original_result_dir

    result = results[0]
    assert_true(captured["provider_size"] == "1024x1024", "social_photo provider request should be square")
    assert_true(stage["modeStatuses"]["social_photo"] == "completed", "mocked real social provider path should complete", stage)
    assert_true(result["status"] == "completed", "social provider result should complete", result)
    assert_true(result["promptMetadata"]["providerSizeRequested"] == "1024x1024", "metadata should expose requested provider size", result)
    assert_true(result["promptMetadata"]["providerAspectRatio"] == 1.0, "metadata should expose used provider aspect ratio", result)
    assert_true(result["qualityReport"]["notForOfficialDocument"] is True, "social output should retain notForOfficialDocument", result)
    identity = result["aiQualityReport"]["checks"]["identity"]
    assert_true(result["aiQualityReport"]["checks"]["socialPhoto"]["identityGuard"] is True, "social quality report should retain identity guard", result)
    assert_true(identity["profile"] == "social_photo_square_vs_id_source", "social identity audit should expose square-vs-ID profile", result)
    assert_true(identity["thresholds"]["centerFail"] == 0.16, "social identity center threshold should be auditable even when detector is unavailable", result)
    assert_true(identity["thresholds"]["sizeRatioFail"] == 0.75, "social identity size threshold should be auditable even when detector is unavailable", result)


def main() -> None:
    test_social_photo_quality_gate_exposes_audit_fields_warning_only()
    test_social_photo_composition_and_realism_warnings_do_not_fallback()
    test_social_photo_real_provider_path_uses_square_size_and_quality_gate()
    print("Social photo T12C gate/provider tests passed")


if __name__ == "__main__":
    main()
