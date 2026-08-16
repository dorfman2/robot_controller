"""
Bootstrap YOLO labels for the pen dataset using the classic-CV detector.

Runs :func:`detectors.detect_pen` on each captured image and writes a
YOLO-format label (class 0 = ``pen``) for the best detection, plus an annotated
preview so the operator can quickly review/correct in Roboflow instead of
labeling from scratch.

This is WEAK SUPERVISION: the classic detector is imperfect (it can pick an
elongated non-pen object in clutter), so the emitted labels are a STARTING
POINT that MUST be reviewed. The point is to cut annotation effort, not to
replace review — a model trained on unreviewed auto-labels would only mimic the
classic detector (errors included).

YOLO label line (one per detection): ``<class> <cx> <cy> <w> <h>`` with all
values normalized to ``[0, 1]`` (axis-aligned box enclosing the oriented pen
box). Images with no detection get an empty label file (a valid "background"
sample in YOLO).

Run on the Pi (needs cv2), against the captured dataset:
    /home/pi/armold-venv/bin/python /home/pi/vision/autolabel_pen.py \
        --images /home/pi/pen_dataset --out /home/pi/pen_labeled
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import cv2
import numpy as np
from detectors import detect_pen

logger = logging.getLogger(__name__)

CLASS_ID: int = 0
CLASS_NAME: str = "pen"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(description="Auto-label pens with classic CV.")
    p.add_argument("--images", required=True, help="Directory of source JPEGs.")
    p.add_argument("--out", required=True, help="Output dir (labels/ + previews/).")
    p.add_argument(
        "--roi",
        type=float,
        nargs=4,
        default=[0.20, 0.16, 0.60, 0.656],
        metavar=("X0", "Y0", "X1", "Y1"),
        help="ROI fractions passed to detect_pen (default: mat ROI).",
    )
    p.add_argument(
        "--min-elongation",
        type=float,
        default=3.0,
        help="Minimum long/short ratio to accept as a pen.",
    )
    p.add_argument(
        "--min-confidence",
        type=float,
        default=200.0,
        help=(
            "Minimum detect_pen confidence to emit a box. Detections below this "
            "become background (empty label) instead of a likely-wrong box. "
            "Observed: tight pen boxes score 380+, partial/edge failures ~120."
        ),
    )
    return p.parse_args()


def aabb_norm(
    box_points: np.ndarray, width: int, height: int
) -> tuple[float, float, float, float]:
    """Return the normalized axis-aligned bbox (cx, cy, w, h) of an oriented box.

    Args:
        box_points: ``(4, 2)`` oriented-box corners in pixels.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        ``(cx, cy, w, h)`` normalized to ``[0, 1]``, clipped to the image.
    """
    xs = box_points[:, 0]
    ys = box_points[:, 1]
    x_min = max(0.0, float(xs.min()))
    y_min = max(0.0, float(ys.min()))
    x_max = min(float(width), float(xs.max()))
    y_max = min(float(height), float(ys.max()))
    cx = (x_min + x_max) / 2.0 / width
    cy = (y_min + y_max) / 2.0 / height
    w = (x_max - x_min) / width
    h = (y_max - y_min) / height
    return cx, cy, w, h


def main() -> None:
    """Auto-label every image in the source dir; write labels + previews."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    images_dir = Path(args.images)
    out_dir = Path(args.out)
    labels_dir = out_dir / "labels"
    previews_dir = out_dir / "previews"
    labels_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    roi = (args.roi[0], args.roi[1], args.roi[2], args.roi[3])
    jpgs = sorted(images_dir.glob("*.jpg"))
    detected = 0
    rejected = 0

    for img_path in jpgs:
        img = cv2.imread(str(img_path))
        if img is None:
            logger.warning("skip (unreadable): %s", img_path.name)
            continue
        h, w = img.shape[:2]
        (rx0, ry0, rx1, ry1), det = detect_pen(
            img, roi_frac=roi, min_elongation=args.min_elongation
        )

        label_path = labels_dir / f"{img_path.stem}.txt"
        preview = img.copy()
        cv2.rectangle(preview, (rx0, ry0), (rx1, ry1), (255, 200, 0), 2)

        accepted = det is not None and det.confidence >= args.min_confidence
        if accepted:
            assert det is not None  # narrowed by `accepted`
            cx, cy, bw, bh = aabb_norm(det.box_points, w, h)
            label_path.write_text(f"{CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            cv2.drawContours(preview, [det.box_points], 0, (0, 0, 255), 2)
            px, py = int(det.center_px[0]), int(det.center_px[1])
            cv2.putText(
                preview,
                f"pen {det.angle_deg:.0f}deg conf={det.confidence:.0f}",
                (px + 8, py),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            detected += 1
        else:
            # Below-threshold or no detection -> background sample (empty label).
            label_path.write_text("")
            if det is not None:
                rejected += 1
                cv2.drawContours(preview, [det.box_points], 0, (0, 165, 255), 2)
                px, py = int(det.center_px[0]), int(det.center_px[1])
                cv2.putText(
                    preview,
                    f"REJECT conf={det.confidence:.0f}<{args.min_confidence:.0f}",
                    (px + 8, py),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 165, 255),
                    2,
                )

        cv2.imwrite(str(previews_dir / img_path.name), preview)

    background = len(jpgs) - detected
    print(f"\nauto-labeled {detected}/{len(jpgs)} images with a pen box")
    print(f"  background (no box): {background}  (of which {rejected} below conf)")
    print(f"labels:   {labels_dir}")
    print(f"previews: {previews_dir}  (REVIEW these — classic CV is imperfect)")


if __name__ == "__main__":
    main()
