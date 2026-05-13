from __future__ import annotations

import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.processor import IDPhotoProcessor  # noqa: E402
from hivision.plugin.ai_enhance import AIEnhanceMetadata, AIEnhanceOutput  # noqa: E402
from hivision.utils import numpy_2_base64  # noqa: E402


class FakeFallbackService:
    def enhance(self, request):
        return AIEnhanceOutput(
            status=False,
            image_base64=request.input_image_base64,
            metadata=AIEnhanceMetadata(
                fallback_used=True,
                fallback_reason="validation_failed",
                error_code="COLOR_CAST_DETECTED",
                latency_ms=12,
                provider=request.provider,
                mode=request.mode,
                ai_generated=False,
                validation_passed=False,
                template_name=request.template_name,
            ),
            message="AI enhancement fallback used because provider output failed validation: COLOR_CAST_DETECTED",
        )


class FakeSuccessService:
    def enhance(self, request):
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        image[:, :] = (180, 175, 170)
        return AIEnhanceOutput(
            status=True,
            image_base64=numpy_2_base64(image),
            metadata=AIEnhanceMetadata(
                fallback_used=False,
                fallback_reason=None,
                error_code=None,
                latency_ms=12,
                provider=request.provider,
                mode=request.mode,
                ai_generated=True,
                validation_passed=True,
                template_name=request.template_name,
            ),
            message="ok",
        )


def update_value(update):
    return update.get("value")


def test_fallback_does_not_show_echoed_input_as_output() -> None:
    processor = IDPhotoProcessor()
    processor.ai_enhance_service = FakeFallbackService()
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :] = (255, 0, 0)

    input_update, output_update, status_update = processor._run_ai_enhance_preview(
        image,
        "zh",
        enable_ai_enhance=True,
        ai_consent=True,
        ai_mode="outfit",
        ai_template_name="business_suit_black",
    )

    assert update_value(input_update) is not None, "input preview should still show the provider input"
    assert update_value(output_update) is None, "fallback must not show echoed input as AI output preview"
    status_text = update_value(status_update)
    assert "AI 输出未通过质量门禁，已回退，不展示为成功输出" in status_text
    assert "AI 输出检测到明显色偏，已回退" in status_text
    assert "error=COLOR_CAST_DETECTED" in status_text


def test_success_still_shows_output_preview() -> None:
    processor = IDPhotoProcessor()
    processor.ai_enhance_service = FakeSuccessService()
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :] = (255, 0, 0)

    input_update, output_update, status_update = processor._run_ai_enhance_preview(
        image,
        "zh",
        enable_ai_enhance=True,
        ai_consent=True,
    )

    assert update_value(input_update) is not None, "input preview should show on success"
    assert update_value(output_update) is not None, "successful AI output preview should still be shown"
    assert "AI 增强预览已生成" in update_value(status_update)


if __name__ == "__main__":
    test_fallback_does_not_show_echoed_input_as_output()
    test_success_still_shows_output_preview()
    print("AI preview fallback display checks passed")
