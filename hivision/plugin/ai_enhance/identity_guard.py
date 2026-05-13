from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from hivision.utils import base64_2_numpy


@dataclass(frozen=True)
class IdentityGuardResult:
    passed: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    message: Optional[str] = None


# Conservative, model-free guard for ID-photo AI edits.  It intentionally uses
# broad portrait geometry instead of external face models so validation can run
# offline and never changes the normal IDCreator pipeline.
def validate_identity_structure_guard(
    original_base64: str,
    candidate_base64: str,
    mode: str,
    edit_region: Optional[dict] = None,
) -> IdentityGuardResult:
    original = _decode_image(original_base64)
    candidate = _decode_image(candidate_base64)
    if original is None or candidate is None:
        return IdentityGuardResult(
            passed=False,
            metrics={"decode_failed": True},
            error_code="IDENTITY_GUARD_DECODE_FAILED",
            message="Cannot decode image for identity/structure guard",
        )

    if original.shape[:2] != candidate.shape[:2]:
        candidate = cv2.resize(candidate, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_AREA)

    height, width = original.shape[:2]
    if height <= 0 or width <= 0:
        return IdentityGuardResult(
            passed=False,
            metrics={"bad_shape": True},
            error_code="IDENTITY_GUARD_BAD_IMAGE_SHAPE",
            message="Image shape is invalid for identity/structure guard",
        )

    protected_mask = _protected_region_mask(height, width, mode, edit_region)
    background_mask = _background_spill_mask(height, width)
    editable_mask = _editable_mask(height, width, mode, edit_region)

    abs_delta = np.abs(candidate[:, :, :3].astype(np.int16) - original[:, :, :3].astype(np.int16))
    luma_delta = _luma_delta(original, candidate)
    changed_mask = luma_delta > 18.0

    protected_pixels = max(1, int(protected_mask.sum()))
    background_pixels = max(1, int(background_mask.sum()))
    all_pixels = height * width
    non_edit_mask = ~editable_mask

    protected_mean_delta = float(abs_delta[protected_mask].mean()) if protected_mask.any() else 0.0
    protected_p95_delta = float(np.percentile(luma_delta[protected_mask], 95)) if protected_mask.any() else 0.0
    protected_changed_ratio = float(np.logical_and(changed_mask, protected_mask).sum()) / float(protected_pixels)
    background_changed_ratio = float(np.logical_and(changed_mask, background_mask).sum()) / float(background_pixels)
    total_changed_ratio = float(changed_mask.sum()) / float(all_pixels)
    non_edit_changed_ratio = float(np.logical_and(changed_mask, non_edit_mask).sum()) / float(max(1, int(non_edit_mask.sum())))

    orig_gray = cv2.cvtColor(original[:, :, :3], cv2.COLOR_BGR2GRAY)
    cand_gray = cv2.cvtColor(candidate[:, :, :3], cv2.COLOR_BGR2GRAY)
    protected_edge_delta = 0.0
    if protected_mask.any():
        orig_edges = cv2.Canny(orig_gray, 50, 150)
        cand_edges = cv2.Canny(cand_gray, 50, 150)
        protected_edge_delta = float(np.logical_xor(orig_edges > 0, cand_edges > 0)[protected_mask].mean())

    orig_mean = original[:, :, :3].astype(np.float32)[protected_mask].mean(axis=0) if protected_mask.any() else np.zeros(3)
    cand_mean = candidate[:, :, :3].astype(np.float32)[protected_mask].mean(axis=0) if protected_mask.any() else np.zeros(3)
    channel_shift = cand_mean - orig_mean
    protected_blue_shift = float(channel_shift[0] - max(channel_shift[1], channel_shift[2]))

    metrics: Dict[str, Any] = {
        "mode": mode,
        "protected_mean_delta": round(protected_mean_delta, 4),
        "protected_p95_delta": round(protected_p95_delta, 4),
        "protected_changed_ratio": round(protected_changed_ratio, 6),
        "protected_edge_delta": round(protected_edge_delta, 6),
        "background_changed_ratio": round(background_changed_ratio, 6),
        "total_changed_ratio": round(total_changed_ratio, 6),
        "non_edit_changed_ratio": round(non_edit_changed_ratio, 6),
        "protected_blue_shift": round(protected_blue_shift, 4),
    }

    limits = _limits_for_mode(mode)
    failures: List[tuple[str, str]] = []
    if protected_mean_delta > limits["protected_mean_delta"]:
        failures.append(("IDENTITY_PROTECTED_REGION_CHANGED", f"protected_mean_delta={protected_mean_delta:.2f}"))
    if protected_p95_delta > limits["protected_p95_delta"]:
        failures.append(("IDENTITY_STRUCTURE_CHANGED", f"protected_p95_delta={protected_p95_delta:.2f}"))
    if protected_changed_ratio > limits["protected_changed_ratio"]:
        failures.append(("IDENTITY_PROTECTED_REGION_CHANGED", f"protected_changed_ratio={protected_changed_ratio:.3f}"))
    if protected_edge_delta > limits["protected_edge_delta"]:
        failures.append(("IDENTITY_STRUCTURE_CHANGED", f"protected_edge_delta={protected_edge_delta:.3f}"))
    if protected_blue_shift > limits["protected_blue_shift"]:
        failures.append(("IDENTITY_FACE_COLOR_SHIFT", f"protected_blue_shift={protected_blue_shift:.2f}"))
    if background_changed_ratio > limits["background_changed_ratio"]:
        failures.append(("BACKGROUND_SPILL_DETECTED", f"background_changed_ratio={background_changed_ratio:.3f}"))
    if non_edit_changed_ratio > limits["non_edit_changed_ratio"]:
        failures.append(("AI_OUTPUT_MODIFIED_TOO_MUCH", f"non_edit_changed_ratio={non_edit_changed_ratio:.3f}"))
    if total_changed_ratio > limits["total_changed_ratio"]:
        failures.append(("AI_OUTPUT_MODIFIED_TOO_MUCH", f"total_changed_ratio={total_changed_ratio:.3f}"))

    warnings: List[str] = []
    for key in ("protected_mean_delta", "protected_changed_ratio", "background_changed_ratio", "total_changed_ratio"):
        if metrics[key] > limits[key] * 0.65:
            warnings.append(f"identity_guard_near_limit:{key}={metrics[key]}")

    if failures:
        error_code, detail = failures[0]
        return IdentityGuardResult(
            passed=False,
            metrics=metrics,
            warnings=warnings,
            error_code=error_code,
            message=f"Identity/structure guard failed: {detail}",
        )

    return IdentityGuardResult(passed=True, metrics=metrics, warnings=warnings)


def _decode_image(image_base64: str) -> Optional[np.ndarray]:
    try:
        image = base64_2_numpy(image_base64)
    except Exception:
        return None
    if image is None or image.ndim != 3 or image.shape[2] < 3:
        return None
    return image


def _protected_region_mask(height: int, width: int, mode: str, edit_region: Optional[dict]) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    x_norm = xx.astype(np.float32) / max(1.0, float(width - 1))
    y_norm = yy.astype(np.float32) / max(1.0, float(height - 1))

    # Broad head/hair/upper-neck oval plus top portrait band.  For outfit edits,
    # include the crop top/neck seam as protected so providers cannot repaint it.
    center_x = 0.5
    center_y = 0.31
    radius_x = 0.30
    radius_y = 0.31
    head_oval = ((x_norm - center_x) / radius_x) ** 2 + ((y_norm - center_y) / radius_y) ** 2 <= 1.0
    upper_band_y = 0.56
    if edit_region and (edit_region.get("protected_y_max") is not None or edit_region.get("y") is not None):
        upper_band_y = max(0.38, min(0.72, float(edit_region.get("protected_y_max") or edit_region.get("y")) / float(height)))
    upper_band = (y_norm <= upper_band_y) & (x_norm >= 0.12) & (x_norm <= 0.88)

    mask = head_oval | upper_band
    if mode == "outfit":
        mask |= y_norm <= upper_band_y
    return mask


def _background_spill_mask(height: int, width: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    x_norm = xx.astype(np.float32) / max(1.0, float(width - 1))
    y_norm = yy.astype(np.float32) / max(1.0, float(height - 1))
    side = (x_norm < 0.12) | (x_norm > 0.88)
    top = y_norm < 0.10
    shoulder_bg = (y_norm > 0.42) & ((x_norm < 0.08) | (x_norm > 0.92))
    return side | top | shoulder_bg


def _editable_mask(height: int, width: int, mode: str, edit_region: Optional[dict]) -> np.ndarray:
    mask = np.ones((height, width), dtype=bool)
    if mode == "outfit":
        mask[:] = False
        if edit_region:
            x = int(edit_region.get("x", 0))
            y = int(edit_region.get("y", int(height * 0.48)))
            w = int(edit_region.get("width", width))
            h = int(edit_region.get("height", height - y))
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(width, x1 + max(0, w)), min(height, y1 + max(0, h))
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = True
        else:
            mask[int(height * 0.48) :, :] = True
    elif mode == "background_template":
        yy, xx = np.mgrid[0:height, 0:width]
        x_norm = xx.astype(np.float32) / max(1.0, float(width - 1))
        y_norm = yy.astype(np.float32) / max(1.0, float(height - 1))
        person_core = (x_norm >= 0.18) & (x_norm <= 0.82) & (y_norm >= 0.08)
        mask = ~person_core
    return mask


def _limits_for_mode(mode: str) -> Dict[str, float]:
    if mode == "outfit":
        return {
            "protected_mean_delta": 8.5,
            "protected_p95_delta": 50.0,
            "protected_changed_ratio": 0.10,
            "protected_edge_delta": 0.045,
            "protected_blue_shift": 18.0,
            "background_changed_ratio": 0.18,
            "non_edit_changed_ratio": 0.08,
            "total_changed_ratio": 0.65,
        }
    if mode == "background_template":
        return {
            "protected_mean_delta": 8.0,
            "protected_p95_delta": 24.0,
            "protected_changed_ratio": 0.05,
            "protected_edge_delta": 0.06,
            "protected_blue_shift": 11.0,
            "background_changed_ratio": 0.95,
            "non_edit_changed_ratio": 0.18,
            "total_changed_ratio": 0.85,
        }
    return {
        "protected_mean_delta": 9.0,
        "protected_p95_delta": 28.0,
        "protected_changed_ratio": 0.07,
        "protected_edge_delta": 0.07,
        "protected_blue_shift": 12.0,
        "background_changed_ratio": 0.20,
        "non_edit_changed_ratio": 0.20,
        "total_changed_ratio": 0.45,
    }


def _luma_delta(original: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    orig = original[:, :, :3].astype(np.float32)
    cand = candidate[:, :, :3].astype(np.float32)
    # Images are BGR; use Rec.601 luma weights in B,G,R order.
    orig_y = orig[:, :, 0] * 0.114 + orig[:, :, 1] * 0.587 + orig[:, :, 2] * 0.299
    cand_y = cand[:, :, 0] * 0.114 + cand[:, :, 1] * 0.587 + cand[:, :, 2] * 0.299
    return np.abs(cand_y - orig_y)
