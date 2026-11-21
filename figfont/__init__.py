"""figfont: check and fix the printed font size of figures in papers."""
from .compare import reference, verdict
from .measure import figure_ocr, pdf_figure_text
from .scale import drawn_pt_for, font_scale_for, panel_width_for, printed_pt, stitched_width

__all__ = ["reference", "verdict", "figure_ocr", "pdf_figure_text", "drawn_pt_for", "font_scale_for",
           "panel_width_for", "printed_pt", "stitched_width"]
__version__ = "0.1.0"
