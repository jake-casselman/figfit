# Changelog

## 0.2.1 (2026-11-21)

- `set_printed_fonts` also sets left and right panel titles, legend titles, figure legends and
  axis offset text.
- `fit`: tick labels that still touch at 30 degrees tilt to 45, 60 or 90.
- `fit`: a long title or label that runs off the figure goes onto two lines.
- OCR reads text on its side, skips tilted labels and no longer counts a line twice.
- `pdf_figure_text` counts a label that sticks a hair out of the edge of its figure.
- README with a picture for every function, drawn by `docs/make_images.py`.

## 0.2.0 (2026-11-21)

- `fit`: a boxed note that cuts into something drawn (a coast, a curve) moves the shortest way
  clear of it. `clear_notes` runs that step on its own.
- `fit`: a legend that lies on the data moves to an empty corner or under the panel.
- `fit`: axis labels keep a gap from their tick numbers that grows with the font.
- `suggest_size` picks a size between 6 and 8 pt from the width of each panel in text heights.
  `density` returns the measurements.

## 0.1.0 (2026-11-20)

- Measure the printed size of figure text: stored text in vector PDFs, OCR for images.
- Compare with the figure text of 111 published papers (`reference`, `verdict`).
- The font-size arithmetic (`printed_pt`, `drawn_pt_for`, `font_scale_for`, `panel_width_for`,
  `stitched_width`).
- `set_printed_fonts` and `scale_fonts` for matplotlib figures.
- `fit`, `overlaps` and `report_overlaps` find and fix text that collides.
- The `figfont` command: `check`, `paper` and `scale`.
