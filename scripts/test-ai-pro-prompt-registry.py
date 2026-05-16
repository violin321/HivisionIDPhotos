from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import build_ai_pro_mock_results, resolve_ai_pro_spec_context  # noqa: E402
from hivision.plugin.ai_pro.prompts import (  # noqa: E402
    DEFAULT_PROMPT_VERSION,
    build_ai_pro_prompt,
    resolve_prompt_template,
)

MODE = "ai_blue_formal_id_photo"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_ai_pro(background: str = "white", prompt_version: str | None = None, mode: str = MODE) -> dict:
    params = {
        "backgroundColor": background,
        "outfit": "dark suit, white shirt",
        "style": "natural",
        "retouchLevel": "medium",
    }
    if prompt_version:
        params["promptVersion"] = prompt_version
    return {
        "enabled": True,
        "modes": [mode],
        "promptParams": params,
        "consentAccepted": True,
    }


def make_options(background: str) -> dict:
    return {
        "background": background,
        "renderMode": "solid",
        "width": 480,
        "height": 640,
        "dpi": 300,
    }


def test_default_and_explicit_version_resolution() -> None:
    default_resolution = resolve_prompt_template(MODE)
    explicit_resolution = resolve_prompt_template(MODE, DEFAULT_PROMPT_VERSION)
    assert_true(default_resolution.prompt_version == DEFAULT_PROMPT_VERSION, "default version should be stable")
    assert_true(explicit_resolution.prompt_version == DEFAULT_PROMPT_VERSION, "explicit version should resolve")
    assert_true(default_resolution.prompt_template_id == "ai_blue_formal_id_photo", "mode should map to ID photo template")
    assert_true(default_resolution.prompt_template_hash == explicit_resolution.prompt_template_hash, "template hash should be stable")


def test_unknown_version_and_mode_fallback_are_controlled() -> None:
    version_fallback = resolve_prompt_template(MODE, "2099-experimental")
    assert_true(version_fallback.prompt_version == DEFAULT_PROMPT_VERSION, "unknown version should fallback to stable default")
    assert_true("unknown_version" in (version_fallback.fallback_reason or ""), "unknown version fallback should be auditable")

    mode_fallback = resolve_prompt_template("does_not_exist", "bad-version")
    assert_true(mode_fallback.prompt_template_id == "ai_repair_basic", "unknown mode should fallback to safe repair template")
    assert_true("unknown_mode" in (mode_fallback.fallback_reason or ""), "unknown mode fallback should be recorded")


def test_legacy_mode_aliases() -> None:
    repair = resolve_prompt_template("repair")
    background = resolve_prompt_template("background_template")
    outfit = resolve_prompt_template("outfit")
    assert_true(repair.mode == "ai_repair", "repair alias should map to ai_repair")
    assert_true(background.mode == "ai_blue_formal_id_photo", "background_template alias should map to ID-photo enhancement")
    assert_true(outfit.mode == "executive_headshot", "outfit alias should map to non-official portrait template")


def test_prompt_build_and_metadata_for_white_and_blue() -> None:
    hashes: list[str] = []
    for background in ("white", "blue"):
        ai_pro = make_ai_pro(background)
        context = resolve_ai_pro_spec_context("cn-id-1inch", make_options(background), ai_pro)
        resolution = resolve_prompt_template(MODE)
        built = build_ai_pro_prompt(mode=MODE, ai_pro=ai_pro, template=resolution.template, spec_context=context)
        metadata = built.metadata
        hashes.append(built.prompt_hash)
        assert_true(metadata["promptTemplateId"] == "ai_blue_formal_id_photo", "metadata should include template id")
        assert_true(metadata["promptVersion"] == DEFAULT_PROMPT_VERSION, "metadata should include prompt version")
        assert_true(metadata["promptHash"] == built.prompt_hash, "metadata should include prompt hash")
        assert_true(metadata["promptTemplateHash"] == built.prompt_template_hash, "metadata should include template hash")
        assert_true(context["specProfile"]["backgroundColor"] == background, "spec context should follow selected background")

    assert_true(hashes[0] != hashes[1], "white/blue prompts should hash differently because spec context differs")


def test_result_metadata_contains_audit_fields_and_fallback_reason() -> None:
    ai_pro = make_ai_pro("white", prompt_version="unknown-version")
    result = build_ai_pro_mock_results("task_test", {"previewUrl": "mock", "downloadUrl": "mock"}, ai_pro, {"passed": True}, template_id="cn-id-1inch", options=make_options("white"))[0]
    metadata = result["promptMetadata"]
    assert_true(metadata["promptTemplateId"] == result["promptTemplateId"], "result metadata should mirror template id")
    assert_true(metadata["promptVersion"] == result["templateVersion"], "result metadata should mirror template version")
    assert_true(bool(metadata["promptHash"]), "result metadata should include prompt hash")
    assert_true(bool(metadata["promptTemplateHash"]), "result metadata should include template hash")
    assert_true("unknown_version" in (metadata.get("fallbackReason") or ""), "version fallback should be in metadata")
    assert_true(metadata["backgroundColor"] == "white", "white metadata should remain white")


def main() -> None:
    test_default_and_explicit_version_resolution()
    test_unknown_version_and_mode_fallback_are_controlled()
    test_legacy_mode_aliases()
    test_prompt_build_and_metadata_for_white_and_blue()
    test_result_metadata_contains_audit_fields_and_fallback_reason()
    print("AI Pro prompt registry tests passed")


if __name__ == "__main__":
    main()
