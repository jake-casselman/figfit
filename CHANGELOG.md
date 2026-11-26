# Changelog

## Unreleased

- **Docs site** (MkDocs): the README as a guide in eight steps, the notebook tour, the published
  sizes by journal, an API reference read from the docstrings, and this changelog. Published to
  GitHub Pages from `main`.

## 0.4.0 (2026-11-23)

- **On PyPI:** `pip install figfit`. A version tag (`v0.4.0`) publishes it through GitHub Actions with
  PyPI trusted publishing; the README's pictures and links point at GitHub so they show on PyPI too.
- **Renamed figfont to figfit**, because it now does more than font sizes: `pip install figfit`,
  `import figfit`, the `figfit` command. The repository moved to github.com/jake-casselman/figfit.
- **Colour-blind check.** `colour_problems(fig)` reports colour pairs that name things (lines,
  points, bars, areas, legend entries) and colour maps that protan, deutan or tritan readers
  can't tell apart, with pairs that also differ by line style or marker as notes only.
  `colormap_problems`, `image_problems` for PNG and PDF files, `colourblind_sheet` for a picture
  of the figure as each reader sees it, and `figfit colours FILE --sheet` on the command line.

## 0.3.0 (2026-11-21)

- The published-paper reference is new: 3,363 papers from 132 journals, where it was 111 papers.
  The typical paper has 6.5 pt figure text and half of the papers are between 5.5 and 7.4 pt. The
  old reference gave 8 pt; most of its papers had no figure text that could be read, so much of
  that number came from other text on the page.
- `verdict` therefore changes: a figure with 7 pt ticks and 8 pt labels is now `ok`, where it was
  `small`. The default sizes of `set_printed_fonts` are the same as before.
- `reference(field=...)`, `verdict(..., field=...)` and `figfit check --field` compare with one
  of five fields. `fields()` and `journals()` list the names. 90 journals have their own numbers.
- `reference()` also gives the range for 8 in 10 papers, the small end of the text, the spread
  inside one paper, the size next to the caption and body text, and the share read by OCR.
- `paper_figures(path)`: the figures of a paper one at a time, each with its page, printed width
  and text sizes, with the paper's body and caption size and the figures that have no text.
- `figfit check --json` prints one key on each line.
- README: opens with the survey chart. `docs/reference.md` has the numbers for every journal.

## 0.2.3 (2026-11-21)

- `docs/tour.ipynb`: a notebook that shows a figure as it prints on the journal's page, then
  fixes it step by step and explains every number it prints. Its output is saved.
- A file can be given as a `pathlib.Path` as well as a string.
- `fit`, `overlaps`, `density` and `clear_notes` work on a figure a notebook has already shown,
  and on a `Figure` made without pyplot.
- Measuring an image no longer switches the plotting backend of the session that calls it.
- `density` returns plain Python numbers.

## 0.2.2 (2026-11-21)

- `fit`: a boxed note never moves onto or over a line drawn right across its panel (an equator,
  a zero line), so a label stays on its own side.
- `fit`: a boxed note in a gap too narrow for the usual clearance takes the place with the most
  room round it, where before it stayed on the drawing.

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
- The `figfit` command: `check`, `paper` and `scale`.
