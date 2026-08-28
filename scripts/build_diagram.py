from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from vsdx_writer import build_vsdx
from qa_compare import compare_images


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    print(result.stdout, end="")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")


def validate_scene(scene: dict, schema_path: Path | None = None) -> None:
    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "scene.schema.json"
    try:
        import jsonschema
    except ImportError:
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(scene, schema)


def libreoffice_binary() -> str:
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    if not binary:
        raise RuntimeError("LibreOffice/soffice was not found in PATH")
    return binary


def convert_to_odg(vsdx: Path, output_odg: Path) -> None:
    soffice = libreoffice_binary()
    with tempfile.TemporaryDirectory(prefix="diagram_odg_") as td:
        td_path = Path(td)
        converted = td_path / "converted"
        converted.mkdir()
        profile = td_path / "profile"
        run([
            soffice,
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--headless",
            "--convert-to", "odg",
            "--outdir", str(converted),
            str(vsdx),
        ])
        candidate = converted / f"{vsdx.stem}.odg"
        if not candidate.exists():
            raise RuntimeError(f"LibreOffice did not create {candidate}")
        shutil.copy2(candidate, output_odg)


def render_first_page(document: Path, output_png: Path, width_px: int, height_px: int) -> None:
    soffice = libreoffice_binary()
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm was not found in PATH")
    with tempfile.TemporaryDirectory(prefix="diagram_render_") as td:
        td_path = Path(td)
        profile = td_path / "profile"
        run([
            soffice,
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(td_path),
            str(document),
        ])
        pdf = td_path / f"{document.stem}.pdf"
        if not pdf.exists():
            raise RuntimeError(f"LibreOffice did not render {pdf}")
        dpi = max(72, int(round(width_px * 72 / max(width_px / 100.0, 1))))
        # Render page one at a high resolution, then normalize to exact source pixels.
        prefix = td_path / "page1"
        run([pdftoppm, "-f", "1", "-singlefile", "-png", "-r", str(dpi), str(pdf), str(prefix)])
        raw = Path(str(prefix) + ".png")
        image = Image.open(raw).convert("RGB")
        image = image.resize((width_px, height_px), Image.Resampling.LANCZOS)
        image.save(output_png)


def build(source: Path, scene_path: Path, out_dir: Path, targets: set[str], render: bool, compare: bool, stem: str) -> dict:
    source = source.resolve()
    scene_path = scene_path.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    validate_scene(scene)
    with Image.open(source) as image:
        source_size = image.size
    canvas_size = (int(scene["canvas"]["width_px"]), int(scene["canvas"]["height_px"]))
    if source_size != canvas_size:
        raise ValueError(f"Scene canvas {canvas_size} does not match source image {source_size}")

    vsdx_path = out_dir / f"{stem}.vsdx"
    result = build_vsdx(scene, source, vsdx_path)
    outputs: dict[str, str | int | float | bool | None] = {"vsdx": str(vsdx_path), **result}

    odg_path = out_dir / f"{stem}.odg"
    if "odg" in targets:
        convert_to_odg(vsdx_path, odg_path)
        outputs["odg"] = str(odg_path)
    if "vsdx" not in targets:
        vsdx_path.unlink(missing_ok=True)
        outputs.pop("vsdx", None)

    render_document = odg_path if odg_path.exists() else vsdx_path
    if render or compare:
        preview = out_dir / f"{stem}_page1.png"
        render_first_page(render_document, preview, canvas_size[0], canvas_size[1])
        outputs["preview"] = str(preview)
        if compare:
            heatmap = out_dir / "diff_heatmap.png"
            report_path = out_dir / "qa_report.json"
            report = compare_images(source, preview, heatmap)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            outputs["qa_report"] = str(report_path)
            outputs["diff_heatmap"] = str(heatmap)
            outputs["guidance_pass"] = report["guidance_pass"]
            outputs["pixel_match_fraction"] = report["pixel_match_fraction"]
            outputs["ssim"] = report["ssim"]
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pixel-coordinate editable Visio and LibreOffice replicas.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--targets", default="vsdx,odg", help="Comma-separated: vsdx,odg")
    parser.add_argument("--stem", default="replica")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    targets = {part.strip().lower() for part in args.targets.split(",") if part.strip()}
    unknown = targets - {"vsdx", "odg"}
    if unknown:
        raise ValueError(f"Unsupported targets: {sorted(unknown)}")
    result = build(args.source, args.scene, args.out_dir, targets, args.render, args.compare, args.stem)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
