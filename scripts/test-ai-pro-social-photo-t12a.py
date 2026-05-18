from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from deploy_api import build_ai_pro_mock_results, normalize_ai_pro_request  # noqa: E402
from hivision.plugin.ai_pro.prompts import build_ai_pro_prompt, resolve_prompt_template  # noqa: E402


def assert_true(condition: bool, message: str, payload: object | None = None) -> None:
    if not condition:
        raise AssertionError(f"{message}: {payload!r}" if payload is not None else message)


def make_request(style: str, *, custom_prompt: str | None = None):
    params = {"socialStyle": style, "outputRatio": "1:1"}
    if custom_prompt is not None:
        params["customPrompt"] = custom_prompt
    return SimpleNamespace(
        enabled=True,
        modes=["social_photo"],
        promptParams=params,
        consentAccepted=True,
    )


def normalize(style: str) -> dict:
    return normalize_ai_pro_request(make_request(style))


def test_professional_social_valid() -> None:
    ai_pro = normalize("professional_social")
    resolution = resolve_prompt_template("social_photo", user_params=ai_pro["promptParams"])
    built = build_ai_pro_prompt(mode="social_photo", ai_pro=ai_pro, template=resolution.template)
    prompt = built.prompt.lower()
    assert_true(resolution.mode == "social_photo", "mode should resolve to social_photo")
    assert_true(resolution.prompt_template_id == "professional_social", "professional style should select professional template")
    for required in ("identity", "realistic", "do not reshape", "do not redraw", "preserve exact facial geometry", "age", "gender", "not an official id photo"):
        assert_true(required in prompt, f"prompt should include guard phrase {required!r}")
    for risky in ("studio portrait", "executive headshot"):
        assert_true(risky not in prompt, f"social prompt should avoid heavy redraw cue {risky!r}")


def test_friendly_social_valid() -> None:
    ai_pro = normalize("friendly_social")
    resolution = resolve_prompt_template("social_photo", user_params=ai_pro["promptParams"])
    built = build_ai_pro_prompt(mode="social_photo", ai_pro=ai_pro, template=resolution.template)
    assert_true(resolution.prompt_template_id == "friendly_social", "friendly style should select friendly template")
    assert_true("friendly" in built.prompt.lower(), "friendly prompt should include style direction")


def test_invalid_social_style_rejected() -> None:
    try:
        normalize("glamour_freeform")
    except HTTPException as exc:
        detail = exc.detail.get("error", {}) if isinstance(exc.detail, dict) else {}
        assert_true(exc.status_code == 400, "invalid socialStyle should be 400")
        assert_true(detail.get("code") == "UNSUPPORTED_SOCIAL_STYLE", "invalid socialStyle should expose stable code")
        return
    raise AssertionError("invalid socialStyle should be rejected")


def test_custom_prompt_rejected_for_social_photo() -> None:
    try:
        normalize_ai_pro_request(make_request("professional_social", custom_prompt="make me look like a movie star"))
    except HTTPException as exc:
        detail = exc.detail.get("error", {}) if isinstance(exc.detail, dict) else {}
        assert_true(exc.status_code == 400, "custom/free prompt should be 400")
        assert_true(detail.get("code") == "SOCIAL_PHOTO_CUSTOM_PROMPT_UNSUPPORTED", "custom/free prompt should expose stable code")
        return
    raise AssertionError("custom/free prompt should be rejected for social_photo")


def test_quality_mock_report_contains_social_audit_fields() -> None:
    ai_pro = normalize("friendly_social")
    result = build_ai_pro_mock_results(
        "task_social",
        {"previewUrl": "mock-preview", "downloadUrl": "mock-download"},
        ai_pro,
        {"passed": True},
        template_id="cn-id-1inch",
        options={"background": "white", "renderMode": "solid"},
    )[0]
    assert_true(result["mode"] == "social_photo", "mock result mode should remain social_photo")
    assert_true(result["promptTemplateId"] == "friendly_social", "mock result should expose selected style template")
    report = result["qualityReport"]
    metadata = result["promptMetadata"]
    assert_true(report["mode"] == "social_photo", "quality report should include mode", report)
    assert_true(report["style"] == "friendly_social", "quality report should include style", report)
    assert_true(report["notForOfficialDocument"] is True, "quality report should include notForOfficialDocument", report)
    assert_true(metadata["mode"] == "social_photo", "metadata should include social_photo mode", metadata)
    assert_true(metadata["socialStyle"] == "friendly_social", "metadata should include style", metadata)
    assert_true(metadata["notForOfficialDocument"] is True, "metadata should mark not official", metadata)
    assert_true(metadata["noFaceReshaping"] is True, "metadata should include identity guard field", metadata)


def test_id_photo_existing_path_unchanged() -> None:
    request = SimpleNamespace(enabled=True, modes=["ai_blue_formal_id_photo"], promptParams={"backgroundColor": "blue"}, consentAccepted=True)
    ai_pro = normalize_ai_pro_request(request)
    assert_true(ai_pro["modes"] == ["ai_blue_formal_id_photo"], "id_photo AI Pro mode should remain supported")
    resolution = resolve_prompt_template("ai_blue_formal_id_photo", user_params=ai_pro["promptParams"])
    assert_true(resolution.prompt_template_id == "ai_blue_formal_id_photo", "id_photo prompt template should be unchanged")


def main() -> None:
    test_professional_social_valid()
    test_friendly_social_valid()
    test_invalid_social_style_rejected()
    test_custom_prompt_rejected_for_social_photo()
    test_quality_mock_report_contains_social_audit_fields()
    test_id_photo_existing_path_unchanged()
    print("AI Pro social_photo T12A tests passed")


if __name__ == "__main__":
    main()
