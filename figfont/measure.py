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
                    box = pymupdf.Rect(span["bbox"])  # a label at the edge of a figure sticks a hair out of it
                    if any(r.contains((box.tl + box.br) / 2) for r in regions):
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


SLANT = 3.5  # a line box taller than this many of its mean letter widths is not upright text


def _upright(width: float, height: float, text: str) -> bool:
    """False for a line set on its side or at a slant: its box height is not its text height."""
    return height * len(text) <= SLANT * width


def _read(image: Image.Image) -> list[tuple[str, tuple[float, float, float, float]]]:
    """(text, (left, top, right, bottom) in px) for each line the OCR is sure of."""
    try:
        from ocrmac import ocrmac
    except ImportError:
        import pytesseract  # needs the tesseract command
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        return [(t.strip(), (x, y, x + w, y + h)) for t, c, x, y, w, h in
                zip(data["text"], data["conf"], data["left"], data["top"], data["width"], data["height"])
                if float(c) >= 50]
    found = ocrmac.OCR(image, recognition_level="accurate").recognize(px=True)
    return [(text.strip(), (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            for text, conf, (x1, y1, x2, y2) in found if conf >= 0.5]


TILT = 0.6   # level text has rows of ink at least this sharp, against the same ink turned to its best angle
SAME = 0.3   # a sideways reading that shares this much of an upright line's box is that line read badly
ANGLES = (15, -15, 30, -30, 45, -45, 60, -60)


def _level(image: Image.Image, box) -> bool:
    """False when the ink in a line box is a tilted label.

    The length test (`_upright`) misses a short tilted word, whose box is still
    wider than it is tall. Level text has sharp rows of ink (its letters start
    and stop on the same lines), and turning it only blurs them; a tilted word
    gets sharper when turned back.
    """
    left, top, right, bottom = (int(round(v)) for v in box)
    grey = np.asarray(image.convert("L").crop((left, top, right, bottom)), dtype=float)
    if grey.shape[0] < 4 or grey.shape[1] < 6:
        return True
    away = np.abs(grey - np.median(grey))
    ink = Image.fromarray((255 * (away > 0.4 * max(away.max(), 1.0))).astype(np.uint8))

    def sharp(angle):
        turned = ink.rotate(angle, expand=True, resample=Image.Resampling.BILINEAR) if angle else ink
        rows = np.asarray(turned, dtype=float).sum(axis=1)
        return float((np.diff(rows, prepend=0, append=0) ** 2).sum())

    return sharp(0) >= TILT * max(sharp(angle) for angle in ANGLES)


def _shared(a, b) -> float:
    """Area two boxes share, as a share of the smaller box."""
    wide = min(a[2], b[2]) - max(a[0], b[0])
    high = min(a[3], b[3]) - max(a[1], b[1])
    if wide <= 0 or high <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return wide * high / smaller if smaller > 0 else 0.0


def _ocr_boxes(image: Image.Image, dpi: int, sideways: bool = True):
    """(text height in pt, text, (left, top, right, bottom) in px) for each text line found.

    A line box only gives the text height when the text is upright, so slanted
    lines (tilted tick labels) are left out, and text written up the page
    (y-axis and colour-bar labels) is read in a second pass with the image
    turned a quarter turn. That second pass also misreads upright text lying
    on its side, so a line it finds on top of an upright one is dropped.
    """
    def good(picture, text, box):
        return len(text) >= 2 and _upright(box[2] - box[0], box[3] - box[1], text) and _level(picture, box)

    lines = [((b - t) * 72 / dpi, text, (l, t, r, b)) for text, (l, t, r, b) in _read(image)
             if good(image, text, (l, t, r, b))]
    if sideways:
        upright = [box for _, _, box in lines]
        turned = image.transpose(Image.Transpose.ROTATE_270)  # text written upwards now reads left to right
        for text, (l, t, r, b) in _read(turned):
            box = (t, image.height - r, b, image.height - l)
            if good(turned, text, (l, t, r, b)) and all(_shared(box, other) < SAME for other in upright):
                lines.append(((b - t) * 72 / dpi, text, box))
    return lines


def _ocr_lines(image: Image.Image, dpi: int, sideways: bool = True) -> list[tuple[float, str]]:
    """(text height in pt, text) for each text line found."""
    return [(height, text) for height, text, _ in _ocr_boxes(image, dpi, sideways)]


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
            heights = [h for h, _ in _ocr_lines(image, dpi, sideways=False)]
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
