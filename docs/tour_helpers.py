"""Pictures for docs/tour.ipynb. They only draw; none of this is part of figfit."""
import io

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.text import Text

import figfit

BODY = ("This is the main text of the paper, set at 10 pt. The figure below sits in the\n"
        "same column, at the width the journal gives it. Compare the two sizes of text.")


def on_the_page(fig, printed_width, label=""):
    """`fig` as a reader gets it: `printed_width` inches wide, in a column of 10 pt text."""
    margin, above, below = 0.4, 0.75, 0.5
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=600 * printed_width / fig.get_figwidth())
    buffer.seek(0)
    picture = plt.imread(buffer)
    plt.close(fig)  # the notebook shows the page, not the figure a second time
    height = printed_width * picture.shape[0] / picture.shape[1]
    page_w, page_h = printed_width + 2 * margin, height + above + below
    page = plt.figure(figsize=(page_w, page_h), facecolor="white", edgecolor="0.6", linewidth=1)
    page.text(margin / page_w, 1 - 0.2 / page_h, BODY, fontsize=10, family="serif", va="top", linespacing=1.3)
    ax = page.add_axes([margin / page_w, below / page_h, printed_width / page_w, height / page_h])
    ax.imshow(picture)
    ax.axis("off")
    caption = "Figure 1. " + (label or "The caption, at 9 pt.")
    page.text(margin / page_w, 0.33 / page_h, caption, fontsize=9, family="serif", va="top")
    return page


def against_papers(results):
    """Each figure's text sizes as a bar, over the sizes found in published papers."""
    papers = figfit.reference()
    plot, ax = plt.subplots(figsize=(8, 1.3 + 0.45 * len(results)), layout="constrained")
    ax.axvspan(*papers["paper_medians_p25_p75"], color="0.88", label="where half of published papers sit")
    ax.axvline(papers["median_pt"], color="0.4", linewidth=1, label="typical published paper")
    for row, result in enumerate(results.values()):
        ax.plot([result.percentile(10), result.percentile(90)], [row, row], color="C0", linewidth=3)
        ax.plot(result.median, row, "o", color="C0")
    ax.set_yticks(range(len(results)), list(results))
    ax.set_ylim(len(results) - 0.4, -0.6)
    ax.set_xlim(2, 11)
    ax.set_xlabel("Size of the figure's text on the page (pt)")
    plot.legend(loc="outside upper right", ncols=2, fontsize=9, frameon=False)
    return plot


def mark(fig, problems):
    """A picture of `fig` with a red box round each piece of text named in `problems`."""
    fig.canvas.draw()
    picture = np.asarray(fig.canvas.buffer_rgba())
    height, width = picture.shape[:2]
    marked = plt.figure(figsize=fig.get_size_inches(), dpi=fig.dpi)
    ax = marked.add_axes([0, 0, 1, 1])
    ax.imshow(picture, extent=(0, width, 0, height))
    ax.set(xlim=(0, width), ylim=(0, height))
    ax.axis("off")
    texts = {id(t): t for pair in problems for t in pair[:2] if isinstance(t, Text)}
    for text in texts.values():
        box = text.get_window_extent()
        ax.add_patch(plt.Rectangle((box.x0, box.y0), box.width, box.height,
                                   fill=False, color="red", linewidth=1.5, clip_on=False))
    return marked
