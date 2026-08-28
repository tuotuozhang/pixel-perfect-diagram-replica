from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
try:
    from skimage.metrics import structural_similarity
except Exception:  # optional
    structural_similarity = None


def compare_images(reference: Path, candidate: Path, heatmap: Path | None = None, tolerance: int = 8) -> dict:
    ref = Image.open(reference).convert("RGB")
    cand = Image.open(candidate).convert("RGB")
    if cand.size != ref.size:
        cand = cand.resize(ref.size, Image.Resampling.LANCZOS)
    a = np.asarray(ref).astype(np.float32)
    b = np.asarray(cand).astype(np.float32)
    delta = np.abs(a - b)
    mae = float(delta.mean())
    rmse = float(np.sqrt(np.mean((a - b) ** 2)))
    per_pixel = delta.max(axis=2)
    pixel_match = float((per_pixel <= tolerance).mean())
    exact_match = float((per_pixel == 0).mean())
    ssim = None
    if structural_similarity is not None:
        ssim = float(structural_similarity(a.astype(np.uint8), b.astype(np.uint8), channel_axis=2, data_range=255))
    if heatmap is not None:
        scaled = np.clip(per_pixel * 5.0, 0, 255).astype(np.uint8)
        heat = np.zeros((*scaled.shape, 3), dtype=np.uint8)
        heat[..., 0] = scaled
        heat[..., 1] = np.clip(scaled // 5, 0, 255)
        Image.fromarray(heat).save(heatmap)
    return {
        "reference": str(reference),
        "candidate": str(candidate),
        "width": ref.width,
        "height": ref.height,
        "tolerance": tolerance,
        "mean_absolute_rgb_error": mae,
        "rmse_rgb": rmse,
        "pixel_match_fraction": pixel_match,
        "exact_pixel_match_fraction": exact_match,
        "ssim": ssim,
        "guidance_pass": bool(pixel_match >= 0.97 and mae <= 4.0 and (ssim is None or ssim >= 0.985)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--heatmap", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--tolerance", type=int, default=8)
    args = parser.parse_args()
    report = compare_images(args.reference, args.candidate, args.heatmap, args.tolerance)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
