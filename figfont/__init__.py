"""figfont: check and fix the printed font size of figures in papers."""
from .compare import reference, verdict
from .measure import figure, figure_ocr, figure_pdf_text, pdf_figure_text
from .scale import drawn_pt_for, font_scale_for, panel_width_for, printed_pt, stitched_width
from .textfit import clear_notes, density, fit, overlaps, report as report_overlaps, suggest_size

__all__ = ["reference", "verdict", "figure", "figure_ocr", "figure_pdf_text", "pdf_figure_text",
           "drawn_pt_for", "font_scale_for", "panel_width_for", "printed_pt", "stitched_width",
           "fit", "clear_notes", "overlaps", "report_overlaps", "density", "suggest_size"]
__version__ = "0.2.0"
