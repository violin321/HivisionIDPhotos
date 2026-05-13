from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from hivision.utils import base64_2_numpy


@dataclass
class AIEnhanceValidationResult:
    passed: bool
    warnings: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None


def validate_ai_enhance_image(image_base64: str) -> AIEnhanceValidationResult:
    try:
        image = base64_2_numpy(image_base64)
    except Exception as exc:
        return AIEnhanceValidationResult(
            passed=False,
            error_code="IMAGE_DECODE_FAILED",
            message=f"Failed to decode provider image: {exc}",
        )

    if image is None:
        return AIEnhanceValidationResult(
            passed=False,
            error_code="IMAGE_DECODE_FAILED",
            message="Provider image could not be decoded",
        )

    if image.ndim != 3:
        return AIEnhanceValidationResult(
            passed=False,
            error_code="BAD_IMAGE_SHAPE",
            message=f"Provider image shape is invalid: {getattr(image, 'shape', None)}",
        )

    height, width, channels = image.shape
    result = AIEnhanceValidationResult(
        passed=True,
        width=width,
        height=height,
        channels=channels,
    )

    if channels not in (3, 4):
        result.passed = False
        result.error_code = "BAD_IMAGE_CHANNELS"
        result.message = f"Provider image channel count is invalid: {channels}"
        return result

    if min(height, width) < 128 or max(height, width) > 4096:
        result.passed = False
        result.error_code = "BAD_IMAGE_SHAPE"
        result.message = f"Provider image resolution is out of range: {width}x{height}"
        return result

    aspect_ratio = width / float(height)
    if aspect_ratio < 0.4 or aspect_ratio > 2.5:
        result.warnings.append(f"unusual_aspect_ratio:{width}x{height}")

    bgr = image[:, :, :3].astype(np.float32)
    mean_b, mean_g, mean_r = bgr.mean(axis=(0, 1))

    if mean_b > mean_g * 1.15 and mean_b > mean_r * 1.3 and (mean_b - mean_r) > 25:
        result.passed = False
        result.error_code = "COLOR_CAST_DETECTED"
        result.message = (
            "Provider image has obvious blue color cast "
            f"(mean_b={mean_b:.1f}, mean_g={mean_g:.1f}, mean_r={mean_r:.1f})"
        )
        return result

    if mean_b > mean_g * 1.08 and mean_b > mean_r * 1.15 and (mean_b - mean_r) > 12:
        result.warnings.append(
            "mild_blue_cast:"
            f"mean_b={mean_b:.1f},mean_g={mean_g:.1f},mean_r={mean_r:.1f}"
        )

    return result
