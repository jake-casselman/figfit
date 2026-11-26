# API reference

Every public function, with its signature and docstring, read from the code. The [guide](guide/size.md)
shows each one at work on a real figure; [All functions](functions.md) lists them on one page.

Everything is importable from `figfit` except where a section says otherwise.

## 1. Work out the size

::: figfit.scale
    options:
      members: [printed_pt, drawn_pt_for, font_scale_for, panel_width_for, stitched_width, cap_height_mm, latex_length_in]

## 2. Measure what prints

::: figfit.measure
    options:
      members: [figure, figure_pdf_text, figure_ocr, pdf_figure_text]

::: figfit.papers
    options:
      members: [paper_figures]

## 3. Compare with published papers

::: figfit.compare
    options:
      members: [reference, verdict, journals, fields]

## 4. Set the printed sizes

These two are in `figfit.mpl`.

::: figfit.mpl
    options:
      members: [set_printed_fonts, scale_fonts]

## 5–7. Small panels and colliding text

`report_overlaps` is `figfit.textfit.report`.

::: figfit.textfit
    options:
      members: [suggest_size, density, overlaps, report, fit, clear_notes]

## 8. Colours for colour-blind readers

`colourblind_sheet` is `figfit.colour.sheet`; `simulate` and `difference` are in `figfit.colour`.

::: figfit.colour
    options:
      members: [colour_problems, colormap_problems, image_problems, sheet, simulate, difference, worst]
