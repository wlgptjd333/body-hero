#!/usr/bin/env python3
"""
Remove uniform cream/light sheet background -> RGBA PNG.
Samples top/left/right borders (skips bottom strip for black footers).

Usage:
  python tools/remove_sheet_background.py path/to/sheet.png -o out.png
  python tools/remove_sheet_background.py a.png b.png -o out_dir/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def _estimate_bg_rgb(arr: np.ndarray, bottom_skip_ratio: float = 0.12) -> np.ndarray:
    h, w = arr.shape[:2]
    strip = max(4, min(40, h // 12, w // 12))
    hb = int(h * (1.0 - bottom_skip_ratio))
    top = arr[:strip, :, :3].reshape(-1, 3)
    left = arr[:hb, :strip, :3].reshape(-1, 3)
    right = arr[:hb, -strip:, :3].reshape(-1, 3)
    all_px = np.vstack([top, left, right])
    return np.median(all_px.astype(np.float32), axis=0)


def remove_uniform_background(
    img: Image.Image,
    *,
    tol_lo: float = 22.0,
    tol_hi: float = 52.0,
    bottom_skip_ratio: float = 0.12,
) -> Image.Image:
    """Alpha from Euclidean RGB distance to estimated bg; soft edge between tol_lo and tol_hi."""
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    bg = _estimate_bg_rgb(arr, bottom_skip_ratio=bottom_skip_ratio)
    d = np.linalg.norm(arr - bg, axis=2)
    alpha = np.clip((d - tol_lo) / max(tol_hi - tol_lo, 1e-3) * 255.0, 0.0, 255.0)
    rgba = np.dstack([arr.astype(np.uint8), alpha.astype(np.uint8)])
    return Image.fromarray(rgba, mode="RGBA")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--tol-lo", type=float, default=22.0)
    p.add_argument("--tol-hi", type=float, default=52.0)
    p.add_argument("--bottom-skip", type=float, default=0.12)
    args = p.parse_args()

    inputs: list[Path] = [x.resolve() for x in args.inputs]
    for inp in inputs:
        if not inp.is_file():
            print(f"Missing file: {inp}", file=sys.stderr)
            return 1

    out = args.output.resolve()
    if len(inputs) == 1:
        if out.is_dir():
            out = out / f"{inputs[0].stem}_nobg.png"
        im = Image.open(inputs[0])
        result = remove_uniform_background(
            im,
            tol_lo=args.tol_lo,
            tol_hi=args.tol_hi,
            bottom_skip_ratio=args.bottom_skip,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        result.save(out, format="PNG")
        print(out)
        return 0

    if out.exists() and not out.is_dir():
        print("-o must be a directory when using multiple inputs.", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    for inp in inputs:
        im = Image.open(inp)
        result = remove_uniform_background(
            im,
            tol_lo=args.tol_lo,
            tol_hi=args.tol_hi,
            bottom_skip_ratio=args.bottom_skip,
        )
        dest = out / f"{inp.stem}_nobg.png"
        result.save(dest, format="PNG")
        print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
