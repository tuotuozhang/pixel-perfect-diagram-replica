from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import Counter

from PIL import Image


def dominant_colors(image: Image.Image, count: int = 12) -> list[str]:
    small = image.convert("RGB")
    small.thumbnail((320, 320))
    quantized = small.quantize(colors=count, method=Image.Quantize.MEDIANCUT).convert("RGB")
    colors = Counter(quantized.getdata()).most_common(count)
    return ["#%02X%02X%02X" % rgb for rgb, _ in colors]


def make_scene(source: Path) -> dict:
    image = Image.open(source)
    return {
        "version": 1,
        "canvas": {
            "width_px": image.width,
            "height_px": image.height,
            "px_per_inch": 100,
            "background": "#FFFFFF",
        },
        "metadata": {
            "title": f"Editable reconstruction of {source.name}",
            "creator": "Pixel-Perfect Diagram Replica Skill",
            "dominant_colors": dominant_colors(image),
        },
        "fonts": ["Times New Roman", "Arial"],
        "pages": [
            {"name": "Editable 1-to-1", "elements": []},
            {"name": "Original Pixel Reference", "reference_image": True},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a scene skeleton from a reference image.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    scene = make_scene(args.source)
    args.output.write_text(json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created {args.output} for {scene['canvas']['width_px']}x{scene['canvas']['height_px']} source")


if __name__ == "__main__":
    main()
