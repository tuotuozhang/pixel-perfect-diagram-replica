from __future__ import annotations

import datetime as _dt
import math
import mimetypes
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

VISIO_NS = "http://schemas.microsoft.com/office/visio/2012/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _esc(value: Any) -> str:
    return escape(str(value), {'"': '&quot;', "'": '&apos;'})


def _f(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


class VisioPage:
    def __init__(self, width_px: float, height_px: float, px_per_inch: float, font_ids: dict[str, int]):
        self.width_px = float(width_px)
        self.height_px = float(height_px)
        self.px_per_inch = float(px_per_inch)
        self.font_ids = font_ids
        self.shapes: list[str] = []
        self._shape_id = 1
        self.media: list[tuple[str, Path]] = []

    def _inch(self, px: float) -> float:
        return float(px) / self.px_per_inch

    def _id(self) -> int:
        value = self._shape_id
        self._shape_id += 1
        return value

    def _xywh(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (
            self._inch(x + w / 2),
            self._inch(self.height_px - (y + h / 2)),
            self._inch(w),
            self._inch(h),
        )

    def _text_sections(self, element: dict[str, Any]) -> str:
        font_family = element.get("font_family", "Times New Roman")
        font_id = self.font_ids.get(font_family, 0)
        font_px = float(element.get("font_px", 14))
        font_color = element.get("font_color", "#111111")
        align = {"left": 0, "center": 1, "right": 2}.get(element.get("align", "center"), 1)
        valign = {"top": 0, "middle": 1, "bottom": 2}.get(element.get("valign", "middle"), 1)
        style = (1 if element.get("bold") else 0) | (2 if element.get("italic") else 0)
        margin = self._inch(float(element.get("margin_px", 0)))
        return f'''<Cell N="VerticalAlign" V="{valign}"/>
<Cell N="LeftMargin" V="{_f(margin)}"/><Cell N="RightMargin" V="{_f(margin)}"/><Cell N="TopMargin" V="{_f(margin)}"/><Cell N="BottomMargin" V="{_f(margin)}"/>
<Section N="Character"><Row IX="0"><Cell N="Font" V="{font_id}"/><Cell N="Color" V="{font_color}"/><Cell N="Size" V="{_f(self._inch(font_px))}"/><Cell N="Style" V="{style}"/></Row></Section>
<Section N="Paragraph"><Row IX="0"><Cell N="HorzAlign" V="{align}"/><Cell N="SpLine" V="-1"/></Row></Section>'''

    def _rect_geometry(self, w: float, h: float, no_fill: int, no_line: int) -> str:
        W, H = self._inch(w), self._inch(h)
        return f'''<Section N="Geometry" IX="0"><Cell N="NoFill" V="{no_fill}"/><Cell N="NoLine" V="{no_line}"/>
<Row T="MoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
<Row T="LineTo" IX="2"><Cell N="X" V="{_f(W)}"/><Cell N="Y" V="0"/></Row>
<Row T="LineTo" IX="3"><Cell N="X" V="{_f(W)}"/><Cell N="Y" V="{_f(H)}"/></Row>
<Row T="LineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="{_f(H)}"/></Row>
<Row T="LineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row></Section>'''

    def _rounded_geometry(self, w: float, h: float, radius_px: float, segments: int = 8) -> str:
        W, H = self._inch(w), self._inch(h)
        R = self._inch(min(radius_px, w / 2, h / 2))
        points: list[tuple[float, float]] = [(R, 0), (W - R, 0)]
        for i in range(1, segments + 1):
            a = -math.pi / 2 + (math.pi / 2) * i / segments
            points.append((W - R + R * math.cos(a), R + R * math.sin(a)))
        points.append((W, H - R))
        for i in range(1, segments + 1):
            a = (math.pi / 2) * i / segments
            points.append((W - R + R * math.cos(a), H - R + R * math.sin(a)))
        points.append((R, H))
        for i in range(1, segments + 1):
            a = math.pi / 2 + (math.pi / 2) * i / segments
            points.append((R + R * math.cos(a), H - R + R * math.sin(a)))
        points.append((0, R))
        for i in range(1, segments + 1):
            a = math.pi + (math.pi / 2) * i / segments
            points.append((R + R * math.cos(a), R + R * math.sin(a)))
        points.append((R, 0))
        rows = []
        for index, (x, y) in enumerate(points, 1):
            row_type = "MoveTo" if index == 1 else "LineTo"
            rows.append(f'<Row T="{row_type}" IX="{index}"><Cell N="X" V="{_f(x)}"/><Cell N="Y" V="{_f(y)}"/></Row>')
        return f'<Section N="Geometry" IX="0"><Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/>{"".join(rows)}</Section>'

    def _ellipse_geometry(self, w: float, h: float) -> str:
        W, H = self._inch(w), self._inch(h)
        return f'''<Section N="Geometry" IX="0"><Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/>
<Row T="Ellipse" IX="1"><Cell N="X" V="{_f(W/2)}"/><Cell N="Y" V="{_f(H/2)}"/><Cell N="A" V="{_f(W)}"/><Cell N="B" V="{_f(H/2)}"/><Cell N="C" V="{_f(W/2)}"/><Cell N="D" V="{_f(H)}"/></Row></Section>'''

    def add_box(self, element: dict[str, Any], geometry: str) -> None:
        sid = self._id()
        x, y, w, h = (float(element[k]) for k in ("x", "y", "w", "h"))
        pin_x, pin_y, width, height = self._xywh(x, y, w, h)
        fill = element.get("fill")
        line = element.get("line")
        fill_pattern = 0 if fill is None else 1
        line_pattern = 0 if line is None or float(element.get("line_px", 1)) <= 0 else 1
        opacity = float(element.get("opacity", 1.0))
        transparency = max(0.0, min(1.0, 1.0 - opacity))
        rotation = math.radians(float(element.get("rotation_deg", 0)))
        text = element.get("text", "")
        text_sections = self._text_sections(element) if text else ""
        name = _esc(element.get("name", element.get("type", "Shape")))
        self.shapes.append(f'''<Shape ID="{sid}" NameU="{name}.{sid}" Name="{name}.{sid}" Type="Shape" LineStyle="0" FillStyle="0" TextStyle="0">
<Cell N="PinX" V="{_f(pin_x)}"/><Cell N="PinY" V="{_f(pin_y)}"/><Cell N="Width" V="{_f(width)}"/><Cell N="Height" V="{_f(height)}"/><Cell N="LocPinX" V="{_f(width/2)}"/><Cell N="LocPinY" V="{_f(height/2)}"/><Cell N="Angle" V="{_f(rotation)}"/>
<Cell N="FillForegnd" V="{fill or '#FFFFFF'}"/><Cell N="FillPattern" V="{fill_pattern}"/><Cell N="FillForegndTrans" V="{_f(transparency)}"/>
<Cell N="LineColor" V="{line or '#FFFFFF'}"/><Cell N="LineWeight" V="{_f(self._inch(float(element.get('line_px', 1))))}"/><Cell N="LinePattern" V="{line_pattern}"/><Cell N="LineColorTrans" V="{_f(transparency)}"/>
{text_sections}{geometry}<Text xml:space="preserve">{_esc(text)}</Text></Shape>''')

    def add_rect(self, element: dict[str, Any], rounded: bool = False) -> None:
        fill = element.get("fill")
        line = element.get("line")
        no_fill = 1 if fill is None else 0
        no_line = 1 if line is None or float(element.get("line_px", 1)) <= 0 else 0
        if rounded:
            geometry = self._rounded_geometry(float(element["w"]), float(element["h"]), float(element.get("radius_px", 8)))
        else:
            geometry = self._rect_geometry(float(element["w"]), float(element["h"]), no_fill, no_line)
        self.add_box(element, geometry)

    def add_ellipse(self, element: dict[str, Any]) -> None:
        self.add_box(element, self._ellipse_geometry(float(element["w"]), float(element["h"])))

    def add_text(self, element: dict[str, Any]) -> None:
        copy = dict(element)
        copy.setdefault("fill", None)
        copy.setdefault("line", None)
        copy.setdefault("line_px", 0)
        self.add_rect(copy, rounded=False)

    def add_polyline(self, element: dict[str, Any], closed: bool = False) -> None:
        points = [[float(p[0]), float(p[1])] for p in element["points"]]
        if closed and points[0] != points[-1]:
            points.append(points[0])
        sid = self._id()
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w, h = max(max_x - min_x, 0.1), max(max_y - min_y, 0.1)
        pin_x, pin_y, width, height = self._xywh(min_x, min_y, w, h)
        rows = []
        for index, (x, y) in enumerate(points, 1):
            row_type = "MoveTo" if index == 1 else "LineTo"
            rows.append(f'<Row T="{row_type}" IX="{index}"><Cell N="X" V="{_f(self._inch(x-min_x))}"/><Cell N="Y" V="{_f(self._inch(max_y-y))}"/></Row>')
        fill = element.get("fill") if closed else None
        line = element.get("line", "#111111")
        opacity = float(element.get("opacity", 1.0))
        transparency = max(0.0, min(1.0, 1.0 - opacity))
        name = _esc(element.get("name", element.get("type", "Polyline")))
        self.shapes.append(f'''<Shape ID="{sid}" NameU="{name}.{sid}" Name="{name}.{sid}" Type="Shape" LineStyle="0" FillStyle="0" TextStyle="0">
<Cell N="PinX" V="{_f(pin_x)}"/><Cell N="PinY" V="{_f(pin_y)}"/><Cell N="Width" V="{_f(width)}"/><Cell N="Height" V="{_f(height)}"/><Cell N="LocPinX" V="{_f(width/2)}"/><Cell N="LocPinY" V="{_f(height/2)}"/><Cell N="Angle" V="0"/>
<Cell N="FillForegnd" V="{fill or '#FFFFFF'}"/><Cell N="FillPattern" V="{1 if fill else 0}"/><Cell N="FillForegndTrans" V="{_f(transparency)}"/>
<Cell N="LineColor" V="{line}"/><Cell N="LineWeight" V="{_f(self._inch(float(element.get('line_px', 1))))}"/><Cell N="LinePattern" V="1"/><Cell N="LineColorTrans" V="{_f(transparency)}"/>
<Cell N="BeginArrow" V="{int(element.get('begin_arrow', 0))}"/><Cell N="EndArrow" V="{int(element.get('end_arrow', 0))}"/><Cell N="BeginArrowSize" V="{int(element.get('arrow_size', 1))}"/><Cell N="EndArrowSize" V="{int(element.get('arrow_size', 1))}"/>
<Section N="Geometry" IX="0"><Cell N="NoFill" V="{0 if fill else 1}"/><Cell N="NoLine" V="0"/>{''.join(rows)}</Section><Text/></Shape>''')

    def add_image(self, element: dict[str, Any], media_target: str) -> None:
        path = Path(element["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        sid = self._id()
        x, y, w, h = (float(element[k]) for k in ("x", "y", "w", "h"))
        pin_x, pin_y, width, height = self._xywh(x, y, w, h)
        rel_id = f"rId{len(self.media)+1}"
        self.media.append((media_target, path))
        self.shapes.append(f'''<Shape ID="{sid}" NameU="Image.{sid}" Name="Image.{sid}" Type="Foreign" LineStyle="0" FillStyle="0" TextStyle="0">
<Cell N="PinX" V="{_f(pin_x)}"/><Cell N="PinY" V="{_f(pin_y)}"/><Cell N="Width" V="{_f(width)}"/><Cell N="Height" V="{_f(height)}"/><Cell N="LocPinX" V="{_f(width/2)}"/><Cell N="LocPinY" V="{_f(height/2)}"/><Cell N="Angle" V="0"/>
<Cell N="ImgOffsetX" V="0"/><Cell N="ImgOffsetY" V="0"/><Cell N="ImgWidth" V="{_f(width)}"/><Cell N="ImgHeight" V="{_f(height)}"/>
<ForeignData ForeignType="Bitmap" CompressionType="PNG"><Rel r:id="{rel_id}"/></ForeignData></Shape>''')

    def add_table(self, element: dict[str, Any]) -> None:
        rows = element["rows"]
        cell_w = float(element["cell_w"])
        cell_h = float(element["cell_h"])
        x, y = float(element["x"]), float(element["y"])
        fills = element.get("row_fills", [])
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                cell = {
                    "type": "rect",
                    "x": x + c * cell_w,
                    "y": y + r * cell_h,
                    "w": cell_w,
                    "h": cell_h,
                    "fill": fills[r] if r < len(fills) else element.get("fill", "#FFFFFF"),
                    "line": element.get("line", "#444444"),
                    "line_px": element.get("line_px", 0.7),
                    "text": str(value),
                    "font_family": element.get("font_family", "Times New Roman"),
                    "font_px": element.get("cell_font_px", 12),
                    "font_color": element.get("cell_font_color", "#111111"),
                    "bold": element.get("bold", False),
                    "align": element.get("align", "center"),
                    "valign": element.get("valign", "middle"),
                    "name": element.get("name", "TableCell"),
                }
                self.add_rect(cell)

    def add_element(self, element: dict[str, Any], media_prefix: str = "image") -> None:
        kind = element["type"]
        if kind == "rect":
            self.add_rect(element)
        elif kind == "rounded_rect":
            self.add_rect(element, rounded=True)
        elif kind == "ellipse":
            self.add_ellipse(element)
        elif kind == "text":
            self.add_text(element)
        elif kind == "polyline":
            self.add_polyline(element)
        elif kind == "polygon":
            self.add_polyline(element, closed=True)
        elif kind == "image":
            suffix = Path(element["path"]).suffix.lower() or ".png"
            self.add_image(element, f"{media_prefix}_{len(self.media)+1}{suffix}")
        elif kind == "table":
            self.add_table(element)
        else:
            raise ValueError(f"Unsupported element type: {kind}")

    def page_xml(self) -> str:
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PageContents xmlns="{VISIO_NS}" xmlns:r="{REL_NS}"><PageSheet><Cell N="PageWidth" V="{_f(self._inch(self.width_px))}"/><Cell N="PageHeight" V="{_f(self._inch(self.height_px))}"/><Cell N="PageScale" V="1"/><Cell N="DrawingScale" V="1"/><Cell N="DrawingSizeType" V="0"/><Cell N="DrawingScaleType" V="0"/></PageSheet><Shapes>{''.join(self.shapes)}</Shapes></PageContents>'''


def _face_names(fonts: list[str]) -> tuple[str, dict[str, int]]:
    unique: list[str] = []
    for font in fonts or ["Times New Roman", "Arial"]:
        if font not in unique:
            unique.append(font)
    if "Times New Roman" not in unique:
        unique.insert(0, "Times New Roman")
    rows = []
    ids = {}
    for index, font in enumerate(unique):
        ids[font] = index
        rows.append(f'<FaceName ID="{index}" NameU="{_esc(font)}" Name="{_esc(font)}" UnicodeRanges="-1" CharSets="0" Panos="2 2 6 3 5 4 5 2 3 4" Flags="325"/>')
    return f'<FaceNames>{"".join(rows)}</FaceNames>', ids


def build_vsdx(scene: dict[str, Any], source_image: Path, output_path: Path) -> dict[str, Any]:
    canvas = scene["canvas"]
    width_px = float(canvas["width_px"])
    height_px = float(canvas["height_px"])
    px_per_inch = float(canvas.get("px_per_inch", 100))
    face_xml, font_ids = _face_names(scene.get("fonts", []))
    pages: list[VisioPage] = []
    for page_index, page_spec in enumerate(scene["pages"], 1):
        page = VisioPage(width_px, height_px, px_per_inch, font_ids)
        if page_spec.get("reference_image"):
            page.add_image({"type": "image", "path": str(source_image), "x": 0, "y": 0, "w": width_px, "h": height_px}, f"reference_{page_index}.png")
        else:
            background = canvas.get("background")
            if background:
                page.add_rect({"type": "rect", "x": 0, "y": 0, "w": width_px, "h": height_px, "fill": background, "line": None, "line_px": 0, "name": "Background"})
            for element in page_spec.get("elements", []):
                page.add_element(element, media_prefix=f"page{page_index}")
        pages.append(page)

    page_w, page_h = width_px / px_per_inch, height_px / px_per_inch
    page_overrides = ''.join(f'<Override PartName="/visio/pages/page{i}.xml" ContentType="application/vnd.ms-visio.page+xml"/>' for i in range(1, len(pages)+1))
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/><Default Extension="jpeg" ContentType="image/jpeg"/><Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/><Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>{page_overrides}<Override PartName="/visio/windows.xml" ContentType="application/vnd.ms-visio.windows+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'''
    document_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/visio/2010/relationships/windows" Target="windows.xml"/></Relationships>'''
    page_rels = ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page{i}.xml"/>' for i in range(1, len(pages)+1))
    pages_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{page_rels}</Relationships>'''
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><VisioDocument xmlns="{VISIO_NS}" xmlns:r="{REL_NS}"><DocumentSettings TopPage="0" DefaultTextStyle="0" DefaultLineStyle="0" DefaultFillStyle="0" DefaultGuideStyle="0"><GlueSettings>9</GlueSettings><SnapSettings>65847</SnapSettings><SnapExtensions>34</SnapExtensions><DynamicGridEnabled>1</DynamicGridEnabled><ProtectStyles>0</ProtectStyles><ProtectShapes>0</ProtectShapes><ProtectMasters>0</ProtectMasters><ProtectBkgnds>0</ProtectBkgnds></DocumentSettings>{face_xml}<StyleSheets><StyleSheet ID="0" NameU="No Style" Name="No Style"><Cell N="EnableLineProps" V="1"/><Cell N="EnableFillProps" V="1"/><Cell N="EnableTextProps" V="1"/><Cell N="LineWeight" V="0.01"/><Cell N="LineColor" V="#111111"/><Cell N="LinePattern" V="1"/><Cell N="FillForegnd" V="#FFFFFF"/><Cell N="FillPattern" V="1"/><Cell N="TextBkgnd" V="0"/></StyleSheet></StyleSheets></VisioDocument>'''
    windows = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Windows xmlns="{VISIO_NS}" xmlns:r="{REL_NS}" ClientWidth="1600" ClientHeight="900"><Window ID="0" WindowType="Drawing" WindowState="1073741824" WindowLeft="0" WindowTop="0" WindowWidth="1600" WindowHeight="900" ContainerType="Page" Page="0" ViewScale="0.85" ViewCenterX="{_f(page_w/2)}" ViewCenterY="{_f(page_h/2)}"/></Windows>'''
    page_entries = []
    for i, spec in enumerate(scene["pages"], 1):
        name = _esc(spec.get("name", f"Page {i}"))
        page_entries.append(f'<Page ID="{i-1}" Name="{name}" NameU="Page_{i}" IsCustomName="1"><PageSheet><Cell N="PageWidth" V="{_f(page_w)}"/><Cell N="PageHeight" V="{_f(page_h)}"/><Cell N="PageScale" V="1"/><Cell N="DrawingScale" V="1"/><Cell N="DrawingSizeType" V="0"/><Cell N="DrawingScaleType" V="0"/></PageSheet><Rel r:id="rId{i}"/></Page>')
    pages_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Pages xmlns="{VISIO_NS}" xmlns:r="{REL_NS}">{''.join(page_entries)}</Pages>'''
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata = scene.get("metadata", {})
    title = _esc(metadata.get("title", "Pixel-perfect editable reconstruction"))
    creator = _esc(metadata.get("creator", "Pixel-Perfect Diagram Replica Skill"))
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{title}</dc:title><dc:creator>{creator}</dc:creator><cp:lastModifiedBy>{creator}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Visio</Application><AppVersion>16.0000</AppVersion></Properties>'''

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        parts = {
            "[Content_Types].xml": content_types,
            "_rels/.rels": root_rels,
            "docProps/core.xml": core,
            "docProps/app.xml": app,
            "visio/document.xml": document,
            "visio/_rels/document.xml.rels": document_rels,
            "visio/windows.xml": windows,
            "visio/pages/pages.xml": pages_xml,
            "visio/pages/_rels/pages.xml.rels": pages_rels,
        }
        for path, data in parts.items():
            archive.writestr(path, data)
        for i, page in enumerate(pages, 1):
            archive.writestr(f"visio/pages/page{i}.xml", page.page_xml())
            if page.media:
                rels = []
                for rel_index, (media_name, media_path) in enumerate(page.media, 1):
                    rels.append(f'<Relationship Id="rId{rel_index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{media_name}"/>')
                    archive.write(media_path, f"visio/media/{media_name}")
                archive.writestr(f"visio/pages/_rels/page{i}.xml.rels", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>''')
    return {
        "path": str(output_path),
        "page_count": len(pages),
        "editable_shape_count": pages[0]._shape_id - 1 if pages else 0,
        "width_px": width_px,
        "height_px": height_px,
    }
