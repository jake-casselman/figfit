"""The math: how big text on a figure ends up on the printed page.

A figure drawn `drawn_width` wide and placed `printed_width` wide on the page is
scaled by printed_width / drawn_width, and so is every font in it. All widths are
in inches; all font sizes in points (1 pt = 1/72 in = 0.353 mm).
"""
from __future__ import annotations

PT_MM = 25.4 / 72
CAP_HEIGHT = 0.7  # capital-letter height as a fraction of the font size (Arial/Helvetica)


def printed_pt(drawn_pt: float, drawn_width: float, printed_width: float) -> float:
    """Size a font set at `drawn_pt` prints at."""
    return drawn_pt * printed_width / drawn_width


def drawn_pt_for(target_pt: float, drawn_width: float, printed_width: float) -> float:
    """Size to set a font at so that it prints at `target_pt`."""
    return target_pt * drawn_width / printed_width


def font_scale_for(target_pt: float, current_printed_pt: float) -> float:
    """Factor to multiply every font by, given what it prints at now."""
    return target_pt / current_printed_pt


def stitched_width(panel_width: float, columns: int, gap: float = 0.0, margin: float = 0.0) -> float:
    """Width of panels placed side by side, with gaps between and a margin around."""
    return columns * panel_width + (columns - 1) * gap + 2 * margin


def panel_width_for(printed_width: float, columns: int, gap: float = 0.0, margin: float = 0.0) -> float:
    """Width each panel gets on the page when `columns` share `printed_width`."""
    return (printed_width - (columns - 1) * gap - 2 * margin) / columns


def pt_to_mm(pt: float) -> float:
    return pt * PT_MM


def cap_height_mm(pt: float) -> float:
    """Height of a capital letter, in mm, for a font of `pt` points."""
    return pt * CAP_HEIGHT * PT_MM


def latex_length_in(value: float, unit: str = "pt") -> float:
    """A LaTeX length in inches (TeX pt = 1/72.27 in)."""
    per_inch = {"pt": 72.27, "bp": 72.0, "mm": 25.4, "cm": 2.54, "in": 1.0}
    return value / per_inch[unit]
