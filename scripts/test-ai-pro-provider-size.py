from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hivision.plugin.ai_pro.engine import AIProEngine, AIProEngineConfig  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _clear_env() -> None:
    for key in [
        "AI_PRO_PROVIDER",
        "GPT_IMAGE_PROVIDER",
        "GPT_IMAGE_API_KEY",
        "OPENAI_API_KEY",
        "GPT_IMAGE_API_BASE",
        "OPENAI_BASE_URL",
        "GPT_IMAGE_MODEL",
        "OPENAI_IMAGE_MODEL",
        "GPT_IMAGE_SIZE",
        "GPT_IMAGE_SIZE_POLICY",
    ]:
        os.environ.pop(key, None)


def test_default_provider_size_is_auto() -> None:
    _clear_env()
    config = AIProEngineConfig.from_env()
    engine = AIProEngine(config)

    assert_true(config.image_size == "auto", "default GPT image size should be auto")
    assert_true(config.image_size_policy == "auto", "default GPT image size policy should be auto")
    assert_true(
        engine.resolve_provider_size(target_spec={"width": 295, "height": 413}) == "auto",
        "default provider request size should be auto, not square",
    )


def test_explicit_provider_size_overrides_request() -> None:
    _clear_env()
    os.environ["GPT_IMAGE_API_KEY"] = "test-key"
    os.environ["AI_PRO_PROVIDER"] = "metapi"
    os.environ["GPT_IMAGE_SIZE"] = "1024x1536"
    config = AIProEngineConfig.from_env()
    engine = AIProEngine(config)

    assert_true(config.image_size == "1024x1536", "explicit GPT_IMAGE_SIZE should be parsed")
    assert_true(
        engine.resolve_provider_size(target_spec={"width": 295, "height": 413}) == "1024x1536",
        "explicit GPT_IMAGE_SIZE should override policy and target spec",
    )


def test_match_aspect_policy_selects_portrait_provider_size() -> None:
    config = AIProEngineConfig(provider="metapi", api_base="http://provider.test/v1", api_key="key", image_size="auto", image_size_policy="match-aspect")
    engine = AIProEngine(config)

    assert_true(
        engine.resolve_provider_size(target_spec={"width": 295, "height": 413}) == "1024x1536",
        "match-aspect should choose nearest portrait provider size for ID photo specs",
    )


def test_metadata_contains_provider_size_requested_without_real_provider() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_path = root / "input.png"
        Image.new("RGB", (295, 413), (255, 255, 255)).save(input_path)
        engine = AIProEngine(AIProEngineConfig())

        result = engine.run_blue_formal_id_photo(
            input_path=input_path,
            output_dir=root,
            final_prompt="test prompt",
            template_id="ai_blue_formal_id_photo",
            template_version="v1",
            target_spec={"width": 295, "height": 413},
        )

    assert_true(result.status == "no_credentials", "mock/no credentials path should not call provider")
    assert_true(result.metadata["providerSizeRequested"] == "auto", "metadata should include requested provider size")
    assert_true(result.metadata["providerSizePolicy"] == "auto", "metadata should include provider size policy")


def test_metadata_contains_provider_output_size_with_mocked_provider() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        input_path = root / "input.png"
        output_stub = root / "provider.png"
        Image.new("RGB", (295, 413), (255, 255, 255)).save(input_path)
        Image.new("RGB", (1060, 1484), (98, 139, 206)).save(output_stub)
        output_b64 = base64.b64encode(output_stub.read_bytes()).decode("ascii")
        captured: dict[str, str] = {}

        class CaptureEngine(AIProEngine):
            def _call_provider(self, *, input_path: Path, prompt: str, provider_size: str) -> str:  # type: ignore[override]
                captured["provider_size"] = provider_size
                return output_b64

        engine = CaptureEngine(AIProEngineConfig(provider="metapi", api_base="http://provider.test/v1", api_key="key"))
        result = engine.run_blue_formal_id_photo(
            input_path=input_path,
            output_dir=root,
            final_prompt="test prompt",
            template_id="ai_blue_formal_id_photo",
            template_version="v1",
            target_spec={"width": 295, "height": 413},
        )

    assert_true(result.status == "completed", "mocked provider should complete")
    assert_true(captured["provider_size"] == "auto", "provider request should use auto by default")
    assert_true(result.metadata["providerSizeRequested"] == "auto", "metadata should record requested size")
    assert_true(result.metadata["providerSizeUsed"] == [1060, 1484], "metadata should record actual output dimensions")
    assert_true(abs(result.metadata["providerAspectRatio"] - (1060 / 1484)) < 0.00001, "metadata should record output aspect ratio")


def main() -> None:
    test_default_provider_size_is_auto()
    test_explicit_provider_size_overrides_request()
    test_match_aspect_policy_selects_portrait_provider_size()
    test_metadata_contains_provider_size_requested_without_real_provider()
    test_metadata_contains_provider_output_size_with_mocked_provider()
    print("AI Pro provider size tests passed")


if __name__ == "__main__":
    main()
