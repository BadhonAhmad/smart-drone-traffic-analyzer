"""Small shared utilities for the CV pipeline."""

from __future__ import annotations

import cv2


def resize(frame: cv2.typing.MatLike, target_w: int) -> cv2.typing.MatLike:
    """Resize *frame* so its width equals *target_w*, preserving aspect ratio."""
    h, w = frame.shape[:2]
    if w == target_w:
        return frame
    scale = target_w / w
    new_h = int(h * scale)
    return cv2.resize(frame, (target_w, new_h), interpolation=cv2.INTER_LINEAR)
