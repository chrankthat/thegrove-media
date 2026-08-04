#!/usr/bin/env python3
"""One-shot asset import + resize from the /design workspace source images
into this repo's assets/. Run once during Task 4; not part of the render
pipeline (D4 — no build step touches images at deploy time)."""
import os
from pathlib import Path
from PIL import Image

SRC = Path(os.environ.get(
    "THEGROVE_DESIGN_SRC",
    "/Users/trunk/TheGrove/docs/design/2026-08-04-thegrove-media/assets",
))
DST = Path(__file__).resolve().parent.parent / "assets"

# (source relative path, dest relative path, max dimension or None to copy as-is)
JOBS = [
    ("thegrove-media-badge.png", "thegrove-media-badge.png", 320),
    ("marks/quill-circle.png", "marks/quill-circle.png", 320),
    ("marks/hitl-circle.png", "marks/hitl-circle.png", 320),
    ("marks/tlf-asis.png", "marks/tlf-asis.png", 320),
    ("chris-shanku.webp", "chris-shanku.webp", None),
    ("sash-photo.jpg", "sash-photo.jpg", None),
]


def resize_or_copy(src, dst, max_dim):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if max_dim is None:
        dst.write_bytes(src.read_bytes())
        return
    with Image.open(src) as img:
        if max(img.size) <= max_dim:
            dst.write_bytes(src.read_bytes())
            return
        ratio = max_dim / max(img.size)
        new_size = (round(img.width * ratio), round(img.height * ratio))
        resized = img.resize(new_size, Image.LANCZOS)
        resized.save(dst, optimize=True)


if __name__ == "__main__":
    for src_rel, dst_rel, max_dim in JOBS:
        resize_or_copy(SRC / src_rel, DST / dst_rel, max_dim)
        print(f"{dst_rel}: {(DST / dst_rel).stat().st_size} bytes")
