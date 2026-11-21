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

The reference (`figfont/reference.json`) holds summary numbers only: 111 journal articles from
62 journals, median 8.0 pt as printed, middle half of papers 7.4 to 9.0 pt.

OCR sizes are within about 7 % of known sizes (Apple Vision, calibrated on rendered text).
