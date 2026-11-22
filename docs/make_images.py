"""Draw every image in the README.

Each picture is made by calling figfont on a real matplotlib figure, so it
shows what the code does today. Run it again after changing the package:

    python docs/make_images.py              # all of them
    python docs/make_images.py hero ticks   # only these

Needs figfont installed (pip install -e ".[mac]"). The map picture needs
cartopy and the measuring picture needs OCR; each is skipped with a message
when its package is missing.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import textwrap
from importlib import resources
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler
from matplotlib import font_manager
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from PIL import Image, ImageDraw, ImageFont

import figfont
import figfont.mpl
from figfont import measure, scale

HERE = Path(__file__).parent
OUT = HERE / "images"
EXAMPLES = HERE / "examples"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#184f95"]
INK, SECOND, MUTED, HAIR = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
RED = (208, 59, 59)
TAG = (42, 120, 214)
PAGE = 5.15       # printed width used in the examples, inches
SHEET = 1700      # pixels across one full-width picture (shown half size in the README)
HALF = 835        # pixels across each of two pictures side by side
ONE = (4.4, 3.1)  # a one-panel example, inches
TWO = (6.4, 2.9)  # a two-panel example

plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": "white",
    "axes.prop_cycle": cycler(color=[BLUE, ORANGE, AQUA]),
    "axes.edgecolor": SECOND, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": SECOND, "ytick.color": SECOND,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})


# ----------------------------------------------------------------------------- pictures

def _font(size: int, bold: bool = False):
    path = font_manager.findfont(font_manager.FontProperties(
        family=["Arial", "Helvetica", "DejaVu Sans"], weight="bold" if bold else "normal"))
    return ImageFont.truetype(path, size)


def new(size, across=HALF, **kw):
    """A figure that comes out `across` pixels wide."""
    return plt.figure(figsize=size, dpi=across / size[0], **kw)


def snap(fig, marks=(), names=(), edge=False) -> Image.Image:
    """The figure as it would be saved, with a red box round each of `marks`
    (display boxes). Text that runs off the figure is kept, as it is when
    saving with bbox_inches="tight"; `edge` draws where the figure ends."""
    fig.canvas.draw()
    dpi = fig.dpi
    width, height = fig.get_size_inches()
    tight = fig.get_tightbbox(fig.canvas.get_renderer())
    pad = 0.06
    x0 = tight.x0 - pad if tight.x0 < 0 else 0.0
    y0 = tight.y0 - pad if tight.y0 < 0 else 0.0
    x1 = tight.x1 + pad if tight.x1 > width else width
    y1 = tight.y1 + pad if tight.y1 > height else height
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches=Bbox.from_extents(x0, y0, x1, y1))
    image = Image.open(buffer).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    if edge:
        left, top, right, bottom = -x0 * dpi, (y1 - height) * dpi, (width - x0) * dpi, y1 * dpi
        for a, b in (((left, top), (right, top)), ((right, top), (right, bottom)),
                     ((right, bottom), (left, bottom)), ((left, bottom), (left, top))):
            steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) // 14)
            for k in range(0, steps, 2):
                p = [a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps]
                q = [a[0] + (b[0] - a[0]) * (k + 1) / steps, a[1] + (b[1] - a[1]) * (k + 1) / steps]
                pen.line(p + q, fill=(137, 135, 129, 255), width=2)
    label = _font(24, True)
    for k, box in enumerate(marks):
        place = [box.x0 - x0 * dpi - 5, y1 * dpi - box.y1 - 5, box.x1 - x0 * dpi + 5, y1 * dpi - box.y0 + 5]
        pen.rounded_rectangle(place, radius=6, fill=RED + (36,), outline=RED + (255,), width=3)
        if k < len(names):
            wide = pen.textlength(names[k], font=label)
            x = min(max(place[0], 4), image.width - wide - 4)
            y = place[1] - 32 if place[1] > 36 else place[3] + 6
            pen.rectangle([x - 4, y - 2, x + wide + 4, y + 28], fill=(255, 255, 255, 235))
            pen.text((x, y), names[k], font=label, fill=RED + (255,))
    return Image.alpha_composite(image, layer).convert("RGB")


def collisions(fig, edges=False):
    """One box, and what is wrong, for each text that figfont.overlaps reports."""
    renderer = fig.canvas.get_renderer()
    found = {}
    for a, b, why in figfont.overlaps(fig, edges):
        boxes, whys = found.setdefault(id(a), ([a.get_window_extent(renderer)], []))
        if isinstance(b, Text):
            boxes.append(b.get_window_extent(renderer))
        if why not in whys:
            whys.append(why)
    return [Bbox.union(boxes) for boxes, _ in found.values()], [", ".join(whys) for _, whys in found.values()]


def tiles(images, captions, name, columns=None, pad=26, gap=30):
    """Pictures in a grid, each under its caption ("Bold part|plain part")."""
    columns = columns or len(images)
    rows = [images[i:i + columns] for i in range(0, len(images), columns)]
    bold, plain = _font(28, True), _font(28)
    head = 52
    widths = [max(row[c].width for row in rows if c < len(row)) for c in range(columns)]
    heights = [max(image.height for image in row) for row in rows]
    sheet = Image.new("RGB", (pad * 2 + sum(widths) + gap * (columns - 1),
                              pad * 2 + sum(heights) + head * len(rows) + gap * (len(rows) - 1)), "white")
    pen = ImageDraw.Draw(sheet)
    y = pad
    for r, row in enumerate(rows):
        x = pad
        for c, image in enumerate(row):
            first, _, rest = captions[r * columns + c].partition("|")
            pen.text((x, y + 6), first, font=bold, fill=INK)
            if rest:
                pen.text((x + pen.textlength(first + "  ", font=bold), y + 6), rest, font=plain, fill=SECOND)
            sheet.paste(image, (x, y + head))
            pen.rectangle([x - 1, y + head - 1, x + image.width, y + head + image.height], outline=HAIR)
            x += widths[c] + gap
        y += head + heights[r] + gap
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / f"{name}.png", optimize=True)
    print(f"wrote {name}.png {sheet.size}")


def run_fit(fig, name):
    """fit() with its printed lines kept, so the build log says which step did the work."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        figfont.fit(fig, name)
    lines = [line for line in out.getvalue().splitlines() if not line.startswith("TEXT DENSITY")]
    print("   " + " | ".join(lines))
    return lines


def before_after(name, build, after="After fit(fig)", before="Before"):
    """`build` returns the figure, then any artists to mark instead of the collisions found."""
    fig, *marked = build()
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    marks = [a.get_window_extent(renderer) for a in marked] if marked else collisions(fig)[0]
    first = snap(fig, marks)
    run_fit(fig, name)
    second = snap(fig)
    tiles([first, second], [before, after], name)
    plt.close(fig)


# ----------------------------------------------------------------------------- the steps of fit

def cover():
    """A legend on the data: to an empty corner, or under a full panel."""
    def corner():
        fig = new(ONE, layout="constrained")
        ax = fig.add_subplot()
        ax.bar(range(6), [9.1, 7.8, 6.9, 3.2, 2.1, 1.4], width=0.8, label="Heating demand")
        ax.set_xticks(range(6), list("ABCDEF"))
        ax.set_xlabel("Region")
        ax.set_ylabel("Energy (MWh per home)")
        return fig, ax.legend(loc="upper left", fontsize=12)

    def under():
        fig = new(ONE)
        ax = fig.add_axes([0.14, 0.2, 0.82, 0.75])
        y, x = np.mgrid[0:1:60j, 0:1:90j]
        field = np.sin(3 * x + 1) + np.cos(4 * y) + 0.6 * x
        zones = np.digitize(field, np.quantile(field, [0.25, 0.5, 0.75]))
        ax.pcolormesh(x, y, zones, cmap=ListedColormap(BLUES), rasterized=True)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_xticks([])
        ax.set_yticks([])
        return fig, ax.legend(handles=[Patch(color=c, label=f"Zone {k + 1}") for k, c in enumerate(BLUES)],
                              loc="lower left", fontsize=12)

    shots = []
    for build, label in ((corner, "cover_corner"), (under, "cover_under")):
        fig, legend = build()
        fig.canvas.draw()
        shots.append(snap(fig, [legend.get_window_extent(fig.canvas.get_renderer())]))
        run_fit(fig, label)
        shots.append(snap(fig))
        plt.close(fig)
    tiles(shots, ["Before|legend on the bars", "After fit(fig)|in the empty corner",
                  "Before|legend on a full panel", "After fit(fig)|under the panel"],
          "fit_cover", columns=2)


def wrap():
    def build():
        fig = new(TWO)
        axes = fig.subplots(1, 2)
        fig.subplots_adjust(left=0.1, right=0.92, top=0.93, bottom=0.3, wspace=0.3)
        x = np.linspace(-20, 15, 60)
        axes[0].plot(x, np.clip(18 - x, 0, None))
        axes[0].set_xlabel("Mean outdoor temperature in winter (°C)", fontsize=14)
        axes[1].plot(x + 20, 40 * np.exp(-(x + 20) / 14), color=ORANGE)
        axes[1].set_xlabel("Daily heating demand per person (kWh)", fontsize=14)
        return (fig,)
    before_after("fit_wrap", build)


def pads():
    def build():
        fig = new(ONE)
        ax = fig.add_axes([0.3, 0.2, 0.65, 0.73])
        ax.plot(np.arange(1980, 2021), 1000 + 4000 * np.linspace(0, 1, 41) ** 2)
        ax.tick_params(labelsize=15)
        ax.set_ylabel("Homes (thousands)", fontsize=15, labelpad=0)
        ax.set_xlabel("Year", fontsize=15, labelpad=0)
        return fig, ax.yaxis.label, ax.xaxis.label
    before_after("fit_pads", build)


def letters():
    def build():
        fig = new((4.4, 4.2))
        axes = fig.subplots(2, 1)
        fig.subplots_adjust(left=0.2, right=0.95, top=0.9, bottom=0.12, hspace=0.55)
        t = np.linspace(0, 12, 100)
        for k, (ax, title) in enumerate(zip(axes, ("Winter", "Summer"))):
            ax.plot(t, np.sin(t / 2 + k) + 1.2, color=(BLUE, ORANGE)[k])
            ax.set_title(title, loc="left", fontsize=13)
            ax.set_ylabel("Demand", fontsize=12)
            box = ax.get_position()
            letter = fig.text(box.x0, box.y1 + 0.02, "ab"[k], fontsize=15, fontweight="bold")
            letter._panel = {"axis": ax, "kind": "letter", "dx": 0.0, "dy": 0.02}
        return (fig,)
    before_after("fit_letters", build)


def ticks():
    def build():
        fig = new(ONE, layout="constrained")
        ax = fig.add_subplot()
        kinds = ["Detached", "Semi-detached", "Terraced", "Apartment", "Mobile home", "Other"]
        ax.bar(kinds, [41, 23, 17, 12, 5, 2], width=0.7)
        ax.tick_params(axis="x", labelsize=12)
        ax.set_ylabel("Share of homes (%)", fontsize=12)
        return (fig,)
    before_after("fit_ticks", build)


def inside():
    def build():
        rng = np.random.default_rng(3)
        fig = new(ONE)
        ax = fig.add_axes([0.16, 0.2, 0.6, 0.73])
        for side in ("top", "right"):
            ax.spines[side].set_visible(True)
        x = rng.uniform(0, 10, 120)
        y = 0.8 * x + rng.normal(0, 1.2, 120)
        points = ax.scatter(x, y, c=y - 0.8 * x, cmap="Blues", s=18, vmin=-4, vmax=3, edgecolors=BLUES[2],
                            linewidths=0.4)
        fig.colorbar(points, cax=fig.add_axes([0.79, 0.2, 0.035, 0.73]), label="Residual")
        ax.set_xlim(0, 10)
        ax.set_ylim(-3, 11)
        ax.set_xlabel("Observed")
        ax.set_ylabel("Modelled")
        note = ax.text(6.3, -1.9, "r = 0.89, n = 120", fontsize=12)
        return fig, note
    before_after("fit_inside", build)


def repel():
    def build():
        fig = new(ONE)
        ax = fig.add_axes([0.16, 0.2, 0.79, 0.73])
        towns = {"Oslo": (2.1, 7.6), "Bergen": (3.0, 5.1), "Stockholm": (6.0, 3.9), "Uppsala": (6.3, 4.35),
                 "Helsinki": (8.2, 6.9)}
        ax.scatter(*zip(*towns.values()), s=42, color=BLUE, zorder=3)
        for name, (x, y) in towns.items():
            ax.text(x + 0.22, y, name, fontsize=13, va="center")
        ax.set_xlim(0, 11)
        ax.set_ylim(2, 9)
        ax.set_xlabel("Winter length (months)")
        ax.set_ylabel("Demand (MWh per home)")
        return (fig,)
    before_after("fit_repel", build)


def legends():
    def build():
        fig = new(TWO, across=HALF)
        fig.set_size_inches(6.4, 3.3)
        axes = fig.subplots(1, 2)
        fig.subplots_adjust(left=0.1, right=0.97, top=0.78, bottom=0.17, wspace=0.3)
        t = np.linspace(0, 10, 80)
        for ax, title in zip(axes, ("North", "South")):
            lines = [ax.plot(t, f(t), label=label)[0] for f, label in
                     ((np.sin, "Observed"), (np.cos, "Modelled"), (lambda v: np.sin(v) * np.cos(v), "Difference"))]
            ax.set_title(title, fontsize=13)
            ax.set_xlabel("Month")
        fig.legend(handles=lines, loc="upper center", ncol=3, fontsize=12, bbox_to_anchor=(0.5, 0.9))
        return (fig,)
    before_after("fit_legends", build)


def _two_maps(fig):
    rng = np.random.default_rng(1)
    axes = fig.subplots(1, 2)
    fig.subplots_adjust(left=0.1, right=0.93, top=0.93, bottom=0.2, wspace=0.25)
    for ax, name in zip(axes, ("Demand (kWh per hour)", "Change since 1980 (%)")):
        image = ax.imshow(rng.random((24, 12)).cumsum(axis=0), aspect="auto", cmap="Blues", origin="lower")
        fig.colorbar(image, ax=ax).set_label(name, fontsize=13)
        ax.set_xlabel("Month", fontsize=13)
        ax.set_ylabel("Hour of day", fontsize=13)
        ax.tick_params(labelsize=12)
    return fig


def space():
    before_after("fit_space", lambda: (_two_maps(new(TWO)),))


def overlaps():
    """overlaps() and report_overlaps(): the three things they look for."""
    rng = np.random.default_rng(1)
    fig = new((10.2, 3.2), across=SHEET)
    a, b, c = fig.subplots(1, 3)
    fig.subplots_adjust(left=0.06, right=0.985, top=0.9, bottom=0.18, wspace=0.3)
    image = a.imshow(rng.random((24, 12)).cumsum(axis=0), aspect="auto", cmap="Blues", origin="lower")
    fig.colorbar(image, ax=a).set_label("Demand (kWh per hour)", fontsize=12)
    a.set_xlabel("Month")
    a.set_ylabel("Hour of day")
    years = np.arange(1980, 2021)
    b.plot(years, 20 + 0.1 * (years - 1980) + rng.normal(0, 0.6, years.size))
    b.set_xlabel("Year")
    b.set_ylabel("Hour of the daily peak", fontsize=12)
    b.text(0.5, 0.9, "The peak comes later each year", transform=b.transAxes, fontsize=12)
    c.bar(["North", "South", "East", "West"], [3.1, 2.4, 1.8, 1.2], width=0.7, color=ORANGE)
    c.set_xlabel("Region")
    c.yaxis.set_label_position("right")
    c.set_ylabel("Change since 1980 (%)", fontsize=12, labelpad=8)
    fig.canvas.draw()
    marks, names = collisions(fig, edges=True)
    picture = snap(fig, marks, names, edge=True)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        figfont.report_overlaps(fig, "peaks.png", edges=True)
    print("   " + out.getvalue().replace("\n", "\n   "))
    (OUT / "overlaps.txt").write_text(out.getvalue())
    tiles([picture], ["overlaps(fig, edges=True)|what it finds, marked in red. The dashed line is the edge of the figure."],
          "overlaps")
    plt.close(fig)


def notes():
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError:
        print("skipped fit_notes (needs cartopy)")
        return

    def build():
        fig = new((6.4, 3.2))
        ax = fig.add_axes([0.02, 0.03, 0.96, 0.94], projection=ccrs.Robinson())
        ax.set_global()
        ax.add_feature(cfeature.LAND, facecolor=BLUES[0], zorder=1)
        ax.coastlines(linewidth=0.5, color=SECOND)
        ax.gridlines(linewidth=0.4, color=HAIR)
        box = dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=MUTED, alpha=0.9, linewidth=0.8)
        north = ax.text(-128, 8, "NDJFM", transform=ccrs.PlateCarree(), fontsize=11,
                        ha="left", va="bottom", bbox=box, zorder=10)
        south = ax.text(-128, -8, "MJJAS", transform=ccrs.PlateCarree(), fontsize=11,
                        ha="left", va="top", bbox=box, zorder=10)
        fig.canvas.draw()
        return fig, north.get_bbox_patch(), south.get_bbox_patch()
    before_after("fit_notes", build)


# ----------------------------------------------------------------------------- whole figures

def _example(width=13.0):
    """A three-panel figure drawn wide, with matplotlib's own 10 pt text."""
    rng = np.random.default_rng(0)
    fig = new((width, 4.3), across=SHEET, layout="constrained")
    a, b, c = fig.subplots(1, 3)
    years = np.arange(1980, 2021)
    a.plot(years, 3000 - 9 * (years - 1980) + rng.normal(0, 60, years.size), label="Observed")
    a.plot(years, 2960 - 8 * (years - 1980), label="Modelled")
    a.set_xlabel("Year")
    a.set_ylabel("Heating degree days per year (°C day)")
    a.legend(loc="lower left")
    kinds = ["Detached", "Semi", "Terrace", "Flat", "Mobile", "Other"]
    b.bar(kinds, [41, 23, 17, 12, 5, 2], width=0.7)
    b.set_ylabel("Share of homes (%)")
    month, hour = np.meshgrid(np.arange(12), np.arange(24))
    demand = (1.2 + np.cos(2 * np.pi * month / 12)) * (1.3 + np.cos(2 * np.pi * (hour - 6) / 24))
    image = c.imshow(demand, aspect="auto", cmap="Blues", origin="lower")
    fig.colorbar(image, ax=c).set_label("Heating demand (kWh per hour)")
    c.set_xlabel("Month of the year")
    c.set_ylabel("Hour of day")
    for letter, ax in zip("abc", (a, b, c)):
        ax.set_title(letter, loc="left", fontweight="bold")
    return fig


def _printed(fig, name):
    """Save the figure as a PDF and read back what its text prints at."""
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    fig.savefig(EXAMPLES / name)
    return figfont.figure_pdf_text(str(EXAMPLES / name), PAGE)


def hero():
    fig = _example()
    drawn = _printed(fig, "before.pdf")
    fig.savefig(EXAMPLES / "before.png", dpi=300)
    first = snap(fig)
    figfont.mpl.set_printed_fonts(fig, PAGE)
    fig.canvas.draw()
    marks, _ = collisions(fig)
    second = snap(fig, marks)
    run_fit(fig, "hero")
    fitted = _printed(fig, "after.pdf")
    fig.savefig(EXAMPLES / "after.png", dpi=300)
    third = snap(fig)
    plt.close(fig)
    print(f"   printed: {drawn.summary()} -> {fitted.summary()}; texts in a collision after resizing: {len(marks)}")
    captions = [
        f"1  As drawn|13 in wide with 10 pt text. On a {PAGE} in page it prints at {drawn.median:.0f} pt.",
        f"2  set_printed_fonts(fig, {PAGE})|Now {fitted.percentile(10):.0f} to {fitted.percentile(90):.0f} pt in print, "
        "but the text collides.",
        "3  fit(fig)|Same sizes. The collisions are gone.",
    ]
    pad, head, gap = 26, 52, 26
    body = _font(round(10 * SHEET / PAGE / 72))
    sheet = Image.new("RGB", (first.width + 2 * pad,
                              pad + sum(head + im.height + gap for im in (first, second, third)) + body.size + pad + 8),
                      "white")
    pen = ImageDraw.Draw(sheet)
    y = pad
    for image, caption in zip((first, second, third), captions):
        lead, _, rest = caption.partition("|")
        pen.text((pad, y + 6), lead, font=_font(28, True), fill=INK)
        pen.text((pad + pen.textlength(lead + "  ", font=_font(28, True)), y + 6), rest, font=_font(28), fill=SECOND)
        sheet.paste(image, (pad, y + head))
        pen.rectangle([pad - 1, y + head - 1, pad + image.width, y + head + image.height], outline=HAIR)
        y += head + image.height + gap
    pen.text((pad, y), "For scale: this line is the 10 pt body text of the paper.", font=body, fill=INK)
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / "hero.png", optimize=True)
    print(f"wrote hero.png {sheet.size}")


def set_fonts():
    """set_printed_fonts: one size for each kind of text, given as it should print."""
    page = 3.4

    def build():
        rng = np.random.default_rng(2)
        fig = new((9.0, 5.6), layout="constrained")
        ax = fig.add_subplot()
        years = np.arange(1980, 2021)
        ax.plot(years, 3000 - 9 * (years - 1980) + rng.normal(0, 60, years.size), label="Observed")
        ax.plot(years, 2960 - 8 * (years - 1980), label="Modelled")
        ax.set_title("Heating demand", loc="left")
        ax.set_xlabel("Year")
        ax.set_ylabel("Degree days per year")
        legend = ax.legend(loc="upper right")
        source = fig.text(0.02, 0.015, "Source: station records", ha="left", va="bottom", color=SECOND)
        fig.get_layout_engine().set(rect=(0.01, 0.09, 0.97, 0.9))
        return fig, ax, legend, source

    fig, *_ = build()
    first = snap(fig)
    plt.close(fig)
    fig, ax, legend, source = build()
    sizes = figfont.mpl.SIZES
    figfont.mpl.set_printed_fonts(fig, page)
    run_fit(fig, "set_printed_fonts")
    second = snap(fig).convert("RGBA")
    renderer = fig.canvas.get_renderer()
    height = fig.canvas.get_width_height()[1]
    layer = Image.new("RGBA", second.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    font = _font(22, True)
    targets = [("tick", [ax.get_xticklabels()[2]], "above"), ("label", [ax.xaxis.label], "right"),
               ("title", [ax._left_title], "right"), ("legend", legend.get_texts(), "below"),
               ("other", [source], "right")]
    for key, artists, where in targets:
        box = Bbox.union([a.get_window_extent(renderer) for a in artists])
        x0, y0, x1, y1 = box.x0 - 5, height - box.y1 - 5, box.x1 + 5, height - box.y0 + 5
        pen.rectangle([x0, y0, x1, y1], outline=TAG + (255,), width=2)
        tag = f"{key}  {sizes[key]} pt"
        wide = pen.textlength(tag, font=font) + 16
        if where == "right":
            tx, ty = x1 + 2, (y0 + y1) / 2 - 15
        elif where == "above":
            tx, ty = (x0 + x1) / 2 - wide / 2, y0 - 32
        else:
            tx, ty = x1 - wide, y1 + 2
        pen.rectangle([tx, ty, tx + wide, ty + 30], fill=TAG + (255,))
        pen.text((tx + 8, ty + 3), tag, font=font, fill="white")
    second = Image.alpha_composite(second, layer).convert("RGB")
    plt.close(fig)
    tiles([first, second], [f"Before|drawn 9 in wide, printed {page} in wide",
                            f"set_printed_fonts(fig, {page})|each kind of text at its printed size"],
          "set_printed_fonts")


def suggest():
    """suggest_size: small panels get smaller text, between 6 and 8 pt."""
    def grid():
        rng = np.random.default_rng(4)
        fig = new((PAGE, 2.5), across=SHEET)
        axes = fig.subplots(2, 5, sharex=True, sharey=True)
        fig.subplots_adjust(left=0.085, right=0.985, top=0.9, bottom=0.18, wspace=0.22, hspace=0.5)
        t = np.arange(1980, 2021)
        for k, ax in enumerate(axes.flat):
            ax.plot(t, 100 + (k - 4) * 0.4 * (t - 1980) + rng.normal(0, 4, t.size), linewidth=1)
            ax.set_title(f"Region {k + 1}", fontsize=8)
            ax.tick_params(labelsize=8, length=2)
            ax.set_xticks([1980, 2000, 2020])
        for ax in axes[1]:
            ax.set_xlabel("Year", fontsize=8)
        for ax in axes[:, 0]:
            ax.set_ylabel("Index", fontsize=8)
        return fig

    fig = grid()
    fig.canvas.draw()
    narrow = figfont.density(fig)["ems_min"]
    size = figfont.suggest_size(fig, printed_pt=8)
    marks, _ = collisions(fig)
    first = snap(fig, marks)
    plt.close(fig)
    fig = grid()
    figfont.mpl.scale_fonts(fig, size / 8)
    fig.canvas.draw()
    after = figfont.density(fig)["ems_min"]
    left = len(figfont.overlaps(fig))
    second = snap(fig)
    plt.close(fig)
    print(f"   narrowest panel {narrow:.1f} text heights at 8 pt ({len(marks)} collisions) -> "
          f"suggest {size:g} pt ({after:.1f}, {left} collisions)")
    tiles([first, second],
          [f"8 pt|the narrowest panel is {narrow:.0f} text heights wide",
           f"suggest_size(fig) says {size:g} pt|scale_fonts(fig, {size:g} / 8): now {after:.0f} text heights wide"],
          "suggest_size", columns=1)


# ----------------------------------------------------------------------------- measuring

def measuring():
    """figure_ocr: each line of text found in a PNG, with the size it prints at."""
    path = EXAMPLES / "after.png"
    if not path.exists():
        hero()
    try:
        page = measure.render(str(path), PAGE, measure.DPI)
        found = measure._ocr_boxes(page, measure.DPI)
    except ImportError:
        print("skipped measure (needs ocrmac or pytesseract)")
        return
    per_point = measure.calibration(measure.DPI)
    shrink = SHEET / page.width
    image = page.resize((SHEET, round(page.height * shrink)), Image.LANCZOS).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    label = _font(19, True)
    found = [(points / per_point.get(measure._kind(text), 1.0), tuple(v * shrink for v in box))
             for points, text, box in found]
    taken = [(l - 3, t - 3, r + 3, b + 3) for _, (l, t, r, b) in found]

    def free(x, y, wide, high):
        if x < 0 or y < 0 or x + wide > image.width or y + high > image.height:
            return False
        return all(x + wide <= l or x >= r or y + high <= t or y >= b for l, t, r, b in taken)

    for points, (left, top, right, bottom) in found:
        pen.rectangle([left - 3, top - 3, right + 3, bottom + 3], outline=TAG + (255,), width=2)
    for points, (left, top, right, bottom) in found:   # each size goes in the first clear place beside its box
        tag = f"{points:.1f}"
        wide, high = pen.textlength(tag, font=label) + 10, 25
        across, down = (left + right) / 2 - wide / 2, (top + bottom) / 2 - high / 2
        places = [(right + 4, down), (across, top - high - 4), (left - wide - 4, down), (across, bottom + 4),
                  (right + 4, top - high - 4), (left - wide - 4, top - high - 4)]
        if bottom - top > right - left:
            places = [places[1], places[3], (left + 2, bottom + 4), (right - wide - 2, bottom + 4),
                      places[0], places[2]]
        spot = next(((x, y) for x, y in places if free(x, y, wide, high)), None)
        if spot is None:
            continue
        x, y = spot
        taken.append((x, y, x + wide, y + high))
        pen.rectangle([x, y, x + wide, y + high], fill=TAG + (255,))
        pen.text((x + 5, y + 1), tag, font=label, fill="white")
    image = Image.alpha_composite(image, layer).convert("RGB")
    ocr = figfont.figure_ocr(str(path), PAGE)
    exact = figfont.figure_pdf_text(str(EXAMPLES / "after.pdf"), PAGE)
    print(f"   OCR {ocr.summary()}; exact from the PDF {exact.summary()}")
    tiles([image], [f"figure_ocr(\"after.png\", {PAGE})|every line it reads, with the size it prints at. "
                    f"Median {ocr.median:.1f} pt; the PDF of the same figure says {exact.median:.1f} pt."], "measure")


def paper():
    """pdf_figure_text: the figure text of a compiled paper, apart from its body text."""
    import pymupdf
    if not (EXAMPLES / "after.pdf").exists():
        hero()
    words = ("Heating demand falls as winters warm, but not evenly through the day. The decline is largest in the "
             "early morning, when demand peaks, and smallest in the afternoon. Detached homes make up the largest "
             "share of the stock and lose the most heat for each degree of cold. ")
    doc = pymupdf.open()
    page = doc.new_page(width=468, height=388)
    left, wide = (468 - PAGE * 72) / 2, PAGE * 72
    body = dict(fontname="tiro", fontsize=10, align=pymupdf.TEXT_ALIGN_JUSTIFY)
    page.insert_textbox(pymupdf.Rect(left, 22, left + wide, 130), words * 2, **body)
    figure = pymupdf.open(EXAMPLES / "after.pdf")
    high = wide * figure[0].rect.height / figure[0].rect.width
    page.show_pdf_page(pymupdf.Rect(left, 118, left + wide, 118 + high), figure, 0)
    page.insert_textbox(pymupdf.Rect(left, 126 + high, left + wide, 154 + high),
                        "Fig. 1 Heating degree days (a), the housing stock (b) and demand through the day and year (c).",
                        fontname="tibo", fontsize=9)
    page.insert_textbox(pymupdf.Rect(left, 150 + high, left + wide, 376), words * 2, **body)
    doc.save(EXAMPLES / "paper.pdf", garbage=3, deflate=True)
    result = figfont.pdf_figure_text(str(EXAMPLES / "paper.pdf"))
    print(f"   {result.summary()}")

    page = pymupdf.open(EXAMPLES / "paper.pdf")[0]
    zoom = SHEET / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    spans = [span for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])
             for span in line["spans"] if span["text"].strip()]
    kept = [span for span in spans if not span["font"].startswith("Times")]
    assert len(kept) == result.n, (len(kept), result.n)
    for span in spans:
        l, t, r, b = (v * zoom for v in span["bbox"])
        if span in kept:
            pen.rectangle([l - 2, t - 1, r + 2, b + 1], outline=TAG + (255,), width=2)
        else:
            pen.rectangle([l - 2, t, r + 2, b], fill=(255, 255, 255, 150))
    image = Image.alpha_composite(image, layer).convert("RGB")
    tiles([image], [f"pdf_figure_text(\"paper.pdf\")|{result.n} pieces of figure text, median "
                    f"{result.median:.1f} pt. The body text and the caption are not counted."], "paper")


def _ref():
    return json.loads(resources.files("figfont").joinpath("reference.json").read_text())


def _range_row(ax, y, v, strong=False):
    """One row: the middle 80 % of papers (thin), the middle half (thick) and the median (dot)."""
    ax.plot(v["paper_medians_p10_p90"], [y, y], color=SECOND if strong else BLUES[1], linewidth=1.4,
            solid_capstyle="round", zorder=2)
    ax.plot(v["paper_medians_p25_p75"], [y, y], color=INK if strong else BLUES[2], linewidth=5,
            solid_capstyle="butt", zorder=3)
    ax.plot(v["median_pt"], y, "o", color="white", markersize=6.5, markeredgecolor=INK if strong else BLUES[3],
            markeredgewidth=1.6, zorder=4)


def reference():
    """reference() and verdict(): where published papers sit."""
    ref = _ref()
    everything = ref["all"]
    low, high = everything["paper_medians_p25_p75"]
    edges = np.array(ref["histogram"]["edges_pt"])
    text, ocr = np.array(ref["histogram"]["text"]), np.array(ref["histogram"]["ocr"])
    fields = sorted(ref["fields"].items(), key=lambda item: item[1]["median_pt"])
    rows = [(f"All {everything['papers']:,} papers", everything)] + fields
    lim = (3.5, 11)

    fig = new((9.4, 6.9), across=SHEET)
    top = fig.add_axes([0.335, 0.47, 0.57, 0.4])
    for ax in (top,):
        ax.axvspan(low, high, color=HAIR, alpha=0.6, linewidth=0)
        ax.axvline(6, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    width = edges[1] - edges[0]
    top.bar(edges[:-1] + width / 2, text, width - 0.035, color=BLUE)
    top.bar(edges[:-1] + width / 2, ocr, width - 0.035, bottom=text, color=ORANGE)
    share = ref["methods"]["text"]["papers"] / everything["papers"]
    fig.text(0.03, 0.83, "How each paper was read", fontsize=10.5, fontweight="bold", color=INK, va="center")
    for y, colour, words in ((0.775, BLUE, f"exact sizes: the paper stores\nits figure text ({share * 100:.0f} % of papers)"),
                             (0.685, ORANGE, f"by OCR: its figures are\nsaved as images ({100 - share * 100:.0f} %)")):
        fig.patches.append(plt.Rectangle((0.03, y - 0.011), 0.016, 0.022, transform=fig.transFigure, color=colour))
        fig.text(0.056, y + 0.013, words, fontsize=10, color=SECOND, va="top", linespacing=1.25)
    top.set_xlim(*lim)
    top.set_ylabel("Papers", fontsize=11)
    top.tick_params(labelsize=10, labelbottom=False)
    top.grid(axis="y", color=HAIR, linewidth=0.8)
    top.set_axisbelow(True)
    place = top.get_xaxis_transform()
    for x, word, align in ((low - 0.12, "small", "right"), ((low + high) / 2, "ok", "center"), (high + 0.12, "large", "left")):
        top.text(x, 1.02, word, transform=place, ha=align, va="bottom", fontsize=11.5, fontweight="bold",
                 color=INK if word == "ok" else SECOND)
    top.text((low + high) / 2, 1.085, "middle half of papers", transform=place, ha="center", va="bottom",
             fontsize=10, color=SECOND)
    fig.add_artist(plt.Line2D([0.03, 0.03], [0.515, 0.585], color=MUTED, linewidth=1, linestyle=(0, (3, 3))))
    fig.text(0.056, 0.588, "6 pt: verdict also says small\nwhen a tenth of a figure's\ntext is under this", fontsize=10,
             color=SECOND, va="top", linespacing=1.25)

    ax = fig.add_axes([0.335, 0.1, 0.57, 0.31])
    ax.axvspan(low, high, color=HAIR, alpha=0.6, linewidth=0)
    ax.axvline(6, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    for i, (name, v) in enumerate(rows):
        _range_row(ax, i, v, strong=not i)
        if i:
            ax.text(lim[1] + 0.62, i, f"{v['papers']:,}", va="center", ha="right", fontsize=10, color=SECOND, clip_on=False)
    ax.text(lim[1] + 0.62, -0.05, "papers", va="center", ha="right", fontsize=10, color=SECOND, clip_on=False)
    ax.set_yticks(range(len(rows)), [name for name, _ in rows], fontsize=10.5)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.get_yticklabels()[0].set_color(INK)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=10)
    ax.set_xlim(*lim)
    ax.set_ylim(len(rows) - 0.4, -0.75)
    ax.set_xlabel("Size of a paper's figure text as printed (pt): the median of its labels", fontsize=11)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=HAIR, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.annotate("median", (everything["median_pt"], 0), xytext=(0, 8), textcoords="offset points",
                ha="center", va="bottom", fontsize=9.5, color=SECOND)
    ax.annotate("8 in 10 papers", (everything["paper_medians_p10_p90"][1], 0), xytext=(8, 0),
                textcoords="offset points", ha="left", va="center", fontsize=9.5, color=SECOND)
    fig.savefig(OUT / "reference.png")
    plt.close(fig)
    print("wrote reference.png")


def journals():
    """reference(journal=...): every journal that has its own numbers, by field."""
    ref = _ref()
    low, high = ref["all"]["paper_medians_p25_p75"]
    groups = []
    for field in sorted(ref["fields"], key=lambda f: ref["fields"][f]["median_pt"]):
        mine = sorted(((n, v) for n, v in ref["journals"].items() if v["field"] == field), key=lambda item: item[1]["median_pt"])
        if mine:
            groups.append((field, mine))
    # two columns of about the same length, a field never split
    rows = [len(mine) + 2 for _, mine in groups]
    best = min(range(2 ** len(groups)), key=lambda pick: abs(
        sum(r for i, r in enumerate(rows) if pick >> i & 1) - sum(r for i, r in enumerate(rows) if not pick >> i & 1)))
    columns = [[g for i, g in enumerate(groups) if best >> i & 1], [g for i, g in enumerate(groups) if not best >> i & 1]]
    columns.sort(key=lambda column: -sum(len(mine) + 2 for _, mine in column))
    depth = max(sum(len(mine) + 2 for _, mine in column) for column in columns)
    lim = (4, 10.5)
    fig = new((9.4, 0.55 + 0.205 * depth), across=SHEET)
    for side, column in enumerate(columns):
        left, wide = 0.315 + 0.5 * side, 0.14
        ax = fig.add_axes([left, 0.55 / fig.get_figheight() * 0.8, wide, 1 - 0.75 / fig.get_figheight()])
        ax.axvspan(low, high, color=HAIR, alpha=0.6, linewidth=0)
        ax.axvline(6, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
        y, ticks, names = 0, [], []
        for field, mine in column:
            ax.text((0.01 + 0.5 * side - left) / wide, y, field, transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=10.5,
                    fontweight="bold", color=INK)
            ax.text(1.04, y, "papers", transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=8.5, color=MUTED)
            y += 1
            for name, v in mine:
                _range_row(ax, y, v)
                ax.text(1.04, y, f"{v['papers']}", transform=ax.get_yaxis_transform(), ha="left", va="center",
                        fontsize=8.5, color=SECOND)
                ticks.append(y)
                names.append(textwrap.fill(name, 40))
                y += 1
            y += 1
        ax.set_yticks(ticks, names, fontsize=8.8, linespacing=0.95)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", labelsize=9)
        ax.set_xlim(*lim)
        ax.set_xticks([4, 6, 8, 10])
        ax.set_ylim(depth - 1.4, -0.7)
        ax.set_xlabel("Figure text as printed (pt)", fontsize=9.5)
        ax.spines["left"].set_visible(False)
        ax.grid(axis="x", color=HAIR, linewidth=0.8)
        ax.set_axisbelow(True)
    fig.savefig(OUT / "journals.png")
    plt.close(fig)
    print("wrote journals.png")


def small_text():
    """The small end, and figure text against the caption."""
    ref = _ref()
    fields = [(name, v) for name, v in ref["fields"].items() if "small_text" in v]
    rows = [("All papers", ref["all"])] + sorted(fields, key=lambda item: -item[1]["small_text"]["share_with_text_under_6pt"])
    fig = new((9.4, 3.7), across=SHEET)
    ax = fig.add_axes([0.235, 0.17, 0.26, 0.62])
    for i, (name, v) in enumerate(rows):
        six, five = v["small_text"]["share_with_text_under_6pt"] * 100, v["small_text"]["share_with_text_under_5pt"] * 100
        ax.barh(i, six, 0.62, color=BLUES[1], label="under 6 pt" if not i else None)
        ax.barh(i, five, 0.62, color=BLUES[3], label="under 5 pt" if not i else None)
        ax.text(six + 2, i, f"{six:.0f} %", va="center", ha="left", fontsize=9.5, color=SECOND)
        if five >= 16:
            ax.text(five - 1.5, i, f"{five:.0f} %", va="center", ha="right", fontsize=9.5, color="white")
    ax.set_yticks(range(len(rows)), [name for name, _ in rows], fontsize=10)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=9.5)
    ax.set_xlim(0, 100)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.set_xlabel("Papers (%)", fontsize=10.5)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=HAIR, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2, fontsize=9.5, handlelength=1.1, borderaxespad=0.1,
              columnspacing=1.2, frameon=False)
    fig.text(0.02, 0.97, "Papers in which a tenth of the figure text is smaller than", fontsize=11, fontweight="bold",
             color=INK, va="top")
    fig.text(0.02, 0.895, f"{ref['all']['small_text']['papers']:,} papers with exact sizes", fontsize=9.5, color=SECOND, va="top")

    ax = fig.add_axes([0.6, 0.17, 0.375, 0.62])
    edges = np.array(ref["caption_ratio_histogram"]["edges"])
    count = np.array(ref["caption_ratio_histogram"]["papers"])
    width = edges[1] - edges[0]
    ax.bar(edges[:-1] + width / 2, count, width - 0.008, color=BLUES[2])
    ax.axvline(1, color=INK, linewidth=1)
    ax.text(1.02, 0.97, "same size as\nthe caption", transform=ax.get_xaxis_transform(), ha="left", va="top",
            fontsize=9.5, color=SECOND, linespacing=1.15)
    middle = ref["all"]["relative_to_caption"]
    ax.axvline(middle, color=INK, linewidth=1, linestyle=(0, (3, 2)))
    ax.text(middle - 0.02, 0.97, f"typical\npaper: {middle:.2f}", transform=ax.get_xaxis_transform(), ha="right", va="top",
            fontsize=9.5, color=SECOND, linespacing=1.15)
    ax.set_xlim(0.4, 1.6)
    ax.set_ylim(0, count.max() * 1.18)
    ax.set_xlabel("Figure text size ÷ caption size", fontsize=10.5)
    ax.set_ylabel("Papers", fontsize=10.5)
    ax.tick_params(labelsize=9.5)
    ax.grid(axis="y", color=HAIR, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.text(0.545, 0.97, "Figure text against the paper's own caption", fontsize=11, fontweight="bold", color=INK, va="top")
    fig.text(0.545, 0.895, "The caption is usually a point or two below the body text", fontsize=9.5, color=SECOND, va="top")
    fig.savefig(OUT / "small_text.png")
    plt.close(fig)
    print("wrote small_text.png")


def reference_table():
    """docs/reference.md: the numbers for every field and journal, as a table."""
    ref = _ref()
    everything = ref["all"]

    def row(name, v):
        low, high = v["paper_medians_p25_p75"]
        wide_low, wide_high = v["paper_medians_p10_p90"]
        return (f"| {name} | {v['papers']:,} | {v['median_pt']:.1f} | {low:.1f} to {high:.1f} | "
                f"{wide_low:.1f} to {wide_high:.1f} | {v['read_by_ocr'] * 100:.0f} % |")

    head = ["| | Papers | Median (pt) | Middle half of papers (pt) | 8 in 10 papers (pt) | Read by OCR |",
            "|---|---:|---:|---:|---:|---:|"]
    lines = ["# Figure text in published papers", "",
             f"The size of figure text as printed, in {everything['papers']:,} journal articles from "
             f"{everything['journals']} journals. Each paper counts once, with the median size of the text in its",
             "figures. This page is written by `docs/make_images.py reference_table` from",
             "[`figfont/reference.json`](../figfont/reference.json); the [README](../README.md#3-compare-with-published-papers)",
             "says how the papers were measured.", "",
             "*Read by OCR* is the share of a row's papers whose figures hold no stored text, so their sizes were",
             "read from the picture. Those sizes are close, not exact.", "",
             "## All papers and fields", "", *head, row("**All papers**", everything)]
    lines += [row(name, v) for name, v in sorted(ref["fields"].items(), key=lambda item: item[1]["median_pt"])]
    for field in sorted(ref["fields"]):
        mine = sorted((n for n, v in ref["journals"].items() if v["field"] == field), key=str.lower)
        if mine:
            lines += ["", f"## {field}", "", *head, *(row(name, ref["journals"][name]) for name in mine)]
    lines += ["", f"A journal needs {min(v['papers'] for v in ref['journals'].values())} or more measured papers "
                  "to have its own row. Papers from other journals count in their field and in the total.", ""]
    (OUT.parent / "reference.md").write_text("\n".join(lines))
    print("wrote reference.md")


def scaling():
    """The arithmetic: drawn width, printed width, and panels side by side."""
    drawn_w, drawn_pt, target = 13.0, 10.0, 8.0
    prints = scale.printed_pt(drawn_pt, drawn_w, PAGE)
    need = scale.drawn_pt_for(target, drawn_w, PAGE)
    factor = scale.font_scale_for(target, prints)
    panel = scale.panel_width_for(PAGE, 3, gap=0.15, margin=0.1)
    whole = scale.stitched_width(panel, 3, gap=0.15, margin=0.1)

    fig = new((9.6, 5.6), across=SHEET)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 14)
    ax.set_aspect("equal")
    ax.axis("off")
    mono = {"family": ["Menlo", "DejaVu Sans Mono", "monospace"], "fontsize": 10}

    def sheet(x, y, w, h, face="white"):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=face, edgecolor=SECOND, linewidth=1.2))

    def span(x0, x1, y, text, above=False):
        ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", color=MUTED, linewidth=1, shrinkA=0, shrinkB=0))
        ax.text((x0 + x1) / 2, y + (0.2 if above else -0.25), text, ha="center", va="bottom" if above else "top",
                fontsize=10, color=SECOND)

    # drawn and printed, to the same scale (1 unit = 1 inch)
    top, h1 = 13.3, 4.3
    sheet(0.6, top - h1, drawn_w, h1, face="#f6f9fe")
    ax.text(0.6 + drawn_w / 2, top - h1 / 2, "Aa", ha="center", va="center_baseline", fontsize=drawn_pt * 4.4, color=BLUE)
    span(0.6, 0.6 + drawn_w, top - h1 - 0.35, f"drawn_width = {drawn_w:g} in, text set at {drawn_pt:g} pt")
    h2, x2 = h1 * PAGE / drawn_w, 17.2
    sheet(x2, top - h1 / 2 - h2 / 2, PAGE, h2, face="#f6f9fe")
    ax.text(x2 + PAGE / 2, top - h1 / 2, "Aa", ha="center", va="center_baseline", fontsize=prints * 4.4, color=BLUE)
    span(x2, x2 + PAGE, top - h1 / 2 - h2 / 2 - 0.35, f"printed_width = {PAGE} in")
    ax.annotate("", (x2 - 0.4, top - h1 / 2), (0.6 + drawn_w + 0.4, top - h1 / 2),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.4))
    ax.text((0.6 + drawn_w + x2) / 2, top - h1 / 2 + 0.3, f"× {PAGE / drawn_w:.2f}", ha="center", va="bottom",
            fontsize=11, color=INK)
    lines = [
        (f"printed_pt({drawn_pt:g}, {drawn_w:g}, {PAGE})", f"{prints:.2f} pt", "what the text prints at"),
        (f"drawn_pt_for({target:g}, {drawn_w:g}, {PAGE})", f"{need:.2f} pt", f"set it to this to print at {target:g} pt"),
        (f"font_scale_for({target:g}, {prints:.2f})", f"{factor:.2f}", "or multiply every font by this"),
    ]
    for k, (call, result, meaning) in enumerate(lines):
        y = 7.25 - 0.72 * k
        ax.text(0.6, y, call, **mono, color=INK, va="center")
        ax.text(8.4, y, "→  " + result, **mono, color=BLUE, va="center", fontweight="bold")
        ax.text(12.3, y, meaning, fontsize=10, color=SECOND, va="center")

    # panels side by side
    ax.plot([0.6, 23.4], [5.05, 5.05], color=HAIR, linewidth=1)
    unit = 1.85  # drawing units per inch here, so the page is easy to see
    x0, y0, ph = 0.6, 1.5, 2.0
    sheet(x0, y0 - 0.1 * unit, whole * unit, ph + 0.2 * unit)
    for k in range(3):
        left = x0 + (0.1 + k * (panel + 0.15)) * unit
        sheet(left, y0, panel * unit, ph, face=BLUES[0])
        ax.text(left + panel * unit / 2, y0 + ph / 2, "abc"[k], ha="center", va="center", fontsize=13,
                color=BLUES[3], fontweight="bold")
    span(x0, x0 + whole * unit, y0 - 0.1 * unit - 0.3, f"printed_width = {PAGE} in")
    first = x0 + 0.1 * unit
    span(first, first + panel * unit, y0 + ph + 0.55, f"{panel:.2f} in", above=True)
    tx = 11.0
    ax.text(tx, 3.7, "panel_width_for(5.15, columns=3, gap=0.15, margin=0.1)", **mono, color=INK, va="center")
    ax.text(tx, 3.1, f"→  {panel:.2f} in", **mono, color=BLUE, va="center", fontweight="bold")
    ax.text(tx, 2.0, f"stitched_width({panel:.2f}, columns=3, gap=0.15, margin=0.1)", **mono, color=INK, va="center")
    ax.text(tx, 1.4, f"→  {whole:.2f} in", **mono, color=BLUE, va="center", fontweight="bold")
    fig.savefig(OUT / "scale.png")
    plt.close(fig)
    print("wrote scale.png")


ALL = {"hero": hero, "scale": scaling, "measure": measuring, "paper": paper, "reference": reference, "journals": journals, "small_text": small_text, "reference_table": reference_table,
       "set_printed_fonts": set_fonts, "suggest_size": suggest, "overlaps": overlaps,
       "cover": cover, "wrap": wrap, "pads": pads, "letters": letters, "ticks": ticks,
       "inside": inside, "repel": repel, "legends": legends, "space": space, "notes": notes}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or ALL:
        print(name)
        ALL[name]()
