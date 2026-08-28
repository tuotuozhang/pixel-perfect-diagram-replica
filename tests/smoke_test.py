from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="diagram_skill_test_") as td:
        work = Path(td)
        source = work / "source.png"
        image = Image.new("RGB", (600, 360), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((40, 40, 560, 300), radius=18, fill="#F8FAFC", outline="#111111", width=2)
        draw.ellipse((240, 90, 360, 150), fill="#FCD180", outline="#111111", width=2)
        draw.line((300, 150, 300, 235), fill="#111111", width=2)
        draw.ellipse((260, 235, 340, 295), fill="#D3E598", outline="#111111", width=2)
        image.save(source)
        scene = {
            "version": 1,
            "canvas": {"width_px": 600, "height_px": 360, "px_per_inch": 100, "background": "#FFFFFF"},
            "metadata": {"title": "Smoke test", "creator": "test"},
            "fonts": ["Times New Roman"],
            "pages": [
                {"name": "Editable 1-to-1", "elements": [
                    {"type": "rounded_rect", "x": 40, "y": 40, "w": 520, "h": 260, "radius_px": 18, "fill": "#F8FAFC", "line": "#111111", "line_px": 2},
                    {"type": "ellipse", "x": 240, "y": 90, "w": 120, "h": 60, "fill": "#FCD180", "line": "#111111", "line_px": 2, "text": "Root", "font_px": 18, "bold": True},
                    {"type": "polyline", "points": [[300, 150], [300, 235]], "line": "#111111", "line_px": 2},
                    {"type": "ellipse", "x": 260, "y": 235, "w": 80, "h": 60, "fill": "#D3E598", "line": "#111111", "line_px": 2, "text": "x0", "font_px": 18, "bold": True}
                ]},
                {"name": "Original Pixel Reference", "reference_image": True}
            ]
        }
        # JSON booleans above are easier written using Python values.
        scene["pages"][0]["elements"][1]["bold"] = True
        scene["pages"][0]["elements"][3]["bold"] = True
        scene["pages"][1]["reference_image"] = True
        scene_path = work / "scene.json"
        scene_path.write_text(json.dumps(scene), encoding="utf-8")
        out_dir = work / "out"
        command = [sys.executable, str(root / "scripts" / "build_diagram.py"), "--source", str(source), "--scene", str(scene_path), "--out-dir", str(out_dir), "--targets", "vsdx,odg", "--render"]
        subprocess.run(command, check=True)
        assert (out_dir / "replica.vsdx").is_file()
        assert (out_dir / "replica.odg").is_file()
        assert (out_dir / "replica_page1.png").is_file()
        print("Smoke test passed")


if __name__ == "__main__":
    main()
