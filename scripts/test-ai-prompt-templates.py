from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from hivision.plugin.ai_enhance import AIEnhanceOutput, AIEnhanceRequest, AIEnhanceService
from hivision.plugin.ai_enhance.errors import AIEnhanceValidationError
from hivision.plugin.ai_enhance.prompt_templates import render_prompt_template
from hivision.plugin.ai_enhance.schemas import AIEnhanceMetadata
from hivision.utils import numpy_2_base64


class EchoProvider:
    provider_name = "gpt-image-2"

    def is_configured(self) -> bool:
        return True

    def enhance(self, request: AIEnhanceRequest) -> AIEnhanceOutput:
        image = base_image()
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
            message="echo provider output",
        )


def base_image() -> np.ndarray:
    image = np.zeros((400, 300, 3), dtype=np.uint8)
    image[:, :] = (180, 185, 190)
    image[:220, 85:215] = (105, 145, 190)
    image[220:, 45:255] = (50, 55, 65)
    return image


def make_request(**kwargs) -> AIEnhanceRequest:
    base = {
        "input_image_base64": numpy_2_base64(base_image()),
        "mode": "repair",
        "consent": True,
        "return_base64": True,
        "client_id": "prompt-template-test",
    }
    base.update(kwargs)
    return AIEnhanceRequest(**base)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_metadata_has_prompt_template(output: AIEnhanceOutput) -> None:
    metadata = output.metadata
    assert_true(bool(metadata.prompt_template_key), "metadata.prompt_template_key should be non-empty")
    assert_true(bool(metadata.prompt_template_version), "metadata.prompt_template_version should be non-empty")
    assert_true(bool(metadata.prompt_template_hash), "metadata.prompt_template_hash should be non-empty")


def test_success_metadata_records_default_v1() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    output = service.enhance(make_request(prompt_version=None))
    assert_true(output.status is True, "default prompt_version request should pass")
    assert_metadata_has_prompt_template(output)
    assert_true(output.metadata.prompt_template_key == "repair:v1", "default key should be repair:v1")
    assert_true(output.metadata.prompt_template_version == "v1", "missing prompt_version should default to v1")


def test_fallback_metadata_records_prompt_template() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    output = service.enhance(make_request(consent=False))
    assert_true(output.status is False, "consent=false should fallback")
    assert_metadata_has_prompt_template(output)
    assert_true(output.metadata.prompt_template_key == "repair:v1", "fallback key should be repair:v1")
    assert_true(output.metadata.prompt_template_version == "v1", "fallback should record default v1")


def test_outfit_black_and_navy_keys_and_hashes_are_distinct() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    black = service.enhance(make_request(mode="outfit", template_name="business_suit_black"))
    navy = service.enhance(make_request(mode="outfit", template_name="business_suit_navy"))

    assert_true(black.status is True, "black outfit request should pass")
    assert_true(navy.status is True, "navy outfit request should pass")
    assert_metadata_has_prompt_template(black)
    assert_metadata_has_prompt_template(navy)

    assert_true(black.metadata.template_name == "business_suit_black", "black template_name should be recorded")
    assert_true(navy.metadata.template_name == "business_suit_navy", "navy template_name should be recorded")
    assert_true(
        black.metadata.prompt_template_key == "outfit:v1:business_suit_black",
        "black outfit key should include concrete template",
    )
    assert_true(
        navy.metadata.prompt_template_key == "outfit:v1:business_suit_navy",
        "navy outfit key should include concrete template",
    )
    assert_true(
        black.metadata.prompt_template_key != navy.metadata.prompt_template_key,
        "black/navy outfit keys should be distinct",
    )
    assert_true(
        black.metadata.prompt_template_hash != navy.metadata.prompt_template_hash,
        "black/navy outfit hashes should be distinct",
    )


def test_render_prompt_template_distinguishes_outfits() -> None:
    black = render_prompt_template(mode="outfit", template_name="business_suit_black")
    navy = render_prompt_template(mode="outfit", template_name="business_suit_navy")
    assert_true(black.version == "v1", "render default version should be v1")
    assert_true(navy.version == "v1", "render default version should be v1")
    assert_true(black.key != navy.key, "rendered outfit keys should be distinct")
    assert_true(black.hash != navy.hash, "rendered outfit hashes should be distinct")
    assert_true("business_suit_black" in black.prompt, "black prompt should include template name")
    assert_true("business_suit_navy" in navy.prompt, "navy prompt should include template name")


def test_social_photo_templates_keys_and_hashes_are_distinct() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    outputs = [
        service.enhance(make_request(mode="social_photo", template_name=name))
        for name in ("resume_clean", "linkedin_professional", "soft_profile")
    ]
    for output, name in zip(outputs, ("resume_clean", "linkedin_professional", "soft_profile")):
        assert_true(output.status is True, f"{name} social_photo request should pass")
        assert_metadata_has_prompt_template(output)
        assert_true(output.metadata.template_name == name, f"{name} template_name should be recorded")
        assert_true(output.metadata.prompt_template_key == f"social_photo:v1:{name}", f"{name} key should include concrete template")
    keys = {output.metadata.prompt_template_key for output in outputs}
    hashes = {output.metadata.prompt_template_hash for output in outputs}
    assert_true(len(keys) == 3, "social_photo template keys should be distinct")
    assert_true(len(hashes) == 3, "social_photo template hashes should be distinct")


def test_render_prompt_template_distinguishes_social_photo_templates() -> None:
    rendered = [
        render_prompt_template(mode="social_photo", template_name=name)
        for name in ("resume_clean", "linkedin_professional", "soft_profile")
    ]
    assert_true({item.version for item in rendered} == {"v1"}, "social_photo default version should be v1")
    assert_true(len({item.key for item in rendered}) == 3, "rendered social_photo keys should be distinct")
    assert_true(len({item.hash for item in rendered}) == 3, "rendered social_photo hashes should be distinct")
    for item, name in zip(rendered, ("resume_clean", "linkedin_professional", "soft_profile")):
        assert_true(name in item.prompt, f"{name} prompt should include template name")


def test_unknown_social_photo_template_is_controlled_validation_error() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    try:
        service.enhance(make_request(mode="social_photo", template_name="unknown_template"))
    except AIEnhanceValidationError as exc:
        message = str(exc)
        assert_true("unsupported social_photo template_name" in message, "unknown template should explain unsupported template_name")
        assert_true("unknown_template" in message, "unknown template error should include rejected template")
        return
    raise AssertionError("unknown social_photo template should raise AIEnhanceValidationError")


def test_unknown_prompt_version_is_controlled_validation_error() -> None:
    service = AIEnhanceService(provider_map={"gpt-image-2": EchoProvider()})
    try:
        service.enhance(make_request(prompt_version="v999"))
    except AIEnhanceValidationError as exc:
        message = str(exc)
        assert_true("unsupported prompt_version" in message, "unknown version should explain unsupported prompt_version")
        assert_true("v999" in message, "unknown version error should include rejected version")
        return
    raise AssertionError("unknown prompt_version should raise AIEnhanceValidationError")


def main() -> None:
    test_success_metadata_records_default_v1()
    test_fallback_metadata_records_prompt_template()
    test_outfit_black_and_navy_keys_and_hashes_are_distinct()
    test_render_prompt_template_distinguishes_outfits()
    test_social_photo_templates_keys_and_hashes_are_distinct()
    test_render_prompt_template_distinguishes_social_photo_templates()
    test_unknown_social_photo_template_is_controlled_validation_error()
    test_unknown_prompt_version_is_controlled_validation_error()
    print("AI prompt template tests passed")


if __name__ == "__main__":
    main()
