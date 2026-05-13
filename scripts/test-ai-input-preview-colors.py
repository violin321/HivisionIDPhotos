from __future__ import annotations

import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.processor import IDPhotoProcessor  # noqa: E402


def assert_color(actual: np.ndarray, expected: tuple[int, int, int], label: str) -> None:
    actual_tuple = tuple(int(v) for v in actual.tolist())
    if actual_tuple != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual_tuple}")


def test_bgra_transparent_area_flattens_to_white_not_blue() -> None:
    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[:, :, 0] = 255  # stale B channel that previously leaked as blue
    image[:, :, 3] = 0
    image[1:3, 1:3] = (0, 0, 255, 255)  # opaque red in BGRA

    prepared = IDPhotoProcessor._prepare_ai_input_rgb(image)

    assert prepared.shape == (4, 4, 3)
    assert_color(prepared[0, 0], (255, 255, 255), "transparent BGRA pixel")
    assert_color(prepared[1, 1], (255, 0, 0), "opaque BGRA pixel")


def test_bgr_rendered_background_converts_to_rgb() -> None:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:, :] = (255, 0, 0)  # blue in BGR, as returned by add_background

    prepared = IDPhotoProcessor._prepare_ai_input_rgb(image)

    assert prepared.shape == (4, 4, 3)
    assert_color(prepared[0, 0], (0, 0, 255), "BGR blue background")


def test_already_rgb_blue_is_not_double_swapped() -> None:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:, :] = (0, 0, 255)  # already RGB blue

    prepared = IDPhotoProcessor._prepare_ai_input_rgb(image)

    assert prepared.shape == (4, 4, 3)
    assert_color(prepared[0, 0], (0, 0, 255), "RGB blue background")


if __name__ == "__main__":
    test_bgra_transparent_area_flattens_to_white_not_blue()
    test_bgr_rendered_background_converts_to_rgb()
    test_already_rgb_blue_is_not_double_swapped()
    print("AI input preview color checks passed")
