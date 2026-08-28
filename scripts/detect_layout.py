from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def rgb_hex(bgr: np.ndarray) -> str:
    b, g, r = [int(v) for v in bgr]
    return f"#{r:02X}{g:02X}{b:02X}"


def detect(source: Path, min_area: int = 200) -> dict:
    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(source)
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    objects = []
    for contour in contours:
        area = abs(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        if cw >= w * 0.98 and ch >= h * 0.98:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        mask = np.zeros((h, w), np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        color = cv2.mean(image, mask=mask)[:3]
        kind = "ellipse" if len(approx) > 8 else "rect" if len(approx) == 4 else "polygon"
        item = {
            "type": kind,
            "x": int(x), "y": int(y), "w": int(cw), "h": int(ch),
            "fill": rgb_hex(np.array(color)),
            "line": "#111111", "line_px": 1,
            "confidence": round(min(1.0, area / max(cw * ch, 1)), 3),
        }
        if kind == "polygon":
            item["points"] = [[int(pt[0][0]), int(pt[0][1])] for pt in approx]
        objects.append(item)
    # Deduplicate heavily overlapping boxes, favoring the larger contour.
    objects.sort(key=lambda o: o["w"] * o["h"], reverse=True)
    kept = []
    for obj in objects:
        box = np.array([obj["x"], obj["y"], obj["x"] + obj["w"], obj["y"] + obj["h"]])
        duplicate = False
        for existing in kept:
            other = np.array([existing["x"], existing["y"], existing["x"] + existing["w"], existing["y"] + existing["h"]])
            inter_w = max(0, min(box[2], other[2]) - max(box[0], other[0]))
            inter_h = max(0, min(box[3], other[3]) - max(box[1], other[1]))
            inter = inter_w * inter_h
            union = obj["w"] * obj["h"] + existing["w"] * existing["h"] - inter
            if union and inter / union > 0.92:
                duplicate = True
                break
        if not duplicate:
            kept.append(obj)
    return {"source": str(source), "width_px": w, "height_px": h, "detected_elements": kept[:500]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap likely diagram shapes. Text must be added by visual inspection.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-area", type=int, default=200)
    args = parser.parse_args()
    result = detect(args.source, args.min_area)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Detected {len(result['detected_elements'])} candidate elements")


if __name__ == "__main__":
    main()
