"""Estimate the blue mat bounding box in a frame, as ROI fractions.

Loads a captured frame and segments the desaturated blue-gray work mat by HSV
range, returns the largest connected region's bounding box expressed as
(x0, y0, x1, y1) fractions of the frame so it can be dropped straight into
``ROI_FRAC``. Also writes an annotated preview with the detected mat box and a
proposed inset ROI for visual confirmation.

Run (on the Pi):
    python mat_bbox.py /tmp/frame_now.jpg
"""

from __future__ import annotations

import sys

import cv2
import numpy as np


def main() -> None:
    """Segment the mat and print its bounding box as frame fractions."""
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frame_now.jpg"
    img = cv2.imread(path)
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Blue-gray mat: hue in the blue band, low-moderate saturation, mid value.
    lower = np.array([90, 20, 40])
    upper = np.array([135, 160, 200])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        print("no mat region found")
        return
    c = max(cnts, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(c)
    print(f"frame {w}x{h}")
    print(f"mat bbox px: x0={x} y0={y} x1={x+bw} y1={y+bh}")
    print(
        "mat bbox frac: "
        f"({x/w:.3f}, {y/h:.3f}, {(x+bw)/w:.3f}, {(y+bh)/h:.3f})"
    )
    # Proposed ROI: inset 6% of the mat span on each edge (avoid the rail/edges).
    mx, my = int(0.06 * bw), int(0.06 * bh)
    ix0, iy0, ix1, iy1 = x + mx, y + my, x + bw - mx, y + bh - my
    print(
        "proposed inset ROI_FRAC = "
        f"({ix0/w:.3f}, {iy0/h:.3f}, {ix1/w:.3f}, {iy1/h:.3f})"
    )
    cv2.rectangle(img, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
    cv2.rectangle(img, (ix0, iy0), (ix1, iy1), (255, 255, 0), 2)
    cv2.imwrite("/tmp/mat_bbox.jpg", img)
    print("wrote /tmp/mat_bbox.jpg")


if __name__ == "__main__":
    main()
