"""figfit: figures that read well in print: text size, text collisions and colour-blind readers."""
from .colour import colour_problems, colormap_problems, image_problems, sheet as colourblind_sheet
from .compare import fields, journals, reference, verdict
from .measure import figure, figure_ocr, figure_pdf_text, pdf_figure_text
from .papers import paper_figures
from .scale import drawn_pt_for, font_scale_for, panel_width_for, printed_pt, stitched_width
from .textfit import clear_notes, density, fit, overlaps, report as report_overlaps, suggest_size

__all__ = ["reference", "verdict", "journals", "fields", "figure", "figure_ocr", "figure_pdf_text", "pdf_figure_text",
           "paper_figures",
           "drawn_pt_for", "font_scale_for", "panel_width_for", "printed_pt", "stitched_width",
           "fit", "clear_notes", "overlaps", "report_overlaps", "density", "suggest_size",
           "colour_problems", "colormap_problems", "image_problems", "colourblind_sheet"]
__version__ = "0.4.0"
