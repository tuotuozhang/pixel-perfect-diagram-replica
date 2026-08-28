# Pixel-Perfect Diagram Replica

A reusable ChatGPT/Codex skill and command-line toolkit for recreating raster diagrams as editable Visio (`.vsdx`) and LibreOffice Draw (`.odg`) files.

## What it does

- Uses the source image's pixel coordinate system.
- Builds editable rectangles, rounded rectangles, ellipses, polygons, text, lines, arrows, tables, and embedded images.
- Adds an exact source-image reference page.
- Converts VSDX to ODG through LibreOffice.
- Renders page 1 and produces objective visual-difference metrics and a heatmap.

## Important limitation

No automatic program can infer every editable object, font, and hidden grouping from arbitrary pixels with guaranteed perfection. The toolkit solves this by combining a deterministic scene manifest with iterative visual QA. The exact reference page is pixel-identical; the editable page reaches 1:1 fidelity through measurement and correction.

## Installation

The folder itself is a skill package. Copy it into the skills directory used by your Codex/agent environment, or run the scripts directly.

```bash
python scripts/install_skill.py --target /path/to/skills
```

## Requirements

Python 3.10+, Pillow, NumPy, OpenCV, scikit-image, LibreOffice, and `pdftoppm`.
