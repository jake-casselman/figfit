"""Find the figures in a paper's PDF and the size of the text inside them.

A figure is a place on a page where things are drawn (lines, filled shapes, images),
on a page that also carries a figure caption. Figure text is text in or right beside
such a place, in a font the paper's own typesetting does not use: a font belongs to
the typesetting when it is used well away from anything drawn, or in running
sentences (body text, captions). A caption itself is never figure text.

Some figures store no text: they were saved as pixels, or their letters were turned
into shapes. Those are listed separately, and can be read with OCR.
"""
from __future__ import annotations

import collections
import os
import re

import numpy as np
import pymupdf

CELL = 3.0                  # pt per cell of the grid that drawings are marked on
JOIN = 7.0                  # drawings this close (pt) belong to one figure
MIN_W, MIN_H = 72.0, 45.0   # a smaller drawn place is a logo, a rule or an icon
NEAR = 14.0                 # a label this close to a figure, or to a label already in it, belongs to it
FAR = 45.0                  # text farther than this from every drawn place is "well away"
MIN_LABELS = 5              # a drawn place needs this many labels to count as a figure with text
DRAWN = {"fill-path", "stroke-path", "fill-shade", "fill-image", "fill-imgmask"}
CAPTION = re.compile(r"^\s*(?:Supplementary\s+|Extended Data\s+)?(?:Fig(?:ure)?s?\.?|Scheme|Chart)\s*S?\d+", re.I)


def _groups(grid: np.ndarray) -> np.ndarray:
    """Number each connected patch of True cells (touching at a side or a corner counts)."""
    labels = np.zeros(grid.shape, int)
    ny, nx = grid.shape
    count = 0
    for y0, x0 in zip(*np.nonzero(grid)):
        if labels[y0, x0]:
            continue
        count += 1
        labels[y0, x0] = count
        stack = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            for yy in range(max(y - 1, 0), min(y + 2, ny)):
                for xx in range(max(x - 1, 0), min(x + 2, nx)):
                    if grid[yy, xx] and not labels[yy, xx]:
                        labels[yy, xx] = count
                        stack.append((yy, xx))
    return labels


def _regions(page) -> list[tuple[pymupdf.Rect, bool, int]]:
    """A box round each group of drawings on the page: (box, holds an image, number of things drawn)."""
    w, h = page.rect.width, page.rect.height
    nx, ny = int(w / CELL) + 2, int(h / CELL) + 2
    grid = np.zeros((ny, nx), bool)
    images = np.zeros((ny, nx), bool)
    pad = JOIN / 2
    centres = []
    for kind, box in page.get_bboxlog():
        if kind not in DRAWN:
            continue
        x0, y0, x1, y1 = max(box[0], 0), max(box[1], 0), min(box[2], w), min(box[3], h)
        if x1 <= x0 and y1 <= y0:
            continue
        if (x1 - x0) > 0.9 * w and (y1 - y0) > 0.9 * h:
            continue  # a page background
        cells = (slice(int(max(y0 - pad, 0) / CELL), int((y1 + pad) / CELL) + 1),
                 slice(int(max(x0 - pad, 0) / CELL), int((x1 + pad) / CELL) + 1))
        grid[cells] = True
        if "im" in kind:
            images[cells] = True
        centres.append((int((y0 + y1) / 2 / CELL), int((x0 + x1) / 2 / CELL)))
    labels = _groups(grid)
    drawn = collections.Counter(int(labels[min(y, ny - 1), min(x, nx - 1)]) for y, x in centres)
    out = []
    for i in range(1, int(labels.max()) + 1):
        ys, xs = np.nonzero(labels == i)
        box = pymupdf.Rect(xs.min() * CELL + pad, ys.min() * CELL + pad,
                           (xs.max() + 1) * CELL - pad, (ys.max() + 1) * CELL - pad)
        if box.width < MIN_W or box.height < MIN_H:
            continue
        out.append((box, bool(images[ys, xs].any()), drawn[i]))
    return out


def _gap(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    """Distance in pt between two rectangles (0 when they touch or overlap)."""
    return max(a.x0 - b.x1, b.x0 - a.x1, a.y0 - b.y1, b.y0 - a.y1, 0)


def paper_figures(path: str | os.PathLike, max_pages: int = 80) -> dict:
    """Every figure in a paper's PDF, with the sizes of its text as printed.

    Returns a dict:
      figures        one per figure that stores text: page, box (pt), width_in, sizes (pt)
      no_text        figures that store no text (pixels, or letters drawn as shapes): page, box
      body_pt        the size of the paper's main text
      caption_pt     the size of its figure captions (None when not found)
      page_width_in  the width of the page
    """
    names = pymupdf.TOOLS.set_subset_fontnames(True)   # two fonts with one name are told apart by their tag
    try:
        doc = pymupdf.open(os.fspath(path))
        if doc.page_count > max_pages:
            raise ValueError(f"{doc.page_count} pages: more than max_pages={max_pages}")
        pages = []
        away = collections.Counter()         # letters of each font well away from anything drawn
        total = collections.Counter()
        prose_font = collections.Counter()   # letters of each font in running sentences
        prose_size = collections.Counter()   # the same for each (font, size)
        every = collections.Counter()
        captions = collections.Counter()
        for page in doc:
            regions = _regions(page)
            spans, has_caption = [], False
            text = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE)
            for block in text["blocks"]:
                first, in_caption = True, False
                for line in block.get("lines", []):
                    parts = [s for s in line["spans"] if s["text"].strip()]
                    if not parts:
                        continue
                    words = "".join(s["text"] for s in parts)
                    prose = len(re.findall(r"[A-Za-z]{2,}", words)) >= 7 and len(words.replace(" ", "")) >= 40
                    caption = bool(CAPTION.match(words))
                    has_caption = has_caption or caption
                    in_caption = in_caption or caption   # the rest of the block is the caption's text
                    for s in parts:
                        n = len(s["text"].strip())
                        box = pymupdf.Rect(s["bbox"])
                        key = (s["font"], round(s["size"], 1))
                        total[s["font"]] += n
                        every[key] += n
                        if prose:
                            prose_size[key] += n
                            prose_font[s["font"]] += n
                        if caption and first and prose:
                            captions[round(s["size"], 1)] += n
                        if all(_gap(box, r[0]) > FAR for r in regions):
                            away[s["font"]] += n
                        spans.append((box, s["font"], s["size"], n, prose, in_caption))
                    first = False
            pages.append((page.number + 1, regions, spans, has_caption))

        def typeset(font, size):
            if away[font] >= 150 or away[font] > 0.10 * total[font]:
                return True
            return prose_font[font] >= 2000 or prose_size[(font, round(size, 1))] >= 300

        figures, no_text = [], []
        for number, regions, spans, has_caption in pages:
            if not has_caption:
                continue  # no "Fig. N" caption on the page: its drawings are logos, banners, tables or boxes
            free = [s for s in spans if not s[5] and not typeset(s[1], s[2])]
            taken = set()
            for box, has_image, drawn in sorted(regions, key=lambda r: -r[0].get_area()):
                grown, mine = pymupdf.Rect(box), []
                changed = True
                while changed:
                    changed = False
                    for i, s in enumerate(free):
                        if i not in taken and _gap(s[0], grown) <= NEAR:
                            taken.add(i)
                            mine.append(s)
                            grown |= s[0]
                            changed = True
                if len(mine) >= MIN_LABELS:
                    if sum(s[3] for s in mine if s[4]) > 0.4 * sum(s[3] for s in mine):
                        continue  # mostly running sentences: a shaded text box, not a figure
                    figures.append({"page": number, "box": [round(v, 1) for v in grown],
                                    "width_in": round(grown.width / 72, 2), "image": has_image,
                                    "sizes": [round(s[2], 2) for s in mine]})
                elif (has_image or drawn >= 100) and box.width >= 120 and box.height >= 90:
                    # Much of the paper's own text inside the box means a table or a text box instead.
                    inside = sum(s[3] for s in spans
                                 if s[0].intersects(box) and (s[0] & box).get_area() > 0.5 * s[0].get_area())
                    if inside < 150:
                        no_text.append({"page": number, "box": [round(v, 1) for v in box], "image": has_image})
        body = every.most_common(1)[0][0] if every else (None, None)
        return {"pages": doc.page_count, "page_width_in": round(doc[0].rect.width / 72, 2),
                "body_pt": body[1], "caption_pt": captions.most_common(1)[0][0] if captions else None,
                "figures": figures, "no_text": no_text}
    finally:
        pymupdf.TOOLS.set_subset_fontnames(names)
