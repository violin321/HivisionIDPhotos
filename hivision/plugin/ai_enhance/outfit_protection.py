from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from hivision.utils import base64_2_numpy, numpy_2_base64


@dataclass(frozen=True)
class OutfitEditPlan:
    """Lightweight geometric outfit edit plan.

    The current WebUI path does not pass landmark boxes through the AI layer, so this
    plan intentionally uses a conservative lower-portrait crop. It protects the
    upper head/face/hair area and only exposes the below-neck clothing/shoulder
    region to providers.
    """

    crop_box: tuple[int, int, int, int]
    mask_base64: str
    edit_region: dict


@dataclass(frozen=True)
class ProtectedRegionCheck:
    passed: bool
    delta: float
    error_code: Optional[str] = None
    message: Optional[str] = None
    warnings: tuple[str, ...] = ()


def build_outfit_edit_plan(image_base64: str) -> OutfitEditPlan:
    image = base64_2_numpy(image_base64)
    if image is None or image.ndim != 3:
        raise ValueError("Cannot build outfit edit plan for invalid image")

    height, width = image.shape[:2]
    # Conservative portrait heuristic: keep face/hair/ears outside the editable
    # area, while starting the crop high enough to include the collar, lapels and
    # upper jacket shoulders.  The mask below still keeps the top/chin side soft-
    # protected, so the provider can blend the neck/collar seam without repainting
    # the face.  A narrow side margin preserves background while avoiding clipped
    # outer coat edges on tight ID-photo crops.
    y1 = int(height * 0.48)
    y2 = height
    x_margin = int(width * 0.02)
    x1 = max(0, x_margin)
    x2 = min(width, width - x_margin)

    crop_h = y2 - y1
    crop_w = x2 - x1
    mask = _build_clothing_only_mask(crop_h, crop_w)

    edit_region = {
        "type": "lower_body_crop",
        "x": x1,
        "y": y1,
        "width": crop_w,
        "height": crop_h,
        "protected_y_max": y1,
        "strategy": "masked_crop_composite",
        "mask_kind": "geometric_clothing_only",
    }
    return OutfitEditPlan(
        crop_box=(x1, y1, x2, y2),
        mask_base64=numpy_2_base64(mask),
        edit_region=edit_region,
    )


def _build_clothing_only_mask(crop_h: int, crop_w: int) -> np.ndarray:
    """Return a clothing mask for complete outfit replacement.

    The provider is allowed to edit the visible jacket/shirt silhouette including
    shoulders, lapels, outer coat edges and lower hem.  The top edge and extreme
    crop sides stay protected so provider failures cannot repaint the face or
    paste a generated card back over the original portrait.
    """

    if crop_h <= 0 or crop_w <= 0:
        return np.zeros((max(0, crop_h), max(0, crop_w)), dtype=np.uint8)

    yy, xx = np.mgrid[0:crop_h, 0:crop_w]
    y_norm = yy.astype(np.float32) / max(1.0, float(crop_h - 1))
    x_norm = xx.astype(np.float32) / max(1.0, float(crop_w - 1))

    # Protect the chin/face boundary and the outside background.  Width starts
    # broad enough for lapels/upper shoulders and expands downward to include the
    # complete jacket body and lower hem.
    top_guard = 0.06
    expand = np.clip((y_norm - top_guard) / (1.0 - top_guard), 0.0, 1.0)
    half_width = 0.34 + 0.16 * np.power(expand, 0.72)
    torso = (y_norm >= top_guard) & (np.abs(x_norm - 0.5) <= half_width)

    mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
    mask[torso] = 255

    # Feather only the mask edge used for compositing; keep a real black outside
    # region so APIs that honor masks also avoid non-clothing pixels.
    kernel = max(5, int(round(min(crop_h, crop_w) * 0.04)) | 1)
    mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)
    mask[mask < 10] = 0
    side_guard = max(1, int(round(crop_w * 0.02)))
    mask[:, :side_guard] = 0
    mask[:, crop_w - side_guard :] = 0
    mask[: max(1, int(round(crop_h * top_guard * 0.60))), :] = 0
    return mask


def crop_request_image(image_base64: str, crop_box: tuple[int, int, int, int]) -> str:
    image = base64_2_numpy(image_base64)
    if image is None:
        raise ValueError("Cannot crop invalid image")
    x1, y1, x2, y2 = crop_box
    crop = image[y1:y2, x1:x2]
    return numpy_2_base64(crop)


def composite_crop(
    original_base64: str,
    edited_crop_base64: str,
    crop_box: tuple[int, int, int, int],
    mask_base64: Optional[str] = None,
) -> str:
    original = base64_2_numpy(original_base64)
    edited_crop = base64_2_numpy(edited_crop_base64)
    if original is None or edited_crop is None:
        raise ValueError("Cannot composite invalid image")

    x1, y1, x2, y2 = crop_box
    target_h = y2 - y1
    target_w = x2 - x1
    if edited_crop.shape[:2] != (target_h, target_w):
        edited_crop = cv2.resize(edited_crop, (target_w, target_h), interpolation=cv2.INTER_AREA)

    result = original.copy()
    original_crop = result[y1:y2, x1:x2, :3].astype(np.float32)
    edited_rgb = edited_crop[:, :, :3].astype(np.float32)

    mask = base64_2_numpy(mask_base64) if mask_base64 else _build_clothing_only_mask(target_h, target_w)
    if mask is None:
        mask = _build_clothing_only_mask(target_h, target_w)
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    if mask.shape[:2] != (target_h, target_w):
        mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_AREA)
    alpha_mask = _build_soft_composite_alpha(mask, target_h, target_w)
    alpha = np.clip(alpha_mask.astype(np.float32) / 255.0, 0.0, 1.0)[:, :, None]

    blended = np.clip(original_crop * (1.0 - alpha) + edited_rgb * alpha, 0, 255).astype(result.dtype)
    result[y1:y2, x1:x2, :3] = blended
    return numpy_2_base64(result)


def _build_soft_composite_alpha(mask: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Build a softer alpha for neck/collar and jacket-edge compositing."""

    alpha = mask.astype(np.uint8, copy=False)
    feather = max(5, int(round(min(target_h, target_w) * 0.055)) | 1)
    alpha = cv2.GaussianBlur(alpha, (feather, feather), 0)
    # Keep the absolute crop top and extreme side guards intact after the extra
    # blur, but preserve a gradual transition immediately below them.
    top_guard_px = max(1, int(round(target_h * 0.05)))
    side_guard_px = max(1, int(round(target_w * 0.015)))
    alpha[:top_guard_px, :] = 0
    alpha[:, :side_guard_px] = 0
    alpha[:, target_w - side_guard_px :] = 0
    return alpha


def check_nested_photo_artifact(
    original_crop_base64: str,
    candidate_crop_base64: str,
    min_area_ratio: float = 0.2,
    max_region_std: float = 12.0,
    min_border_contrast: float = 18.0,
) -> ProtectedRegionCheck:
    original_crop = base64_2_numpy(original_crop_base64)
    candidate_crop = base64_2_numpy(candidate_crop_base64)
    if original_crop is None or candidate_crop is None or candidate_crop.ndim != 3:
        return ProtectedRegionCheck(
            passed=False,
            delta=999.0,
            error_code="OUTFIT_NESTED_PHOTO_GUARD_FAILED",
            message="Cannot decode image for outfit nested-photo guard",
        )

    if original_crop.shape[:2] != candidate_crop.shape[:2]:
        candidate_crop = cv2.resize(
            candidate_crop,
            (original_crop.shape[1], original_crop.shape[0]),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(candidate_crop[:, :, :3], cv2.COLOR_BGR2GRAY)
    bright_mask = (gray >= 240).astype(np.uint8) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bright_mask, connectivity=8)
    height, width = gray.shape[:2]
    frame_margin_x = max(4, int(width * 0.03))
    frame_margin_y = max(4, int(height * 0.03))

    suspicious_score = 0.0
    for label_idx in range(1, num_labels):
        x, y, w, h, area = stats[label_idx]
        if area <= 0:
            continue
        area_ratio = float(area) / float(width * height)
        if area_ratio < min_area_ratio:
            continue
        inset = x >= frame_margin_x and y >= frame_margin_y and (x + w) <= (width - frame_margin_x) and (y + h) <= (height - frame_margin_y)
        if not inset:
            continue

        region_mask = labels[y : y + h, x : x + w] == label_idx
        if region_mask.mean() < 0.85:
            continue

        region_pixels = gray[y : y + h, x : x + w][region_mask]
        region_std = float(region_pixels.std()) if region_pixels.size else 999.0
        if region_std > max_region_std:
            continue

        ring_outer_x1 = max(0, x - 4)
        ring_outer_y1 = max(0, y - 4)
        ring_outer_x2 = min(width, x + w + 4)
        ring_outer_y2 = min(height, y + h + 4)
        ring = gray[ring_outer_y1:ring_outer_y2, ring_outer_x1:ring_outer_x2].copy()
        inner_y1 = y - ring_outer_y1
        inner_y2 = inner_y1 + h
        inner_x1 = x - ring_outer_x1
        inner_x2 = inner_x1 + w
        ring[inner_y1:inner_y2, inner_x1:inner_x2] = 0
        ring_pixels = ring[ring > 0]
        ring_mean = float(ring_pixels.mean()) if ring_pixels.size else 255.0
        border_contrast = float(region_pixels.mean() - ring_mean)
        if border_contrast < min_border_contrast:
            continue

        suspicious_score = max(suspicious_score, area_ratio * 100.0 + border_contrast)

    if suspicious_score > 0:
        return ProtectedRegionCheck(
            passed=False,
            delta=suspicious_score,
            error_code="OUTFIT_NESTED_PHOTO_DETECTED",
            message="Edited outfit crop appears to contain an embedded photo/card-like rectangle",
        )

    return ProtectedRegionCheck(passed=True, delta=0.0)


def check_protected_region_color(
    original_base64: str,
    candidate_base64: str,
    edit_region: Optional[dict] = None,
    max_mean_delta: float = 8.0,
    max_blue_shift: float = 10.0,
) -> ProtectedRegionCheck:
    original = base64_2_numpy(original_base64)
    candidate = base64_2_numpy(candidate_base64)
    if original is None or candidate is None or original.ndim != 3 or candidate.ndim != 3:
        return ProtectedRegionCheck(
            passed=False,
            delta=999.0,
            error_code="OUTFIT_COLOR_GUARD_FAILED",
            message="Cannot decode image for outfit protected-region color guard",
        )

    if original.shape[:2] != candidate.shape[:2]:
        candidate = cv2.resize(candidate, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_AREA)

    protected_y_max = None
    if edit_region:
        protected_y_max = edit_region.get("protected_y_max") or edit_region.get("y")
    if protected_y_max is None:
        protected_y_max = int(original.shape[0] * 0.56)
    protected_y_max = int(max(1, min(original.shape[0], protected_y_max)))

    orig_region = original[:protected_y_max, :, :3].astype(np.float32)
    cand_region = candidate[:protected_y_max, :, :3].astype(np.float32)
    orig_mean = orig_region.mean(axis=(0, 1))
    cand_mean = cand_region.mean(axis=(0, 1))
    channel_delta = cand_mean - orig_mean
    mean_delta = float(np.mean(np.abs(channel_delta)))
    blue_shift = float(channel_delta[0] - max(channel_delta[1], channel_delta[2]))

    warnings = []
    if mean_delta > max_mean_delta:
        return ProtectedRegionCheck(
            passed=False,
            delta=mean_delta,
            error_code="PROTECTED_REGION_CHANGED",
            message=f"Protected face/upper region changed too much (mean_delta={mean_delta:.2f})",
        )
    if blue_shift > max_blue_shift:
        return ProtectedRegionCheck(
            passed=False,
            delta=mean_delta,
            error_code="FACE_COLOR_SHIFT_DETECTED",
            message=f"Protected face/upper region has blue shift (blue_shift={blue_shift:.2f})",
        )
    if mean_delta > max_mean_delta * 0.5:
        warnings.append(f"protected_region_delta:{mean_delta:.2f}")

    return ProtectedRegionCheck(passed=True, delta=mean_delta, warnings=tuple(warnings))
