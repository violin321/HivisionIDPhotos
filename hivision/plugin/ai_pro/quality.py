from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


BACKGROUND_MEAN_DELTA_FAIL_THRESHOLD = 45.0
BACKGROUND_MEAN_DELTA_WARN_THRESHOLD = 22.0
ASPECT_RATIO_MISMATCH_FAIL_THRESHOLD = 0.03
ASPECT_RATIO_PROPORTIONAL_RESIZE_THRESHOLD = 0.001
IDENTITY_CENTER_DELTA_WARN_THRESHOLD = 0.07
IDENTITY_CENTER_DELTA_FAIL_THRESHOLD = 0.12
IDENTITY_SIZE_RATIO_DELTA_WARN_THRESHOLD = 0.18
IDENTITY_SIZE_RATIO_DELTA_FAIL_THRESHOLD = 0.30



def _issue(code: str, message: str, severity: str = "warning", metric: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message, "severity": severity}
    if metric:
        item["metric"] = metric
    return item


def _score_from_issues(errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> int:
    score = 100
    score -= 35 * len(errors)
    score -= 8 * len(warnings)
    return max(0, min(100, score))


def _sample_edge_pixels(image_rgb: np.ndarray) -> np.ndarray:
    height, width = image_rgb.shape[:2]
    border = max(2, min(height, width) // 18)
    mask = np.zeros((height, width), dtype=bool)
    mask[:border, :] = True
    mask[-border:, :] = True
    mask[:, :border] = True
    mask[:, -border:] = True
    corner = max(4, min(height, width) // 10)
    corner_mask = np.zeros((height, width), dtype=bool)
    corner_mask[:corner, :corner] = True
    corner_mask[:corner, -corner:] = True
    corner_mask[-corner:, :corner] = True
    corner_mask[-corner:, -corner:] = True
    combined = mask | corner_mask
    return image_rgb[:, :, :3][combined]


def _detect_face_count(image_rgb: np.ndarray) -> tuple[int | None, str, list[list[int]]]:
    try:
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(cascade_path)
        if classifier.empty():
            return None, "unavailable", []
        faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        rectangles = [[int(x), int(y), int(w), int(h)] for (x, y, w, h) in faces]
        return len(rectangles), "opencv_haar", rectangles
    except Exception:
        return None, "unavailable", []


def _face_payload(rectangle: list[int], image_shape: tuple[int, ...]) -> dict[str, Any]:
    height, width = image_shape[:2]
    x, y, w, h = [int(v) for v in rectangle]
    center_x = (x + w / 2) / width if width else 0.0
    center_y = (y + h / 2) / height if height else 0.0
    area_ratio = (w * h) / (width * height) if width and height else 0.0
    width_ratio = w / width if width else 0.0
    height_ratio = h / height if height else 0.0
    return {
        "rectangle": [x, y, w, h],
        "center": {"x": round(center_x, 4), "y": round(center_y, 4)},
        "widthRatio": round(width_ratio, 4),
        "heightRatio": round(height_ratio, 4),
        "areaRatio": round(area_ratio, 4),
    }


def compare_identity_geometry(
    *,
    source_rectangle: list[int],
    source_shape: tuple[int, ...],
    ai_rectangle: list[int],
    ai_shape: tuple[int, ...],
) -> dict[str, Any]:
    """Compare face-box geometry using normalized, explainable metrics."""

    source_face = _face_payload(source_rectangle, source_shape)
    ai_face = _face_payload(ai_rectangle, ai_shape)
    center_dx = abs(float(source_face["center"]["x"]) - float(ai_face["center"]["x"]))
    center_dy = abs(float(source_face["center"]["y"]) - float(ai_face["center"]["y"]))
    center_distance = float((center_dx ** 2 + center_dy ** 2) ** 0.5)
    source_area_ratio = float(source_face["areaRatio"])
    ai_area_ratio = float(ai_face["areaRatio"])
    if source_area_ratio > 0:
        size_ratio_delta = abs(ai_area_ratio - source_area_ratio) / source_area_ratio
    else:
        size_ratio_delta = 0.0 if ai_area_ratio == 0 else 1.0

    status = "passed"
    if center_distance > IDENTITY_CENTER_DELTA_FAIL_THRESHOLD or size_ratio_delta > IDENTITY_SIZE_RATIO_DELTA_FAIL_THRESHOLD:
        status = "failed"
    elif center_distance > IDENTITY_CENTER_DELTA_WARN_THRESHOLD or size_ratio_delta > IDENTITY_SIZE_RATIO_DELTA_WARN_THRESHOLD:
        status = "warning"

    return {
        "sourceFace": source_face,
        "aiFace": ai_face,
        "centerDelta": {
            "x": round(center_dx, 4),
            "y": round(center_dy, 4),
            "distance": round(center_distance, 4),
            "warnThreshold": IDENTITY_CENTER_DELTA_WARN_THRESHOLD,
            "failThreshold": IDENTITY_CENTER_DELTA_FAIL_THRESHOLD,
        },
        "sizeRatioDelta": round(size_ratio_delta, 4),
        "sizeRatioThresholds": {
            "warn": IDENTITY_SIZE_RATIO_DELTA_WARN_THRESHOLD,
            "fail": IDENTITY_SIZE_RATIO_DELTA_FAIL_THRESHOLD,
        },
        "status": status,
    }


def _read_rgb_image(path: Path | str | None) -> np.ndarray | None:
    if not path:
        return None
    try:
        with Image.open(path) as image:
            return np.array(image.convert("RGB"))
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _evaluate_identity_check(source_rgb: np.ndarray | None, ai_rgb: np.ndarray) -> dict[str, Any]:
    check: dict[str, Any] = {
        "detector": "opencv_haar",
        "status": "unavailable",
        "sourceFace": None,
        "aiFace": None,
        "centerDelta": None,
        "sizeRatioDelta": None,
    }
    if source_rgb is None:
        check.update({"detector": "unavailable", "reason": "source_image_unavailable"})
        return check

    source_count, source_detector, source_rectangles = _detect_face_count(source_rgb)
    ai_count, ai_detector, ai_rectangles = _detect_face_count(ai_rgb)
    detector = source_detector if source_detector == ai_detector else f"{source_detector}/{ai_detector}"
    check.update({
        "detector": detector,
        "sourceFaceCount": source_count,
        "aiFaceCount": ai_count,
        "sourceRectangles": source_rectangles[:3],
        "aiRectangles": ai_rectangles[:3],
    })
    if source_count is None or ai_count is None:
        check.update({"status": "unavailable", "reason": "face_detector_unavailable"})
        return check
    if source_count != 1 or ai_count != 1:
        check.update({"status": "unavailable", "reason": "single_face_not_confident"})
        return check

    geometry = compare_identity_geometry(
        source_rectangle=source_rectangles[0],
        source_shape=source_rgb.shape,
        ai_rectangle=ai_rectangles[0],
        ai_shape=ai_rgb.shape,
    )
    check.update(geometry)
    return check


def evaluate_ai_pro_quality(
    *,
    ai_image_path: Path | str | None,
    source_image_path: Path | str | None = None,
    output_dir: Path | str,
    task_id: str,
    target_spec: dict[str, Any],
    background_rgb: tuple[int, int, int] | list[int],
    free_result: dict[str, Any] | None = None,
    core_quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lightweight, explainable quality gate for AI Pro ID-photo candidates.

    The gate is intentionally conservative for hard failures: unreadable files,
    severe background drift, and ID-photo aspect-ratio mismatches fail. Provider
    outputs are never non-proportionally stretched into the target spec.
    """

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    target_width = int(target_spec.get("width") or 0)
    target_height = int(target_spec.get("height") or 0)
    target_dpi = int(target_spec.get("dpi") or 300)
    output_root = Path(output_dir)
    derivative_path: Path | None = None
    usable_path: Path | None = None

    if not ai_image_path:
        errors.append(_issue("AI_PRO_OUTPUT_MISSING", "AI Pro provider did not return an output image.", "error", "file"))
        checks["file"] = {"exists": False, "readable": False}
        return _finalize_report(checks, warnings, errors, None, free_result, core_quality_report)

    candidate = Path(ai_image_path)
    checks["file"] = {"path": candidate.name, "exists": candidate.exists(), "readable": False}
    if not candidate.is_file():
        errors.append(_issue("AI_PRO_OUTPUT_NOT_FOUND", "AI Pro output file was not found.", "error", "file"))
        return _finalize_report(checks, warnings, errors, None, free_result, core_quality_report)

    try:
        with Image.open(candidate) as image:
            image = image.convert("RGB")
            image_rgb = np.array(image)
    except (UnidentifiedImageError, OSError, ValueError):
        errors.append(_issue("AI_PRO_OUTPUT_UNREADABLE", "AI Pro output image could not be decoded.", "error", "file"))
        return _finalize_report(checks, warnings, errors, None, free_result, core_quality_report)

    checks["file"]["readable"] = True
    height, width = image_rgb.shape[:2]
    dimensions_match = bool(width == target_width and height == target_height)
    actual_aspect_ratio = (width / height) if height else None
    target_aspect_ratio = (target_width / target_height) if target_width > 0 and target_height > 0 else None
    aspect_ratio_delta = (
        abs(float(actual_aspect_ratio) - float(target_aspect_ratio)) / float(target_aspect_ratio)
        if actual_aspect_ratio and target_aspect_ratio
        else None
    )
    aspect_ratio_within_spec = bool(aspect_ratio_delta is not None and aspect_ratio_delta <= ASPECT_RATIO_MISMATCH_FAIL_THRESHOLD)
    can_resize_proportionally = bool(
        aspect_ratio_delta is not None
        and aspect_ratio_delta <= ASPECT_RATIO_PROPORTIONAL_RESIZE_THRESHOLD
    )
    checks["dimensions"] = {
        "actual": {"width": width, "height": height},
        "expected": {"width": target_width, "height": target_height},
        "match": dimensions_match,
        "actualAspectRatio": round(float(actual_aspect_ratio), 6) if actual_aspect_ratio else None,
        "expectedAspectRatio": round(float(target_aspect_ratio), 6) if target_aspect_ratio else None,
        "aspectRatioDelta": round(float(aspect_ratio_delta), 6) if aspect_ratio_delta is not None else None,
        "aspectRatioThreshold": ASPECT_RATIO_MISMATCH_FAIL_THRESHOLD,
        "proportionalResizeThreshold": ASPECT_RATIO_PROPORTIONAL_RESIZE_THRESHOLD,
        "aspectRatioMatch": aspect_ratio_within_spec,
        "canResizeProportionally": can_resize_proportionally,
        "derivative": None,
    }
    usable_path = candidate
    if not dimensions_match:
        if target_width <= 0 or target_height <= 0:
            errors.append(_issue("AI_PRO_TARGET_SPEC_INVALID", "Target dimensions are unavailable, so AI Pro output cannot be normalized.", "error", "dimensions"))
        elif not can_resize_proportionally:
            usable_path = None
            errors.append(_issue(
                "AI_PRO_ASPECT_RATIO_MISMATCH",
                "AI Pro 输出比例不符合证件照规格，已回退 Free Core。",
                "error",
                "dimensions.aspectRatioDelta",
            ))
        else:
            derivative_path = output_root / f"ai_pro_quality_resized_{task_id[-8:]}.png"
            resized = Image.fromarray(image_rgb).resize((target_width, target_height), Image.Resampling.LANCZOS)
            derivative_path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(derivative_path, format="PNG", dpi=(target_dpi, target_dpi))
            usable_path = derivative_path
            image_rgb = np.array(resized)
            warnings.append(_issue("AI_PRO_OUTPUT_RESIZED", "AI Pro output size differed from the target spec but preserved the ID-photo aspect ratio, so it was resized proportionally for the Pro candidate.", "warning", "dimensions"))
            checks["dimensions"].update({
                "actual": {"width": target_width, "height": target_height},
                "match": True,
                "derivative": {"path": derivative_path.name, "width": target_width, "height": target_height, "resizeMode": "proportional"},
            })

    samples = _sample_edge_pixels(image_rgb)
    target = np.array([int(v) for v in background_rgb], dtype=np.float32)
    if samples.size:
        mean_rgb = samples.astype(np.float32).mean(axis=0)
        mean_delta = float(np.abs(mean_rgb - target).mean())
        max_delta = float(np.abs(mean_rgb - target).max())
        checks["backgroundColor"] = {
            "targetRgb": [int(v) for v in background_rgb],
            "sampleMeanRgb": [round(float(v), 2) for v in mean_rgb],
            "meanDelta": round(mean_delta, 3),
            "maxChannelDelta": round(max_delta, 3),
            "thresholds": {"warn": BACKGROUND_MEAN_DELTA_WARN_THRESHOLD, "fail": BACKGROUND_MEAN_DELTA_FAIL_THRESHOLD},
        }
        if mean_delta > BACKGROUND_MEAN_DELTA_FAIL_THRESHOLD:
            errors.append(_issue("AI_PRO_BACKGROUND_COLOR_FAILED", "AI Pro background color differs too much from the target background.", "error", "backgroundColor.meanDelta"))
        elif mean_delta > BACKGROUND_MEAN_DELTA_WARN_THRESHOLD:
            warnings.append(_issue("AI_PRO_BACKGROUND_COLOR_WARNING", "AI Pro background color has visible drift from the target background.", "warning", "backgroundColor.meanDelta"))
    else:
        checks["backgroundColor"] = {"available": False}
        warnings.append(_issue("AI_PRO_BACKGROUND_SAMPLE_UNAVAILABLE", "Could not sample AI Pro background color; manual review is required.", "warning", "backgroundColor"))

    face_count, detector, rectangles = _detect_face_count(image_rgb)
    checks["face"] = {"detector": detector, "count": face_count, "rectangles": rectangles[:3]}
    if face_count is None:
        warnings.append(_issue("AI_PRO_FACE_DETECTOR_UNAVAILABLE", "Face detector was unavailable for AI Pro output; this does not block fallback-safe delivery.", "warning", "face"))
    elif face_count != 1:
        warnings.append(_issue("AI_PRO_FACE_COUNT_REVIEW", "AI Pro output did not produce a confident single-face detector result; manual review is required.", "warning", "face.count"))

    identity_check = _evaluate_identity_check(_read_rgb_image(source_image_path), image_rgb)
    checks["identity"] = identity_check
    if identity_check.get("status") == "failed":
        errors.append(_issue("AI_PRO_IDENTITY_DRIFT_FAILED", "AI Pro may have changed face position or structure too much, so Free Core fallback is used.", "error", "identity"))
    elif identity_check.get("status") == "warning":
        warnings.append(_issue("AI_PRO_IDENTITY_DRIFT_WARNING", "AI Pro face geometry differs from Free Core and should be reviewed.", "warning", "identity"))
    elif identity_check.get("status") == "unavailable":
        warnings.append(_issue("AI_PRO_IDENTITY_CHECK_UNAVAILABLE", "Identity consistency check could not get confident single-face detections; this does not block fallback-safe delivery.", "warning", "identity"))

    checks["composition"] = {
        "targetDimensions": {"width": target_width, "height": target_height},
        "matchesFreeCoreSpec": bool(checks.get("dimensions", {}).get("match")),
        "source": "free_core_spec_metadata",
    }

    return _finalize_report(checks, warnings, errors, usable_path, free_result, core_quality_report)


def _finalize_report(
    checks: dict[str, Any],
    warnings: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    usable_path: Path | None,
    free_result: dict[str, Any] | None,
    core_quality_report: dict[str, Any] | None,
) -> dict[str, Any]:
    score = _score_from_issues(errors, warnings)
    passed = not errors and score >= 70
    fallback_reason = None if passed else (errors[0]["code"] if errors else "AI_PRO_QUALITY_SCORE_LOW")
    return {
        "score": score,
        "passed": passed,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "fallbackReason": fallback_reason,
        "fallbackToFree": not passed,
        "usableImagePath": str(usable_path) if usable_path else None,
        "corePassed": bool((core_quality_report or {}).get("passed")),
        "freeResultFileId": (free_result or {}).get("fileId"),
    }
