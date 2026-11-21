"""Keep figure text from colliding after a font change.

A figure laid out at one font size and then printed bigger (plotstyle.scale_text)
keeps its old spacing, so labels can land on each other. fit() finds every
pair of touching text and fixes it with the smallest change that works, in
this order:

  0. cover  a legend lying on what its panel draws (a map, bars) moves to an
            empty corner of the panel, or, when there is none, under the
            panel with its entries in a row;
  1. wrap   a panel title, axis label or colour-bar label longer than its
            panel or bar, that touches other text, goes onto two lines
            (the words stay the same);
     pads   an axis or colour-bar label keeps 0.3 of its font size from
            its tick labels (a pad set in points does not grow with the font);
  2. letters a panel letter on its own axis labels moves left, past them,
            and so do the other letters in its column, so they stay aligned;
  3. ticks  tick labels that touch their neighbours tilt 30 degrees;
     inside a note inside a panel that runs past its side moves back in;
     repel  two notes inside one panel push apart vertically;
     legend a legend that touches a label moves away from it;
  Cartopy coordinate labels are redrawn by cartopy on every draw; call
  pad_cartopy_labels() so cartopy itself keeps a gap between them.

  4. space  text that still touches a neighbouring panel's text gets more
            space between the panels, in steps: wspace for side by side;
            for rows, hspace and a taller figure (the width, which sets
            the print scale, never changes).

Nothing else changes: no sizes, colours, data or wording. report() prints
what is left, so a figure never ships with text on top of text unseen.
"""
from __future__ import annotations

import os
import re

import numpy as np
from matplotlib.text import Annotation, Text

GAP = 3.0       # px kept between text after a fix
STEP = 0.04     # gridspec wspace / hspace added per spacing step
MAX_STEPS = 30


# ----------------------------------------------------------------------------- geometry

def _renderer(figure):
    figure.canvas.draw()
    return figure.canvas.get_renderer()


def _extent(text, renderer):
    """The text's own box; an annotation's would also include its arrow."""
    return Text.get_window_extent(text, renderer)


def _quad(text, renderer) -> np.ndarray:
    """The four corners of the text's ink box in display pixels, rotation included."""
    box = _extent(text, renderer)
    angle = text.get_rotation() % 180
    if abs(angle) < 0.5:
        return np.array([[box.x0, box.y0], [box.x1, box.y0], [box.x1, box.y1], [box.x0, box.y1]])
    # A rotated text's window extent is the box around the rotated rectangle;
    # rebuild the rectangle itself from its upright size, around the same centre.
    rotation = text.get_rotation()
    text.set_rotation(0)
    upright = _extent(text, renderer)
    text.set_rotation(rotation)
    w, h = upright.width / 2, upright.height / 2
    c = np.radians(rotation)
    r = np.array([[np.cos(c), -np.sin(c)], [np.sin(c), np.cos(c)]])
    corners = np.array([[-w, -h], [w, -h], [w, h], [-w, h]]) @ r.T
    return corners + [(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2]


def _touch(a: np.ndarray, b: np.ndarray, pad: float = 0.5) -> bool:
    """Separating-axis test for two convex quads (pad px of overlap allowed)."""
    for quad in (a, b):
        for i in range(4):
            edge = quad[(i + 1) % 4] - quad[i]
            normal = np.array([-edge[1], edge[0]])
            norm = np.hypot(*normal)
            if norm == 0:
                continue
            normal /= norm
            pa, pb = a @ normal, b @ normal
            if pa.max() <= pb.min() + pad or pb.max() <= pa.min() + pad:
                return False
    return True


def _index(figure):
    """Which panel owns each text, and which tick labels are really drawn.

    Matplotlib does not set .axes on tick and axis labels, so ownership comes
    from walking each axes' children; a colour bar's axes count as its panel's.
    Ticks outside the view keep stale labels that are never drawn: skip them."""
    owner, all_ticks, drawn = {}, set(), set()
    for axes in figure.axes:
        panel = _owner_axes(axes)
        for text in axes.findobj(Text):
            owner.setdefault(id(text), panel)
        for axis in (axes.xaxis, axes.yaxis):
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                all_ticks.update((id(tick.label1), id(tick.label2)))
            if not axes.axison or not axis.get_visible():
                all_ticks.add(id(axis.label))  # axes switched off: nothing on it is drawn
                continue
            for tick in axis._update_ticks():
                drawn.update((id(tick.label1), id(tick.label2)))
    for text in figure.texts:
        tag = getattr(text, "_panel", None)
        if tag is not None:
            owner[id(text)] = tag["axis"]
    figure._textfit_owner = owner
    return all_ticks - drawn


def _texts(figure, renderer) -> list[tuple[Text, np.ndarray]]:
    hidden = _index(figure)
    found = []
    for text in figure.findobj(Text):
        if id(text) in hidden:
            continue
        if not text.get_visible() or not text.get_text().strip() or text.get_alpha() == 0:
            continue
        if text.get_figure() is None:
            continue
        box = _extent(text, renderer)
        if box.width <= 0 or box.height <= 0:
            continue
        if text.get_clip_on() and text.get_clip_box() is not None and not text.get_clip_box().overlaps(box):
            continue  # clipped away, e.g. a tick outside the view
        found.append((text, _quad(text, renderer)))
    return found


def _owner(text):
    """The panel a piece of text belongs to (see _index); None for figure text."""
    figure = text.get_figure()
    return getattr(figure, "_textfit_owner", {}).get(id(text))


# ----------------------------------------------------------------------------- finding

CLEARANCE = 0.3  # text of different panels keeps this many font sizes apart


def _clear_px(a, b, figure) -> float:
    size = min(a.get_fontsize(), b.get_fontsize() if isinstance(b, Text) else a.get_fontsize())
    return CLEARANCE * size * figure.dpi / 72.0


def _plot_areas(figure, renderer):
    """(axes, box quad) for every panel's plot area and colour bar."""
    areas = []
    for axes in figure.axes:
        if not axes.get_visible():
            continue
        box = axes.get_window_extent(renderer)
        areas.append((axes, np.array([[box.x0, box.y0], [box.x1, box.y0], [box.x1, box.y1], [box.x0, box.y1]])))
    return areas


def overlaps(figure, edges: bool = False):
    """[(text_a, text_b | axes | None, why)] for: text touching text (text of
    different panels must also keep a small gap), text lying on another
    panel's plot area or colour bar, and (edges=True) text off the figure.
    Off-figure is meaningless when saving with bbox="tight"."""
    renderer = _renderer(figure)
    found = _texts(figure, renderer)
    areas = _plot_areas(figure, renderer)
    edge = figure.bbox
    problems = []
    for i, (a, qa) in enumerate(found):
        if edges and (qa[:, 0].min() < edge.x0 - 2 or qa[:, 0].max() > edge.x1 + 2
                      or qa[:, 1].min() < edge.y0 - 2 or qa[:, 1].max() > edge.y1 + 2):
            problems.append((a, None, "off the figure"))
        oa = _owner(a)
        for b, qb in found[i + 1:]:
            ob = _owner(b)
            apart = (oa is not None and ob is not None and oa is not ob) or any(
                getattr(t, "_panel", {}).get("kind") == "letter" for t in (a, b))
            if _touch(qa, qb, -_clear_px(a, b, figure) if apart else 0.5):
                problems.append((a, b, "overlap"))
        if oa is None:
            continue
        own = oa.get_window_extent(renderer)
        for axes, qb in areas:
            if _owner_axes(axes) is oa:
                continue  # its own panel or its own colour bar
            box = axes.get_window_extent(renderer)
            if np.allclose(box.bounds, own.bounds, atol=1.0):
                continue  # a twin of its panel
            if box.x0 <= own.x0 and box.y0 <= own.y0 and box.x1 >= own.x1 and box.y1 >= own.y1:
                continue  # its panel is an inset of this one
            if _touch(qa, qb, -_clear_px(a, a, figure) / 2):
                problems.append((a, axes, "on another panel"))
    return problems


def report(figure, name: str = "", edges: bool = False) -> int:
    """Print each text collision in `figure`; returns how many."""
    problems = overlaps(figure, edges)
    for a, b, why in problems:
        other = (f" <-> {b.get_text()[:40]!r}" if isinstance(b, Text)
                 else " <-> a neighbouring panel" if b is not None else "")
        print(f"TEXT {why.upper()} {name}: {a.get_text()[:40]!r}{other}", flush=True)
    if not problems:
        print(f"TEXT OK {name}: no overlaps", flush=True)
    return len(problems)


# ----------------------------------------------------------------------------- fixing

def _wrapped(s: str, lines: int = 2) -> str:
    """s on `lines` lines, split at the spaces nearest equal lengths (never
    inside $...$); a deliberate wide gap ("predicted   R² = 0.52") first."""
    if "\n" in s or lines < 2:
        return s
    gap = re.search(r"(?<=\S) {2,}(?=\S)", s)
    if lines == 2 and gap and s[:gap.start()].count("$") % 2 == 0:
        return f"{s[:gap.start()]}\n{s[gap.end():]}"
    spaces, inside = [], False
    for i, ch in enumerate(s):
        if ch == "$":
            inside = not inside
        elif ch == " " and not inside and 0 < i < len(s) - 1 and s[i - 1] != " ":
            spaces.append(i)
    if not spaces:
        return s
    cuts = []
    for k in range(1, lines):
        target = len(s) * k / lines
        free = [i for i in spaces if i not in cuts and (not cuts or i > cuts[-1])]
        if not free:
            break
        cuts.append(min(free, key=lambda i: abs(i - target)))
    parts, last = [], 0
    for cut in cuts:
        parts.append(s[last:cut].strip())
        last = cut
    parts.append(s[last:].strip())
    return "\n".join(p for p in parts if p)


def wrap(figure) -> int:
    """Two lines for a panel title or axis label longer than its panel that
    touches other text, and two or three for any colour-bar label longer than
    its bar (always, so matching bars look alike). Returns how many."""
    touching = {id(t) for a, b, _ in overlaps(figure) for t in (a, b) if isinstance(t, Text)}
    renderer = _renderer(figure)
    count = 0

    def fit_to(text, length, along_x=True, always=False):
        nonlocal count, renderer
        was = text.get_text()
        if not was.strip():
            return
        box = _extent(text, renderer)
        size = box.width if along_x else box.height
        if not (always or id(text) in touching) or size <= length * 1.02:
            return
        if "\n" not in was:
            lines = int(np.ceil(size / length)) if always else 2
            new = _wrapped(was, max(2, min(lines, 3)))
            if new != was:
                text.set_text(new)
                count += 1
            return
        # Already on two lines and still too long (one line much longer than
        # the other): share the same words out evenly, on two lines, then three.
        joined = " ".join(part.strip() for part in was.split("\n"))
        best, best_size = was, size
        for lines in (2, 3):
            text.set_text(_wrapped(joined, lines))
            renderer = _renderer(figure)
            box = _extent(text, renderer)
            now = box.width if along_x else box.height
            if now < best_size - 1.0:
                best, best_size = text.get_text(), now
            if now <= length * 1.02:
                break
        text.set_text(best)
        if best != was:
            count += 1
        renderer = _renderer(figure)

    for text in figure.texts:
        tag = getattr(text, "_panel", None)
        if tag is not None and tag["kind"] == "title":
            fit_to(text, tag["axis"].get_window_extent(renderer).width)
    for axes in figure.axes:
        box = axes.get_window_extent(renderer)
        if hasattr(axes, "_colorbar"):
            vertical = getattr(axes._colorbar, "orientation", "vertical") == "vertical"
            label = axes.yaxis.label if vertical else axes.xaxis.label
            # longer than its bar: always wrapped, so twin bars match
            fit_to(label, box.height if vertical else box.width, along_x=not vertical, always=True)
            continue
        fit_to(axes.title, box.width)
        fit_to(axes.xaxis.label, box.width)
        fit_to(axes.yaxis.label, box.height, along_x=False)
    return count


def pads(figure) -> int:
    """An axis label (a colour bar's too) keeps CLEARANCE of its font size
    from its tick labels. A label pad is set in points, so after the text
    grows the label ends up touching the numbers."""
    renderer = _renderer(figure)
    hidden = _index(figure)
    moved = 0
    for axes in figure.axes:
        if not axes.axison or not axes.get_visible():
            continue
        for axis, k in ((axes.xaxis, 1), (axes.yaxis, 0)):
            label = axis.label
            if not label.get_visible() or not label.get_text().strip() or not axis.get_visible():
                continue
            if not getattr(axis, "_autolabelpos", True):
                continue  # placed by hand
            numbers = [_extent(t, renderer) for t in axis.get_ticklabels(which="both")
                       if id(t) not in hidden and t.get_visible() and t.get_text().strip()]
            numbers = [b for b in numbers if b.width > 0 and b.height > 0]
            if not numbers:
                continue
            box = _extent(label, renderer)
            low = min(b.min[k] for b in numbers)
            high = max(b.max[k] for b in numbers)
            if (box.min[k] + box.max[k]) / 2 >= (low + high) / 2:
                gap = box.min[k] - high
            else:
                gap = low - box.max[k]
            need = CLEARANCE * label.get_fontsize() * figure.dpi / 72.0
            if gap < need - 0.5:
                axis.labelpad = axis.labelpad + (need - gap) * 72.0 / figure.dpi
                moved += 1
    if moved:
        _renderer(figure)
    return moved


COVER = 0.20  # a legend with more than this share of its box on drawn data moves
TOUCH = 0.01  # and so does one with more than this share of any entry's text on data,
EMPTY = 0.05  # to a spot in the panel with less than this, or under the panel


def _backdrop(axes):
    """What a legend may lie on: grid lines and bands that span the panel
    (axvspan), and, for a legend with a frame, reference lines that span it
    (axhline); a legend without a frame would have the line through its text."""
    from matplotlib.artist import Artist
    from matplotlib.legend import Legend
    spanning = (axes.get_xaxis_transform(which="grid"), axes.get_yaxis_transform(which="grid"))
    found = list(axes.xaxis.get_gridlines()) + list(axes.yaxis.get_gridlines())
    legends = [c for c in axes.get_children() if isinstance(c, Legend) and c.get_visible()]
    framed = all(l.get_frame().get_visible() and (l.get_frame().get_alpha() or 1.0) >= 0.5
                 for l in legends)
    for artist in list(axes.patches) + (list(axes.lines) if framed else []):
        if any(Artist.get_transform(artist) is t for t in spanning):
            found.append(artist)
    return found


def _drawn(figure):
    """The figure's pixels drawn without its legends and without the backdrop
    (row 0 at the bottom), or None when it has no legend in a panel."""
    from matplotlib.legend import Legend
    shown = [l for l in figure.findobj(Legend) if l.get_visible() and l.axes is not None]
    if not shown or not hasattr(figure.canvas, "buffer_rgba"):
        return None
    shown += [a for axes in figure.axes for a in _backdrop(axes) if a.get_visible()]
    for artist in shown:
        artist.set_visible(False)
    try:
        figure.canvas.draw()
        pixels = np.asarray(figure.canvas.buffer_rgba())[::-1, :, :3].astype(np.int16)
    finally:
        for artist in shown:
            artist.set_visible(True)
    return pixels


def _covered(pixels, box, backgrounds) -> float:
    """Share of `box` (display px) that is drawn on, i.e. not a background colour."""
    x0, x1 = int(np.floor(box.x0)), int(np.ceil(box.x1))
    y0, y1 = int(np.floor(box.y0)), int(np.ceil(box.y1))
    if x0 < 0 or y0 < 0 or x1 > pixels.shape[1] or y1 > pixels.shape[0] or x1 <= x0 or y1 <= y0:
        return 1.0  # off the figure: no place for a legend
    patch = pixels[y0:y1, x0:x1]
    ink = np.ones(patch.shape[:2], bool)
    for colour in backgrounds:
        ink &= np.abs(patch - colour).max(axis=2) > 4
    return float(ink.mean())


def uncover(figure, pixels) -> int:
    """Move a legend that lies on what its panel draws (a map, bars): to the
    emptiest corner of the panel when one is empty, else under the panel,
    below its tick and axis labels, with the entries side by side.
    `pixels` is _drawn(figure), made before anything was hidden."""
    from matplotlib.legend import Legend
    from matplotlib.transforms import Bbox
    if pixels is None:
        return 0
    renderer = _renderer(figure)
    moved = 0
    for legend in list(figure.findobj(Legend)):
        axes = legend.axes
        if axes is None or not legend.get_visible() or not legend.get_texts():
            continue
        backgrounds = [np.round(np.array(colour[:3]) * 255)
                       for colour in (figure.get_facecolor(), axes.get_facecolor())]
        box = legend.get_window_extent(renderer)
        entries = [_extent(t, renderer) for t in legend.get_texts() if t.get_text().strip()]

        def cover(dx=0.0, dy=0.0):
            """(share of the box on data, largest share of one entry's text on data)
            with the legend moved by dx, dy px."""
            whole = _covered(pixels, box.translated(dx, dy), backgrounds)
            return whole, max(_covered(pixels, e.translated(dx, dy), backgrounds) for e in entries)

        whole, text = cover()
        if whole <= COVER and text <= TOUCH:
            continue
        panel = axes.get_window_extent(renderer)
        size = legend.get_texts()[0].get_fontsize()
        pad = legend.borderaxespad * size * figure.dpi / 72.0
        spots = {}
        if box.width + 2 * pad <= panel.width and box.height + 2 * pad <= panel.height:
            rows = {"upper": panel.y1 - pad - box.height, "center": panel.y0 + (panel.height - box.height) / 2,
                    "lower": panel.y0 + pad}
            columns = {"left": panel.x0 + pad, "center": panel.x0 + (panel.width - box.width) / 2,
                       "right": panel.x1 - pad - box.width}
            for row, y in rows.items():
                for column, x in columns.items():
                    if row == column:
                        continue  # the middle of the panel
                    share = cover(x - box.x0, y - box.y0)
                    if share[0] <= EMPTY and share[1] <= TOUCH:
                        spots[f"{row} {column}"] = share[0]
        best = min(spots, key=spots.get) if spots else None
        if best is not None:
            legend.set_bbox_to_anchor(None)
            legend._loc = Legend.codes[best]
            legend.stale = True
            moved += 1
            renderer = _renderer(figure)
            continue
        # No empty corner: under the panel, clear of its own labels and colour bar.
        below = [panel.y0] + [q[:, 1].min() for q in _own_text(axes, renderer)]
        below += [a.get_window_extent(renderer).y0 for a in figure.axes
                  if a is not axes and _owner_axes(a) is axes]
        below += [l.get_window_extent(renderer).y0 for l in axes.findobj(Legend)
                  if l is not legend and getattr(l, "_under", False)]
        gap = CLEARANCE * size * figure.dpi / 72.0
        y = (min(below) - gap - panel.y0) / panel.height
        handles = list(getattr(legend, "legend_handles", None) or legend.legendHandles)
        labels = [t.get_text() for t in legend.get_texts()]
        title = legend.get_title()
        keep = {"fontsize": size, "frameon": legend.get_frame_on(), "handlelength": legend.handlelength,
                "handletextpad": legend.handletextpad, "labelspacing": legend.labelspacing,
                "columnspacing": legend.columnspacing, "borderpad": legend.borderpad,
                "markerscale": 1.0, "borderaxespad": 0.0, "loc": "upper center",
                "bbox_to_anchor": (0.5, y), "bbox_transform": axes.transAxes}
        if title.get_text().strip():
            keep.update(title=title.get_text(), title_fontsize=title.get_fontsize())
        main = axes.legend_ is legend
        legend.remove()
        count = len(labels)
        tries = sorted({count, int(np.ceil(count / 2)), int(np.ceil(count / 3)), 1}, reverse=True)
        for columns in tries:
            new = Legend(axes, handles, labels, ncol=columns, **keep)
            if main:
                axes.legend_ = new
                new._remove_method = axes._remove_legend
            else:
                axes.add_artist(new)
            renderer = _renderer(figure)
            if new.get_window_extent(renderer).width <= panel.width or columns == 1:
                break
            new.remove()
        new._under = True  # legends() keeps it clear of its own panel's labels only
        moved += 1
    return moved


def _own_text(axis, renderer):
    """Quads of an axes' tick labels and axis labels (and its colour bar's)."""
    quads = []
    for axes in [axis] + [a for a in axis.figure.axes if _owner_axes(a) is axis and a is not axis]:
        for ax in (axes.xaxis, axes.yaxis):
            for text in [ax.label] + ax.get_ticklabels(which="both"):
                if text.get_visible() and text.get_text().strip():
                    quads.append(_quad(text, renderer))
    return quads


def _owner_axes(axes):
    """A colour bar's axes belong to the panel the bar is for."""
    parents = getattr(axes, "_colorbar_info", {}).get("parents") if hasattr(axes, "_colorbar") else None
    if parents:
        return parents[0]  # the panel it was made for (figure.colorbar(ax=...))
    if hasattr(axes, "_colorbar"):
        mappable = getattr(axes._colorbar, "mappable", None)
        if getattr(mappable, "axes", None) is not None:
            return mappable.axes
    return axes


def place_letters(figure) -> int:
    """Move a panel letter that sits on its own panel's labels left, clear of
    them; letters in the same column move with it so the column stays straight."""
    renderer = _renderer(figure)
    letters = [t for t in figure.texts if getattr(t, "_panel", {}).get("kind") == "letter"]
    moved = 0
    to_pixels = figure.transFigure
    for letter in letters:
        axis = letter._panel["axis"]
        quad = _quad(letter, renderer)
        others = [q for t, q in _texts(figure, renderer)
                  if t is not letter and getattr(t, "_panel", {}).get("kind") != "letter"
                  and _owner(t) in (axis, None)]  # own panel or figure title; a neighbour's is for space()
        clear = CLEARANCE * letter.get_fontsize() * figure.dpi / 72.0
        own = [q for q in others if _touch(quad, q, -clear)]
        if not own:
            continue
        left = min(q[:, 0].min() for q in own)
        shift = quad[:, 0].max() - left + clear  # px to move left
        if shift > 0.4 * axis.get_window_extent(renderer).width:
            continue  # too far: leave it to more space between panels
        column = [t for t in letters
                  if abs(t.get_position()[0] - letter.get_position()[0]) < 0.01]
        for t in column:
            x, y = t.get_position()
            px = to_pixels.transform((x, y))
            t.set_position(to_pixels.inverted().transform((px[0] - shift, px[1])))
            t._panel["dx"] -= shift / figure.bbox.width
        moved += 1
        renderer = _renderer(figure)
    return moved


def _free_texts(axes):
    return [t for t in axes.texts if t.get_visible() and t.get_text().strip()]


def _shift_text(text, dy_px, renderer, dx_px=0.0):
    if isinstance(text, Annotation):
        transform = text._get_xy_transform(renderer, text.anncoords)
    else:
        transform = text.get_transform()
    x, y = text.get_position()
    px = transform.transform((x, y))
    text.set_position(transform.inverted().transform((px[0] + dx_px, px[1] + dy_px)))


def inside(figure) -> int:
    """A note written inside a panel that runs past the panel's side (under
    a colour bar, say) moves sideways until it fits."""
    renderer = _renderer(figure)
    moved = 0
    for axes in figure.axes:
        if hasattr(axes, "_colorbar"):
            continue
        box = axes.get_window_extent(renderer)
        for text in _free_texts(axes):
            if getattr(text, "_panel", None) is not None:
                continue
            quad = _quad(text, renderer)
            left, right = quad[:, 0].min(), quad[:, 0].max()
            centre = (left + right) / 2
            if not box.x0 <= centre <= box.x1 or right - left > box.width:
                continue  # placed outside on purpose, or wider than the panel
            if right > box.x1:
                _shift_text(text, 0.0, renderer, box.x1 - right - GAP)
                moved += 1
            elif left < box.x0:
                _shift_text(text, 0.0, renderer, box.x0 - left + GAP)
                moved += 1
    return moved


def ticks(figure) -> int:
    """Tilt an axis's tick labels 30 degrees when neighbours touch (two-line
    labels go onto one line first, as tilted stacks still collide), and pad
    the x and y labels out where they meet at a corner."""
    renderer = _renderer(figure)
    hidden = _index(figure)
    tilted = 0
    for axes in figure.axes:
        if hasattr(axes, "_colorbar") or not axes.axison:
            continue
        labels = [t for t in axes.xaxis.get_ticklabels()
                  if id(t) not in hidden and t.get_visible() and t.get_text().strip()]
        if len(labels) < 2 or any(abs(t.get_rotation()) > 0.5 for t in labels):
            continue
        ylabels = [t for t in axes.yaxis.get_ticklabels()
                   if id(t) not in hidden and t.get_visible() and t.get_text().strip()]
        for _ in range(6):
            if not any(_touch(_quad(a, renderer), _quad(b, renderer)) for a in labels for b in ylabels):
                break
            for axis in (axes.xaxis, axes.yaxis):  # labels meet at the corner: pad both out
                pad = axis.get_major_ticks()[0].get_pad() if axis.get_major_ticks() else 3.5
                axis.set_tick_params(which="both", pad=pad + 1.5)
            tilted += 1
            renderer = _renderer(figure)
        quads = sorted((_quad(t, renderer) for t in labels), key=lambda q: q[:, 0].min())
        if any(_touch(a, b) for a, b in zip(quads, quads[1:])):
            texts = [t.get_text() for t in axes.xaxis.get_ticklabels()]
            if any("\n" in t for t in texts):
                # tilted, two-line labels still collide: one line each
                axes.xaxis.set_ticks(axes.get_xticks(), [t.replace("\n", " ") for t in texts])
            for t in axes.xaxis.get_ticklabels():
                t.set_rotation(30)
                t.set_ha("right")
                t.set_rotation_mode("anchor")
            tilted += 1
    return tilted


def repel(figure) -> int:
    """Push apart notes inside one panel that touch: the upper one moves up."""
    moved = 0
    for _ in range(20):
        renderer = _renderer(figure)
        again = False
        for axes in figure.axes:
            notes = [(t, _quad(t, renderer)) for t in _free_texts(axes)]
            for i, (a, qa) in enumerate(notes):
                for b, qb in notes[i + 1:]:
                    if not _touch(qa, qb):
                        continue
                    lower, upper = (a, b) if qa[:, 1].mean() <= qb[:, 1].mean() else (b, a)
                    ql, qu = (qa, qb) if lower is a else (qb, qa)
                    _shift_text(upper, ql[:, 1].max() - qu[:, 1].min() + GAP, renderer)
                    moved += 1
                    again = True
                    break
                if again:
                    break
            if again:
                break
        if not again:
            break
    return moved


def legends(figure) -> int:
    """Move a legend that touches other text away from it, vertically: down
    when it sits below its panel's middle, up when above."""
    from matplotlib.legend import Legend
    moved = 0
    for legend in figure.findobj(Legend):
        for _ in range(30):
            renderer = _renderer(figure)
            own = {id(t) for t in legend.findobj(Text)}
            mine = [_quad(t, renderer) for t in legend.get_texts() if t.get_text().strip()]
            if legend.get_title().get_text().strip():
                mine.append(_quad(legend.get_title(), renderer))
            under = getattr(legend, "_under", False)
            hit = [q for t, q in _texts(figure, renderer) if id(t) not in own
                   and any(_touch(m, q) for m in mine)
                   and not (under and _owner(t) is not legend.axes)]  # a neighbour's: for space()
            if not hit:
                break
            box = legend.get_window_extent(renderer)
            panel = legend.axes if legend.axes is not None else None
            anchor = legend.get_bbox_to_anchor()
            if panel is not None:
                middle = panel.get_window_extent(renderer).y0 + panel.get_window_extent(renderer).height / 2
            else:
                middle = figure.bbox.height / 2
            if (box.y0 + box.y1) / 2 < middle:
                dy = -(box.y1 - min(q[:, 1].min() for q in hit) + GAP)
            else:
                dy = max(q[:, 1].max() for q in hit) - box.y0 + GAP
            shifted = anchor.translated(0, dy)
            # anchored to its panel, so it follows when the panels move apart
            frame = panel.transAxes if panel is not None else figure.transFigure
            legend.set_bbox_to_anchor(shifted.transformed(frame.inverted()), transform=frame)
            moved += 1
    return moved


def _gridspecs(figure):
    specs = {}
    for axes in figure.axes:
        spec = axes.get_subplotspec() if hasattr(axes, "get_subplotspec") else None
        if spec is None:
            continue
        grid = spec.get_topmost_subplotspec().get_gridspec()
        specs[id(grid)] = grid
    return list(specs.values())


def _replace_labels(figure):
    """Put tagged letters and titles back on their panels after the panels moved."""
    for text in figure.texts:
        tag = getattr(text, "_panel", None)
        if tag is None:
            continue
        box = tag["axis"].get_position()
        if tag["kind"] == "letter":
            left = tag.get("left")
            x0 = min(a.get_position().x0 for a in left) if left else box.x0
            text.set_position((x0 + tag["dx"], box.y1 + tag["dy"]))
        else:
            text.set_position(((box.x0 + box.x1) / 2, box.y1 + tag["dy"]))


def space(figure, problems) -> bool:
    """One step more space between panels whose text touches across them."""
    renderer = _renderer(figure)
    wider = taller = False
    for a, b, why in problems:
        if b is None:
            continue
        oa = _owner(a)
        ob = _owner(b) if isinstance(b, Text) else _owner_axes(b)
        if oa is None or ob is None or oa is ob:
            continue
        pa, pb = oa.get_position(), ob.get_position()
        dx = abs((pa.x0 + pa.x1) - (pb.x0 + pb.x1)) / 2
        dy = abs((pa.y0 + pa.y1) - (pb.y0 + pb.y1)) / 2
        if dx >= dy:
            wider = True
        else:
            taller = True
    if not (wider or taller):
        return False
    changed = False
    for grid in _gridspecs(figure):
        params = grid.get_subplot_params(figure)
        # Panels the script placed by hand (lined up with the map above, say)
        # keep the same place within their grid cell when the cells move.
        placed = {}
        for ax in figure.axes:
            spec = ax.get_subplotspec() if hasattr(ax, "get_subplotspec") else None
            if spec is None or spec.get_topmost_subplotspec().get_gridspec() is not grid:
                continue
            if hasattr(ax, "_colorbar"):
                continue
            own, cell = ax.get_position(original=True), spec.get_position(figure)
            if not np.allclose(own.bounds, cell.bounds, atol=1e-3):
                placed[ax] = ((own.x0 - cell.x0) / cell.width, (own.y0 - cell.y0) / cell.height,
                              own.width / cell.width, own.height / cell.height)
        update = {}
        if wider and grid.ncols > 1:
            update["wspace"] = params.wspace + STEP
        if taller and grid.nrows > 1:
            update["hspace"] = params.hspace + STEP
        if not update:
            continue
        if "hspace" in update:
            # Rows apart: make the figure taller. Its width sets the print
            # scale, so text keeps its printed size; and panels that keep
            # their aspect (maps) get real room, which hspace alone does not
            # give them when their width limits their size.
            figure.set_figheight(figure.get_figheight() * (1 + STEP))
        grid.update(**update)
        for ax, (fx, fy, fw, fh) in placed.items():
            cell = ax.get_subplotspec().get_position(figure)
            ax.set_position([cell.x0 + fx * cell.width, cell.y0 + fy * cell.height,
                             fw * cell.width, fh * cell.height])
        changed = True
    if changed:
        _renderer(figure)
        _replace_labels(figure)
    return changed


def _hide_drawing(figure):
    """Hide what text does not depend on (filled shapes, lines, images) so each
    redraw while fitting is fast; returns the artists to show again."""
    from matplotlib.collections import Collection
    from matplotlib.image import AxesImage
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    hidden = []
    for axes in figure.axes:
        for child in axes.get_children():
            if child is axes.patch or not child.get_visible():
                continue
            if isinstance(child, (Collection, AxesImage, Line2D)) or (
                    isinstance(child, Patch) and child not in axes.spines.values()):
                child.set_visible(False)
                hidden.append(child)
    return hidden


def density(figure) -> dict:
    """How much of each panel its labels take: the area of the text that
    labels a panel (ticks, axis and colour-bar labels, legend, map coordinates;
    not titles or panel letters) over the panel's plot area. Text area grows
    with the square of font size, so a font that gives density d now gives
    d * (new / now) ** 2. Returns {"median", "panels": [...]}."""
    renderer = _renderer(figure)
    hidden = _index(figure)
    owner = figure._textfit_owner
    for axes in figure.axes:  # cartopy coordinate labels, made at draw time
        for gl in getattr(axes, "_gridliners", []):
            for text in getattr(gl, "label_artists", []):
                owner[id(text)] = axes
    texts = list(figure.findobj(Text))
    for axes in figure.axes:
        for gl in getattr(axes, "_gridliners", []):
            texts += list(getattr(gl, "label_artists", []))
    area = {}
    for text in texts:
        if id(text) in hidden or not text.get_visible() or not text.get_text().strip():
            continue
        tag = getattr(text, "_panel", None)
        panel = owner.get(id(text))
        if panel is None or tag is not None or text is panel.title or panel.figure is None:
            continue
        rotation = text.get_rotation()
        text.set_rotation(0)
        box = _extent(text, renderer)
        text.set_rotation(rotation)
        area[panel] = area.get(panel, 0.0) + box.width * box.height
    sizes = {}
    for text in texts:
        panel = owner.get(id(text))
        if panel is not None and getattr(text, "_panel", None) is None and text.get_visible() \
                and text.get_text().strip() and id(text) not in hidden:
            sizes.setdefault(panel, []).append(text.get_fontsize())
    panels, widths = [], []
    for axes in figure.axes:
        if hasattr(axes, "_colorbar") or not axes.get_visible():
            continue
        box = axes.get_window_extent(renderer)
        if box.width * box.height > 0:
            panels.append(area.get(axes, 0.0) / (box.width * box.height))
            # the panel's width in heights of its own largest label text
            font = max(sizes.get(axes, [0.0]) + [t.get_fontsize() for t in figure.texts
                                                 if getattr(t, "_panel", {}).get("axis") is axes])
            if font > 0:
                widths.append(min(box.width, box.height * 2) * 72.0 / figure.dpi / font)
    return {"median": float(np.median(panels)) if panels else 0.0, "panels": panels,
            "ems": float(np.median(widths)) if widths else 0.0, "ems_min": float(min(widths)) if widths else 0.0,
            "panel_ems": widths}


def fit(figure, name: str = "", edges: bool = False, quiet: bool = False) -> int:
    """Fix colliding text in `figure` as described above; returns what is left."""
    if not quiet:
        d = density(figure)
        print(f"TEXT DENSITY {name}: median {d['median']:.4f} ems {d['ems']:.1f} min {d['ems_min']:.1f} panels "
              + " ".join(f"{p:.4f}" for p in d["panels"]) + " | ems "
              + " ".join(f"{w:.1f}" for w in d["panel_ems"]), flush=True)
    pixels = _drawn(figure)  # one full draw, while everything is still shown
    hidden = _hide_drawing(figure)
    try:
        return _fit(figure, name, edges, quiet, pixels)
    finally:
        for artist in hidden:
            artist.set_visible(True)


def _fit(figure, name, edges, quiet, pixels=None):
    steps = {"cover": 0, "wrap": 0, "pads": 0, "letters": 0, "ticks": 0, "inside": 0,
             "repel": 0, "legends": 0, "space": 0}
    steps["cover"] = uncover(figure, pixels)
    fixers = (("wrap", wrap), ("pads", pads), ("letters", place_letters), ("ticks", ticks),
              ("inside", inside), ("repel", repel), ("legends", legends))
    retries = 3  # rounds allowed when a fix changed something but more space did not help
    for _ in range(MAX_STEPS):
        fixed = 0
        for key, fixer in fixers:
            count = fixer(figure)
            steps[key] += count
            fixed += count
        problems = overlaps(figure, edges)
        if os.environ.get("TEXTFIT_DEBUG"):
            for a, b, why in problems:
                print("  step", steps["space"], why, repr(a.get_text()[:30]),
                      repr(b.get_text()[:30]) if isinstance(b, Text) else b, flush=True)
        if not problems:
            break
        if space(figure, problems):
            steps["space"] += 1
            continue
        # One fix can set up the next (a label pushed out by pads now needs
        # wrapping): go round again while the fixes still change something.
        retries -= 1
        if not fixed or retries < 0:
            break
    else:
        # the last spacing step moved panels: settle letters and notes once more
        steps["letters"] += place_letters(figure)
        steps["repel"] += repel(figure)
    if not quiet:
        done = ", ".join(f"{k} {v}" for k, v in steps.items() if v)
        if done:
            print(f"TEXT FIXED {name}: {done}", flush=True)
    return report(figure, name, edges) if not quiet else len(overlaps(figure, edges))


def pad_cartopy_labels(points: float = 2.0) -> None:
    """Cartopy hides a coordinate label that overlaps another one, but lets
    labels touch ("60°W0°"). Make it keep `points` of space between them.
    Cartopy redraws its labels on every draw, so this has to be its rule."""
    try:
        from cartopy.mpl import gridliner
    except ImportError:
        return
    label_class = gridliner.Label
    if getattr(label_class, "_textfit_padded", None) == points:
        return
    original = getattr(label_class, "_textfit_original", label_class.check_overlapping)

    def check_overlapping(self, label):
        overlapping = self.path.intersects_path(label.path)
        if not overlapping:
            pad = points * self.artist.figure.dpi / 72.0 / 2.0
            overlapping = self.path.get_extents().padded(pad).overlaps(label.path.get_extents().padded(pad))
        if overlapping:
            self.set_visible(False)
        return overlapping

    label_class._textfit_original = original
    label_class.check_overlapping = check_overlapping
    label_class._textfit_padded = points


TARGET_WIDTH = 15.0  # panels read well at 15 or more text heights wide (eHDD figures, 2026-11-20)


def suggest_size(figure, printed_pt: float = 8.0, target: float = TARGET_WIDTH,
                 low: float = 6.0, high: float = 8.0, step: float = 1.0) -> float:
    """The printed font size this figure should use, from its narrowest panel.

    `printed_pt` is what its main text prints at now. A panel `w` text heights
    wide at that size is `w * now / new` wide at `new`; pick the size that
    brings the narrowest panel to `target`, kept within [low, high] and
    rounded down to `step`. Words should never be as big as the panels."""
    narrowest = density(figure)["ems_min"]
    if narrowest <= 0:
        return high
    size = printed_pt * narrowest / target
    size = np.floor(size / step + 1e-9) * step
    return float(min(high, max(low, size)))
