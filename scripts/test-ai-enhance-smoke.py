from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from hivision.plugin.ai_enhance import AIEnhanceOutput, AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.rate_limit import AIEnhanceRateLimiter
from hivision.plugin.ai_enhance.providers.gpt_image2 import GPTImage2Provider
from hivision.plugin.ai_enhance.schemas import AIEnhanceMetadata
from hivision.plugin.ai_enhance.usage import AIEnhanceUsageLogger
from hivision.plugin.ai_enhance.validator import validate_ai_enhance_image
from hivision.utils import numpy_2_base64


class FakeBlueProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        image = np.zeros((512, 512, 3), dtype=np.uint8)
        image[:, :, 0] = 255
        image[:, :, 1] = 20
        image[:, :, 2] = 20
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
            message="fake provider output",
        )


class FakeGoodProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        image = make_input_numpy()
        image[:, :, 1] = np.clip(image[:, :, 1].astype(np.int16) + 2, 0, 255).astype(np.uint8)
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
            message="fake provider output",
        )


class FakeSlowProvider:
    provider_name = "gpt-image-2"

    def __init__(self, sleep_seconds: float = 0.5):
        self.sleep_seconds = sleep_seconds

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        time.sleep(self.sleep_seconds)
        image = make_input_numpy()
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
            message="fake slow provider output",
        )


def make_input_numpy() -> np.ndarray:
    image = np.zeros((400, 300, 3), dtype=np.uint8)
    image[:, :] = (180, 185, 190)
    image[:220, 85:215] = (105, 145, 190)
    image[220:, 45:255] = (50, 55, 65)
    return image


def make_input_base64() -> str:
    return numpy_2_base64(make_input_numpy())


def make_request(**kwargs) -> AIEnhanceRequest:
    base = {
        "input_image_base64": make_input_base64(),
        "mode": "repair",
        "consent": True,
        "return_base64": True,
        "client_id": "smoke-client",
    }
    base.update(kwargs)
    return AIEnhanceRequest(**base)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class EnvGuard:
    def __init__(self, **updates):
        self.updates = updates
        self.original = {}

    def __enter__(self):
        for key, value in self.updates.items():
            self.original[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)
        return self

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class TempUsageLogger(AIEnhanceUsageLogger):
    def __init__(self, path: str, estimated_cost: float | None = None):
        self._path = Path(path)
        self._estimated_cost = estimated_cost

    def enabled(self) -> bool:
        return True

    def log_path(self) -> Path:
        return self._path

    def estimated_cost(self) -> float | None:
        return self._estimated_cost


def test_consent_false() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": FakeGoodProvider()})
    request = make_request(consent=False)
    output = service.enhance(request)
    assert_true(output.status is False, "consent=false should fallback")
    assert_true(output.metadata.error_code == "CONSENT_REQUIRED", "wrong consent error code")
    assert_true(output.metadata.debug_input_path is None, "debug path should be None by default")
    assert_true(output.metadata.validation_passed is False, "consent fallback should not mark validation pass")
    assert_true(output.metadata.request_id is not None, "request_id should be generated")
    assert_true(output.metadata.rate_limited is False, "consent fallback should not mark rate_limited")


def test_outfit_schema_and_consent_fallback_template() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": FakeGoodProvider()})
    request = make_request(mode="outfit", template_name="business_suit_navy", consent=False)
    output = service.enhance(request)
    assert_true(output.status is False, "outfit consent=false should fallback")
    assert_true(output.metadata.mode == "outfit", "outfit mode should be preserved in metadata")
    assert_true(output.metadata.template_name == "business_suit_navy", "outfit template should be preserved on fallback")
    assert_true(output.metadata.error_code == "CONSENT_REQUIRED", "wrong outfit consent error code")


def test_provider_not_configured() -> None:
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        service = AIEnhanceService()
        request = make_request(return_base64=False)
        output = service.enhance(request)
        assert_true(output.status is False, "missing key should fallback")
        assert_true(output.metadata.error_code == "PROVIDER_NOT_CONFIGURED", "wrong provider config error")
        assert_true(output.image_base64 is None, "return_base64=false should not echo image")
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key


def test_validator_blue_cast_detection() -> None:
    blue_image = np.zeros((512, 512, 3), dtype=np.uint8)
    blue_image[:, :, 0] = 255
    blue_image[:, :, 1] = 0
    blue_image[:, :, 2] = 0
    result = validate_ai_enhance_image(numpy_2_base64(blue_image))
    assert_true(result.passed is False, "blue cast should fail validation")
    assert_true(result.error_code == "COLOR_CAST_DETECTED", "wrong blue cast error code")


def test_service_validation_fallback_and_metadata() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": FakeBlueProvider()})
    request = make_request(mode="background_template")
    output = service.enhance(request)
    assert_true(output.status is False, "invalid provider output should fallback")
    assert_true(output.metadata.fallback_reason == "validation_failed", "wrong fallback reason")
    assert_true(output.metadata.error_code == "COLOR_CAST_DETECTED", "wrong validation error")
    assert_true(output.metadata.validation_passed is False, "validation flag should be false")
    assert_true(isinstance(output.metadata.validation_warnings, list), "validation warnings should be list")
    assert_true(output.metadata.usage_logged is True, "usage log should be written by default")


def test_debug_save_paths_and_metadata_file() -> None:
    temp_dir = tempfile.mkdtemp(prefix="ai-enhance-debug-")
    with EnvGuard(AI_ENHANCE_DEBUG_SAVE="1", AI_ENHANCE_DEBUG_DIR=temp_dir):
        service = AIEnhanceService(provider_map={"gpt-image-2": FakeGoodProvider()})
        request = make_request()
        output = service.enhance(request)
        metadata = output.metadata
        assert_true(output.status is True, "good provider should pass validation")
        assert_true(metadata.validation_passed is True, "validation flag should be true")
        assert_true(Path(metadata.debug_input_path).exists(), "debug input should exist")
        assert_true(Path(metadata.debug_output_path).exists(), "debug output should exist")
        assert_true(Path(metadata.debug_metadata_path).exists(), "debug metadata should exist")
        saved = json.loads(Path(metadata.debug_metadata_path).read_text(encoding="utf-8"))
        assert_true(saved["request"]["input_image_base64"] == "<redacted>", "request input should be redacted")
        assert_true(saved["output"]["metadata"]["validation_passed"] is True, "saved metadata should include validation")
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_rate_limit_hit() -> None:
    limiter = AIEnhanceRateLimiter()
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        rate_limiter=limiter,
        usage_logger=TempUsageLogger(usage_file.name, estimated_cost=0.12),
    )
    with EnvGuard(
        AI_ENHANCE_RATE_LIMIT_ENABLED="1",
        AI_ENHANCE_RATE_LIMIT_WINDOW_SECONDS="300",
        AI_ENHANCE_RATE_LIMIT_MAX_REQUESTS="1",
        AI_ENHANCE_MAX_CONCURRENT_REQUESTS="2",
    ):
        first = service.enhance(make_request(client_id="rl-client"))
        second = service.enhance(make_request(client_id="rl-client"))
    assert_true(first.status is True, "first request should pass")
    assert_true(second.status is False, "second request should be rate limited")
    assert_true(second.metadata.error_code == "RATE_LIMITED", "wrong rate limit error")
    assert_true(second.metadata.rate_limited is True, "rate_limited flag should be true")
    assert_true(second.metadata.estimated_cost == 0.12, "estimated cost should be carried")
    os.unlink(usage_file.name)


def test_concurrency_guard() -> None:
    limiter = AIEnhanceRateLimiter()
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeSlowProvider(0.6)},
        rate_limiter=limiter,
        usage_logger=TempUsageLogger(usage_file.name),
    )
    with EnvGuard(
        AI_ENHANCE_RATE_LIMIT_ENABLED="1",
        AI_ENHANCE_RATE_LIMIT_WINDOW_SECONDS="300",
        AI_ENHANCE_RATE_LIMIT_MAX_REQUESTS="10",
        AI_ENHANCE_MAX_CONCURRENT_REQUESTS="1",
    ):
        results = {}

        def run_first():
            results["first"] = service.enhance(make_request(client_id="cc-client"))

        thread = threading.Thread(target=run_first)
        thread.start()
        time.sleep(0.1)
        second = service.enhance(make_request(client_id="cc-client"))
        thread.join()

    assert_true(results["first"].status is True, "first concurrent request should complete")
    assert_true(second.status is False, "second concurrent request should be blocked")
    assert_true(second.metadata.error_code == "TOO_MANY_CONCURRENT_REQUESTS", "wrong concurrency error")
    assert_true(second.metadata.rate_limited is True, "concurrency block should set rate_limited")
    os.unlink(usage_file.name)


def test_usage_log_and_no_base64() -> None:
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        usage_logger=TempUsageLogger(usage_file.name, estimated_cost=0.34),
    )
    output = service.enhance(make_request(client_id="usage-client"))
    assert_true(output.metadata.usage_logged is True, "usage log should report success")
    lines = Path(usage_file.name).read_text(encoding="utf-8").strip().splitlines()
    assert_true(len(lines) >= 1, "usage log should have at least one line")
    payload = json.loads(lines[-1])
    assert_true(payload["request_id"] == output.metadata.request_id, "request_id should match")
    assert_true(payload["estimated_cost"] == 0.34, "estimated cost should be logged")
    serialized = json.dumps(payload, ensure_ascii=False)
    assert_true("base64" not in serialized.lower(), "usage log must not contain base64 data")
    os.unlink(usage_file.name)


def test_outfit_template_usage_log_and_prompt() -> None:
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        usage_logger=TempUsageLogger(usage_file.name, estimated_cost=0.78),
    )
    output = service.enhance(make_request(mode="outfit", template_name="business_suit_black", client_id="outfit-client"))
    assert_true(output.status is True, "outfit good provider should pass")
    assert_true(output.metadata.mode == "outfit", "outfit mode should be recorded")
    assert_true(output.metadata.template_name == "business_suit_black", "outfit template should pass through metadata")
    lines = Path(usage_file.name).read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert_true(payload["mode"] == "outfit", "usage log should record outfit mode")
    assert_true(payload["template_name"] == "business_suit_black", "usage log should record outfit template")

    prompt = GPTImage2Provider()._build_prompt(make_request(mode="outfit", template_name="business_suit_black"))
    prompt_lower = prompt.lower()
    assert_true("Target outfit template: business_suit_black" in prompt, "outfit prompt should include template name")
    assert_true("replace only the visible upper-body clothing" in prompt_lower, "outfit prompt should constrain clothing-only edits")
    assert_true("lapels, shoulders, outer coat edges" in prompt_lower, "outfit prompt should request complete jacket replacement")
    assert_true("blend the collar/neck boundary naturally" in prompt_lower, "outfit prompt should request natural neck/collar blending")
    assert_true("background unchanged" in prompt_lower, "outfit prompt should preserve background")
    for forbidden in ("portrait", "profile", "preview", "resume"):
        assert_true(forbidden not in prompt_lower, f"outfit prompt should not contain '{forbidden}'")
    assert_true(output.metadata.crop_edit is True, "outfit metadata should record crop_edit")
    assert_true(output.metadata.face_protected is True, "outfit metadata should record face protection")
    os.unlink(usage_file.name)


def test_social_photo_template_usage_log_prompt_and_metadata() -> None:
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        usage_logger=TempUsageLogger(usage_file.name, estimated_cost=0.91),
    )
    output = service.enhance(make_request(mode="social_photo", template_name="resume_clean", client_id="social-client"))
    assert_true(output.status is True, "social_photo good provider should pass")
    assert_true(output.metadata.mode == "social_photo", "social_photo mode should be recorded")
    assert_true(output.metadata.template_name == "resume_clean", "social_photo template should pass through metadata")
    assert_true(output.metadata.prompt_template_key == "social_photo:v1:resume_clean", "social_photo key should include concrete template")
    assert_true(output.metadata.prompt_template_version == "v1", "social_photo template version should be v1")
    assert_true(bool(output.metadata.prompt_template_hash), "social_photo prompt hash should be recorded")
    assert_true(output.metadata.identity_guard_passed is True, "social_photo should run identity guard")
    assert_true(output.metadata.face_protected is True, "social_photo should mark face protection")

    payload = json.loads(Path(usage_file.name).read_text(encoding="utf-8").strip().splitlines()[-1])
    assert_true(payload["mode"] == "social_photo", "usage log should record social_photo mode")
    assert_true(payload["template_name"] == "resume_clean", "usage log should record social_photo template")
    assert_true(payload["prompt_template_key"] == "social_photo:v1:resume_clean", "usage log should record social_photo prompt key")
    assert_true(payload["prompt_template_version"] == "v1", "usage log should record social_photo version")
    assert_true(bool(payload["prompt_template_hash"]), "usage log should record social_photo hash")

    prompt = GPTImage2Provider()._build_prompt(make_request(mode="social_photo", template_name="resume_clean"))
    prompt_lower = prompt.lower()
    assert_true("Target social_photo template: resume_clean" in prompt, "social_photo prompt should include template name")
    for required in ("informal use only", "preserve", "face shape", "facial features", "age", "hairstyle", "not an official id photo", "do not", "exaggerated beautification"):
        assert_true(required in prompt_lower, f"social_photo prompt should contain '{required}'")
    os.unlink(usage_file.name)


def test_metadata_fields_exist() -> None:
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        usage_logger=TempUsageLogger(usage_file.name, estimated_cost=0.56),
    )
    output = service.enhance(make_request(client_id="meta-client"))
    metadata = output.metadata
    assert_true(metadata.request_id is not None, "request_id missing")
    assert_true(metadata.estimated_cost == 0.56, "estimated_cost missing")
    assert_true(metadata.rate_limited is False, "rate_limited should be false for success")
    assert_true(metadata.usage_logged is True, "usage_logged should be true")
    assert_true(bool(metadata.prompt_template_key), "prompt_template_key missing")
    assert_true(bool(metadata.prompt_template_version), "prompt_template_version missing")
    assert_true(bool(metadata.prompt_template_hash), "prompt_template_hash missing")
    assert_true(metadata.prompt_template_version == "v1", "default prompt template version should be v1")
    os.unlink(usage_file.name)


def test_identity_guard_metadata_and_usage_log() -> None:
    usage_file = tempfile.NamedTemporaryFile(prefix="ai-usage-", suffix=".jsonl", delete=False)
    usage_file.close()
    service = AIEnhanceService(
        provider_map={"gpt-image-2": FakeGoodProvider()},
        usage_logger=TempUsageLogger(usage_file.name),
    )
    output = service.enhance(make_request(mode="repair", client_id="identity-meta-client"))
    assert_true(output.status is True, "identity-guarded repair should pass")
    assert_true(output.metadata.identity_guard_passed is True, "identity guard should pass")
    assert_true(output.metadata.face_protected is True, "repair should mark face protection")
    assert_true("protected_mean_delta" in output.metadata.identity_guard_metrics, "guard metrics missing")
    payload = json.loads(Path(usage_file.name).read_text(encoding="utf-8").strip().splitlines()[-1])
    assert_true(payload["identity_guard_passed"] is True, "usage log should include guard result")
    assert_true("identity_guard_metrics" in payload, "usage log should include guard metrics")
    os.unlink(usage_file.name)


def main() -> None:
    test_consent_false()
    test_outfit_schema_and_consent_fallback_template()
    test_provider_not_configured()
    test_validator_blue_cast_detection()
    test_service_validation_fallback_and_metadata()
    test_debug_save_paths_and_metadata_file()
    test_rate_limit_hit()
    test_concurrency_guard()
    test_usage_log_and_no_base64()
    test_outfit_template_usage_log_and_prompt()
    test_social_photo_template_usage_log_prompt_and_metadata()
    test_metadata_fields_exist()
    test_identity_guard_metadata_and_usage_log()
    print("AI enhance smoke tests passed")


if __name__ == "__main__":
    main()
