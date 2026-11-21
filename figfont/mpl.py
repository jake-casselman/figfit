"""matplotlib helpers: set fonts in printed points before saving."""
from __future__ import annotations

from .scale import drawn_pt_for


def scale_fonts(fig, factor: float) -> None:
    """Multiply the size of every piece of text in `fig` by `factor`."""
    from matplotlib.text import Text
    for text in fig.findobj(Text):
        text.set_fontsize(text.get_fontsize() * factor)


def set_printed_fonts(fig, printed_width: float, sizes: dict[str, float] | None = None) -> None:
    """Make every text in `fig` print at the given sizes when placed `printed_width` inches wide.

    `sizes` keys: tick, label, title, legend, other (points as printed).
    Default: 7 pt ticks, 8 pt labels, titles and legends.
    """
    from matplotlib.text import Text
    sizes = {"tick": 7, "label": 8, "title": 8, "legend": 8, "other": 8, **(sizes or {})}
    drawn_width = fig.get_figwidth()
    size = lambda key: drawn_pt_for(sizes[key], drawn_width, printed_width)
    for ax in fig.axes:
        ax.tick_params(labelsize=size("tick"))
        ax.xaxis.label.set_fontsize(size("label"))
        ax.yaxis.label.set_fontsize(size("label"))
        ax.title.set_fontsize(size("title"))
        legend = ax.get_legend()
        if legend:
            for t in legend.get_texts():
                t.set_fontsize(size("legend"))
    handled = {id(t) for ax in fig.axes for t in
               [ax.xaxis.label, ax.yaxis.label, ax.title, *ax.get_xticklabels(), *ax.get_yticklabels(),
                *(ax.get_legend().get_texts() if ax.get_legend() else [])]}
    for text in fig.texts:
        if id(text) not in handled:
            text.set_fontsize(size("other"))
