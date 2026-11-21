"""matplotlib helpers: set fonts in printed points before saving."""
from __future__ import annotations

from .scale import drawn_pt_for

SIZES = {"tick": 7, "label": 8, "title": 8, "legend": 8, "other": 8}


def scale_fonts(fig, factor: float) -> None:
    """Multiply the size of every piece of text in `fig` by `factor`."""
    from matplotlib.text import Text
    for text in fig.findobj(Text):
        text.set_fontsize(text.get_fontsize() * factor)


def set_printed_fonts(fig, printed_width: float, sizes: dict[str, float] | None = None) -> None:
    """Make every text in `fig` print at the given sizes when placed `printed_width` inches wide.

    `sizes` keys, in points as printed:
      tick    tick labels, colour-bar numbers and axis offset text (default 7)
      label   axis and colour-bar labels (8)
      title   panel titles: centre, left and right (8)
      legend  legend entries and legend titles, on a panel or on the figure (8)
      other   everything else: notes in a panel, figure titles, panel letters (8)
    """
    sizes = {**SIZES, **(sizes or {})}
    drawn_width = fig.get_figwidth()
    done = set()

    def put(texts, key):
        for text in texts:
            if text is not None and id(text) not in done:
                text.set_fontsize(drawn_pt_for(sizes[key], drawn_width, printed_width))
                done.add(id(text))

    def put_legend(legend):
        if legend is not None:
            put([*legend.get_texts(), legend.get_title()], "legend")

    for ax in fig.axes:
        ax.tick_params(which="both", labelsize=drawn_pt_for(sizes["tick"], drawn_width, printed_width))
        put([ax.xaxis.get_offset_text(), ax.yaxis.get_offset_text()], "tick")
        put([ax.xaxis.label, ax.yaxis.label], "label")
        put([ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)], "title")
        put_legend(ax.get_legend())
        put(ax.texts, "other")
    for legend in fig.legends:
        put_legend(legend)
    put(fig.texts, "other")
