# figfont

Checks how big the text in your figures prints, compares it with published papers, and gives
the font sizes to draw at so it comes out right.

A figure drawn 26 in wide and placed 5 in wide on the page shrinks every font by five. Text set
at 15 pt then prints at 3 pt, half of what journals use. figfont measures what prints, from the
compiled paper or the figure file, including text inside stitched raster images.

```
pip install -e ".[mac]"        # or ".[tesseract]" off macOS

figfont check fig01.pdf fig05.png@5.15     # figure files at their printed width (inches)
figfont paper paper.pdf                     # vector figure text in a compiled paper
figfont scale 8 26.3 5.15                   # draw at this size to print at 8 pt
```

In Python:

```python
import figfont
r = figfont.figure_ocr("fig01.png", printed_width=5.15)
figfont.verdict(r)            # ok / small / large against published papers
figfont.drawn_pt_for(8, drawn_width=26.3, printed_width=5.15)

from figfont.mpl import set_printed_fonts
set_printed_fonts(fig, printed_width=5.15)  # 7 pt ticks, 8 pt labels and titles, as printed
```

Bigger text in the same layout collides. `figfont.fit(fig)` finds every pair of touching
text in a matplotlib figure and fixes it with the smallest change: a legend whose text
lies on the data (a map, bars, a filled band) moves to an empty spot in its panel or, when
there is none, under the panel in a row; long labels that touch something wrap onto two
lines; axis labels keep clear of their tick numbers; panel letters step clear of axis
labels; crowded tick labels tilt; notes inside a panel push apart; legends move off labels;
and only then do panels get more space between them. Background bands and grid lines do
not count as data. Sizes, colours, data and wording stay as they are. It prints what it
changed and anything it could not fix:

```python
from figfont.mpl import scale_fonts
scale_fonts(fig, 1.6)
figfont.fit(fig, "fig04")     # TEXT FIXED fig04: wrap 2, letters 2, space 2 / TEXT OK
```

Panel letters and titles placed with `fig.text` can be tagged so `fit` knows their panel:
`t._panel = {"axis": ax, "kind": "letter" or "title", "dx": ..., "dy": ...}` (offsets in
figure fractions from the panel's top-left corner).

How big should the text be? 8 pt is the published average, but it comes mostly from
figures with a few large panels. On a grid of small maps 8 pt words are as big as the maps.
`figfont.suggest_size(fig, printed_pt=8)` measures each panel's width in heights of its own
text and picks the size (6 to 8 pt, whole points) that keeps the narrowest panel at least 15
text heights wide. 15 is the floor of the eHDD figures that read well; the two that did not
were 10 and 11. (A text-area-to-panel-area ratio was tried first and did not separate them.)

The reference (`figfont/reference.json`) holds summary numbers only: 111 journal articles from
62 journals, median 8.0 pt as printed, middle half of papers 7.4 to 9.0 pt.

OCR sizes are within about 7 % of known sizes (Apple Vision, calibrated on rendered text).
