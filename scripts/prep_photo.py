#!/usr/bin/env python3
"""Prep a source photo into a grayscale image ready for ASCII conversion.

A flatly-lit photo converts to a dark, unreadable blob. Three steps fix that:

  1. Remove the background with rembg so the subject is isolated.
  2. Crop to the subject's alpha bounding box so the portrait is centered
     and free of empty margins.
  3. Boost local contrast with OpenCV's CLAHE (contrast-limited adaptive
     histogram equalization) — this is what gives a flat face real
     highlights and shadows.
  4. Composite onto pure white so the background maps to the blank end of
     the ASCII ramp (white -> spaces).

Run once per photo:

    python scripts/prep_photo.py source-photo.jpg

Output: source-prepped.png (grayscale) at the repo root.
"""

import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "source-prepped.png"

CLIP_LIMIT = 2.0
TILE_GRID = (8, 8)


def _crop_subject(subject: np.ndarray, pad_ratio: float = 0.02) -> np.ndarray:
    """Crop to the subject's alpha bounding box (plus a little padding) so
    the portrait is centered and free of empty margins."""
    alpha = subject[:, :, 3]
    ys, xs = np.nonzero(alpha > 10)
    if xs.size == 0:
        return subject
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    pad = max(1, int(round(max(x1 - x0, y1 - y0) * pad_ratio)))
    h, w = subject.shape[:2]
    x0 = max(0, x0 - pad)
    x1 = min(w - 1, x1 + pad)
    y0 = max(0, y0 - pad)
    y1 = min(h - 1, y1 + pad)
    return subject[y0 : y1 + 1, x0 : x1 + 1]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: python scripts/prep_photo.py <source-photo>")

    source = Path(sys.argv[1])
    if not source.exists():
        sys.exit(f"source photo not found: {source}")

    print(f"removing background from {source.name} ...")
    # u2net is the classic 176 MB model — plenty for a monochrome ASCII
    # portrait, and far lighter than rembg's 1 GB bria-rmbg default.
    session = new_session("u2net")
    subject_bytes = remove(source.read_bytes(), session=session)

    subject = np.array(Image.open(io.BytesIO(subject_bytes)).convert("RGBA"))
    print("cropping to the subject ...")
    subject = _crop_subject(subject)
    rgb = subject[:, :, :3]
    alpha = subject[:, :, 3].astype(np.float32) / 255.0

    print("boosting local contrast with CLAHE ...")
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLIP_LIMIT, tileGridSize=TILE_GRID)
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    print("compositing onto white ...")
    white = np.full_like(gray, 255, dtype=np.float32)
    composited = (
        gray.astype(np.float32) * alpha + white * (1.0 - alpha)
    ).astype(np.uint8)

    Image.fromarray(composited, mode="L").save(OUTPUT)
    print(f"wrote {OUTPUT.name} ({composited.shape[1]}x{composited.shape[0]})")


if __name__ == "__main__":
    main()
