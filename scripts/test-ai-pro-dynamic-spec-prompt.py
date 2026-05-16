from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_api import (  # noqa: E402
    PROMPT_TEMPLATE_REGISTRY,
    build_ai_pro_final_prompt,
    build_ai_pro_mock_results,
    resolve_ai_pro_spec_context,
)

MODE = "ai_blue_formal_id_photo"
TEMPLATE = PROMPT_TEMPLATE_REGISTRY[MODE]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_ai_pro(background: str) -> dict:
    return {
        "enabled": True,
        "modes": [MODE],
        "promptParams": {
            "backgroundColor": background,
            "outfit": "dark suit, white shirt",
            "style": "natural",
            "retouchLevel": "medium",
            "outputSpec": "480x640@300dpi",
        },
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


def test_white_prompt_and_metadata_are_not_blue_locked() -> None:
    ai_pro = make_ai_pro("white")
    context = resolve_ai_pro_spec_context("cn-id-1inch", make_options("white"), ai_pro)
    prompt, prompt_hash = build_ai_pro_final_prompt(ai_pro, TEMPLATE, context)
    lowered = prompt.lower()

    assert_true(prompt_hash, "white prompt hash should be populated")
    assert_true("white" in lowered, "white prompt should describe the selected white background")
    assert_true("rgb [255, 255, 255]" in lowered, "white prompt should include white RGB")
    assert_true("#ffffff" in lowered, "white prompt should include white HEX")
    assert_true("blue background" not in lowered, "white prompt must not contain stale 'blue background'")
    assert_true("official blue" not in lowered, "white prompt must not contain stale 'official blue'")
    assert_true("blue-background" not in lowered, "white prompt must not contain stale 'blue-background'")

    mock_result = build_ai_pro_mock_results("task_test", {"previewUrl": "mock", "downloadUrl": "mock"}, ai_pro, {"passed": True}, template_id="cn-id-1inch", options=make_options("white"))[0]
    metadata = mock_result["promptMetadata"]
    spec_profile = metadata["specProfile"]
    assert_true(spec_profile["backgroundColor"] == "white", "metadata specProfile.backgroundColor should be white")
    assert_true(spec_profile["backgroundRgb"] == [255, 255, 255], "metadata should include white RGB")
    assert_true(spec_profile["backgroundHex"] == "#FFFFFF", "metadata should include white HEX")
    assert_true(spec_profile["width"] == 480 and spec_profile["height"] == 640, "metadata should keep requested dimensions")


def test_blue_prompt_and_metadata_remain_blue_when_selected() -> None:
    ai_pro = make_ai_pro("blue")
    context = resolve_ai_pro_spec_context("cn-id-1inch", make_options("blue"), ai_pro)
    prompt, prompt_hash = build_ai_pro_final_prompt(ai_pro, TEMPLATE, context)
    lowered = prompt.lower()

    assert_true(prompt_hash, "blue prompt hash should be populated")
    assert_true("blue" in lowered, "blue prompt should describe blue when selected")
    assert_true("rgb [98, 139, 206]" in lowered, "blue prompt should include configured blue RGB")
    assert_true("#628bce" in lowered, "blue prompt should include configured blue HEX")

    mock_result = build_ai_pro_mock_results("task_test", {"previewUrl": "mock", "downloadUrl": "mock"}, ai_pro, {"passed": True}, template_id="cn-id-1inch", options=make_options("blue"))[0]
    spec_profile = mock_result["promptMetadata"]["specProfile"]
    assert_true(spec_profile["backgroundColor"] == "blue", "metadata specProfile.backgroundColor should be blue")
    assert_true(spec_profile["backgroundRgb"] == [98, 139, 206], "metadata should include configured blue RGB")
    assert_true(spec_profile["backgroundHex"] == "#628BCE", "metadata should include configured blue HEX")


def main() -> None:
    test_white_prompt_and_metadata_are_not_blue_locked()
    test_blue_prompt_and_metadata_remain_blue_when_selected()
    print("AI Pro dynamic spec prompt tests passed")


if __name__ == "__main__":
    main()
