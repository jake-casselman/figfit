"""Measure the printed text size of figures.

Two ways, used together:
  text   fonts stored as text in a PDF (vector figures): exact sizes, as placed on the page.
  ocr    text read off the pixels (raster figures, stitched images): the figure is
         rendered at its printed width and each text line's height is converted to
         points with a calibration made the same way. About +-7 % against known sizes.

OCR uses Apple Vision (ocrmac) on macOS, otherwise the tesseract command if installed.
"""
from __future__ import annotations

import collections
import statistics
from dataclasses import dataclass, field

import numpy as np
import pymupdf
from PIL import Image

DPI = 600
DESCENDERS = set("gjpqy(),;[]{}|/_")


@dataclass
class Result:
    name: str
    method: str
    sizes: list[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.sizes)

    @property
    def median(self) -> float | None:
        return round(statistics.median(self.sizes), 2) if self.sizes else None

    def percentile(self, q: float) -> float | None:
        return round(float(np.percentile(self.sizes, q)), 2) if self.sizes else None

    def summary(self) -> dict:
        return {"name": self.name, "method": self.method, "n": self.n, "median_pt": self.median,
                "p10_pt": self.percentile(10), "p90_pt": self.percentile(90)}


# ----------------------------------------------------------------------------- text in PDFs

def pdf_figure_text(path: str) -> Result:
    """Sizes of text that sits inside figures of a PDF paper (vector text only).

    Figure text is text in a font other than the paper's body font, inside a region
    that also holds an image or vector drawings.
    """
    doc = pymupdf.open(path)
    body = collections.Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    body[span["font"]] += len(span["text"])
    body_font = body.most_common(1)[0][0] if body else None
    sizes = []
    for page in doc:
        regions = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
        drawings = [d["rect"] for d in page.get_drawings() if d["rect"].width * d["rect"].height > 4]
        if drawings:
            box = pymupdf.Rect(drawings[0])
            for d in drawings[1:]:
                box |= d
            if box.height > 100:
                regions.append(box)
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if not span["text"].strip() or span["font"] == body_font:
                        continue
                    if any(r.contains(pymupdf.Rect(span["bbox"])) for r in regions):
                        sizes.append(span["size"])
    return Result(path.rsplit("/", 1)[-1], "text", sizes)


def figure_pdf_text(path: str, printed_width: float) -> Result:
    """Exact printed sizes of the text in a vector figure PDF placed `printed_width` inches wide.

    Empty when the figure's text is part of an image (use figure_ocr then).
    """
    page = pymupdf.open(path)[0]
    factor = printed_width * 72 / page.rect.width
    sizes = [round(span["size"] * factor, 2)
             for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])
             for span in line["spans"] if span["text"].strip()]
    return Result(path.rsplit("/", 1)[-1], "text", sizes)


def figure(path: str, printed_width: float) -> Result:
    """Exact sizes from a vector PDF when it has text, otherwise OCR."""
    if path.lower().endswith(".pdf"):
        result = figure_pdf_text(path, printed_width)
        if result.n >= 5:
            return result
    return figure_ocr(path, printed_width)


# ----------------------------------------------------------------------------- OCR

def render(path: str, printed_width: float, dpi: int = DPI) -> Image.Image:
    """A figure file (PDF page 1, PNG, JPG...) rendered at its printed width."""
    if path.lower().endswith(".pdf"):
        page = pymupdf.open(path)[0]
        zoom = printed_width * dpi / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    image = Image.open(path).convert("RGB")
    return image.resize((int(printed_width * dpi), int(image.height * printed_width * dpi / image.width)),
                        Image.LANCZOS)


def _ocr_lines(image: Image.Image, dpi: int) -> list[tuple[float, str]]:
    """(line-box height in pt, text) for each text line found."""
    try:
        from ocrmac import ocrmac
        found = ocrmac.OCR(image, recognition_level="accurate").recognize(px=True)
        return [(abs(y2 - y1) * 72 / dpi, text.strip()) for text, conf, (x1, y1, x2, y2) in found
                if conf >= 0.5 and len(text.strip()) >= 2]
    except ImportError:
        import pytesseract  # needs the tesseract command
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        return [(h * 72 / dpi, t.strip()) for t, h, c in zip(data["text"], data["height"], data["conf"])
                if float(c) >= 50 and len(t.strip()) >= 2]


def _kind(text: str) -> str:
    if set(text) & DESCENDERS:
        return "desc"
    return "letters" if any(c.isalpha() for c in text) else "digits"


_CALIBRATION: dict[str, float] | None = None


def calibration(dpi: int = DPI) -> dict[str, float]:
    """Line-box height per point of font size, per kind of text, measured on known text."""
    global _CALIBRATION
    if _CALIBRATION is not None:
        return _CALIBRATION
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    samples = {"desc": "Heating degree days (kWh)", "letters": "Total U 1971 ABC", "digits": "0.25 1980 -40 100"}
    ratios = {k: [] for k in samples}
    for pt in (5, 6, 7, 8, 10, 12):
        for kind, text in samples.items():
            fig = plt.figure(figsize=(5, 0.6), dpi=dpi)
            fig.text(0.02, 0.3, text, fontsize=pt, family=["Arial", "Helvetica", "DejaVu Sans"])
            fig.canvas.draw()
            image = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
            plt.close(fig)
            heights = [h for h, _ in _ocr_lines(image, dpi)]
            if heights:
                ratios[kind].append(np.median(heights) / pt)
    _CALIBRATION = {k: float(np.median(v)) for k, v in ratios.items() if v}
    return _CALIBRATION


def figure_ocr(path: str, printed_width: float, dpi: int = DPI) -> Result:
    """Printed text sizes of one figure file placed `printed_width` inches wide."""
    k = calibration(dpi)
    lines = _ocr_lines(render(path, printed_width, dpi), dpi)
    sizes = [h / k.get(_kind(t), 1.0) for h, t in lines]
    return Result(path.rsplit("/", 1)[-1], "ocr", [round(s, 2) for s in sizes])
