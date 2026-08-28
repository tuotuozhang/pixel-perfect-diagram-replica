---
name: pixel-perfect-diagram-replica
description: Reconstruct a reference image as an editable Microsoft Visio VSDX and/or LibreOffice Draw ODG using a pixel-coordinate scene manifest, deterministic vector primitives, an exact reference page, and render-diff iteration. Use for 1:1 technical diagrams, flowcharts, trees, tables, posters, and scientific figures.
---

# Pixel-Perfect Diagram Replica Skill

Use this skill when a user asks to reproduce an image in **Visio** or **LibreOffice Draw** with matching shapes, text, colors, dimensions, and positions.

## Core principle

A raster source does not contain editable object semantics. Therefore every job must produce two fidelity layers:

1. **Editable reconstruction page** — individual vector shapes, text boxes, lines, arrows, and table cells.
2. **Original pixel-reference page** — the source image embedded at its native dimensions for exact overlay comparison.

Do not claim an editable page is mathematically identical merely because it looks close. Claim 1:1 only after render-and-diff QA, and disclose any font substitution or unresolved mismatch.

## Non-negotiable workflow

1. Read the source image dimensions and use them as the drawing coordinate system.
2. Create a `scene.json` manifest. Every element must use source-image pixel coordinates.
3. Reconstruct with deterministic primitives; do not use generative image tools for the editable page.
4. Build `.vsdx`; convert the same drawing to `.odg` when requested.
5. Render page 1 to PNG at the source resolution.
6. Compare rendered page 1 against the source with `qa_compare.py`.
7. Inspect the reference, reconstruction, and heatmap at 100% zoom.
8. Correct the scene and repeat until the visual error is acceptable.
9. Deliver the requested editable file plus the QA report when fidelity is important.

## Preferred modes

- `editable`: independent vector objects; best for later modification.
- `exact-reference`: source image as a single page object; pixel-identical but not decomposed.
- `hybrid`: editable reconstruction on page 1 and exact reference on page 2. This is the default.

## Scene authoring rules

- Use the original image width and height exactly.
- Record coordinates as top-left-origin pixels.
- Preserve object order because element order controls z-order.
- Sample colors from the source; store six-digit hexadecimal RGB values.
- Split mixed-color labels into separate text boxes rather than relying on rich text.
- Use one text box per independently positioned text block.
- Use individual cells for tables when cell borders or fills differ.
- For arrows, reproduce line width, color, route, arrowhead, and endpoint placement.
- For rounded rectangles, record the actual corner radius.
- Keep the source font family. If unavailable, report the substituted font and do not promise exact typography.

## CLI quick start

```bash
python scripts/make_scene.py reference.png scene.json
# Edit scene.json or have the model populate it from visual inspection.
python scripts/build_diagram.py \
  --source reference.png \
  --scene scene.json \
  --out-dir output \
  --targets vsdx,odg \
  --render --compare
```

Expected outputs:

- `output/replica.vsdx`
- `output/replica.odg`
- `output/replica_page1.png`
- `output/qa_report.json`
- `output/diff_heatmap.png`

## Accuracy gates

The defaults are guidance rather than universal guarantees:

- Pixel match at tolerance 8: at least 97%
- Mean absolute RGB error: no more than 4.0
- SSIM: at least 0.985

For text-heavy diagrams, font rendering differences may prevent these thresholds even when geometry is correct. In that case, compare geometry and disclose the font limitation.

## Package layout

- `scripts/vsdx_writer.py` — native VSDX writer using editable vector primitives.
- `scripts/build_diagram.py` — orchestration, ODG conversion, rendering, and QA.
- `scripts/make_scene.py` — scene skeleton and palette bootstrap.
- `scripts/detect_layout.py` — optional contour/line bootstrap; never treat it as a finished reconstruction.
- `scripts/qa_compare.py` — pixel metrics and heatmap.
- `schemas/scene.schema.json` — manifest schema.
- `templates/blank_scene.json` — starter scene.

## Shipping gate

Before delivery, confirm:

- the VSDX opens in Visio;
- the ODG opens in LibreOffice Draw;
- page size matches the source aspect ratio;
- all required objects are independently editable on page 1;
- page 2 contains the exact source image;
- no text is clipped or missing;
- the latest QA report corresponds to the delivered file.
