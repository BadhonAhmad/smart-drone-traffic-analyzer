"""OpenCV drawing helpers for annotated video output."""

from __future__ import annotations

import cv2


def draw_counting_line(frame: cv2.typing.MatLike, y: int, width: int) -> None:
    """Draw the virtual counting line in red across the full frame width."""
    cv2.line(frame, (0, y), (width, y), (0, 0, 255), 2)


def draw_box(
    frame: cv2.typing.MatLike,
    tid: int,
    cls_name: str,
    conf: float,
    ox1: int, oy1: int,
    ox2: int, oy2: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a labelled bounding box on the frame."""
    cv2.rectangle(frame, (ox1, oy1), (ox2, oy2), color, 2)
    label = f"ID:{tid} {cls_name} {conf:.0%}"
    cv2.putText(
        frame, label, (ox1, oy1 - 6),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
    )


def draw_hud(frame: cv2.typing.MatLike, count: int, frame_idx: int) -> None:
    """Draw the heads-up display showing vehicle count and frame number."""
    cv2.putText(
        frame, f"Vehicles Counted: {count}", (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
    )
    cv2.putText(
        frame, f"Frame: {frame_idx}", (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
    )
