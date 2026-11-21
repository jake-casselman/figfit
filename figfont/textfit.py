"""Keep figure text from colliding after a font change.

A figure laid out at one font size and then printed bigger (plotstyle.scale_text)
keeps its old spacing, so labels can land on each other. fit() finds every
pair of touching text and fixes it with the smallest change that works, in
this order:

  1. wrap   a panel title, axis label or colour-bar label longer than its
            panel or bar, that touches other text, goes onto two lines
            (the words stay the same);
  2. letters a panel letter on its own axis labels moves left, past them,
            and so do the other letters in its column, so they stay aligned;
  3. ticks  tick labels that touch their neighbours tilt 30 degrees;
     inside a note inside a panel that runs past its side moves back in;
     repel  two notes inside one panel push apart vertically;
     legend a legend that touches a label moves away from it;
  4. space  text that still touches a neighbouring panel's text gets more
            space between the panels (gridspec wspace / hspace), in steps.

Nothing else changes: no sizes, colours, data or wording. report() prints
what is left, so a figure never ships with text on top of text unseen.
"""
from __future__ import annotations

import re

import numpy as np
from matplotlib.text import Annotation, Text

GAP = 3.0       # px kept between text after a fix
STEP = 0.04     # gridspec wspace / hspace added per spacing step
MAX_STEPS = 12


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

def overlaps(figure, edges: bool = False):
    """[(text_a, text_b or None, why)] for touching text, and (edges=True) text
    off the figure. Off-figure is meaningless when saving with bbox="tight"."""
    renderer = _renderer(figure)
    found = _texts(figure, renderer)
    edge = figure.bbox
    problems = []
    for i, (a, qa) in enumerate(found):
        if edges and (qa[:, 0].min() < edge.x0 - 2 or qa[:, 0].max() > edge.x1 + 2
                      or qa[:, 1].min() < edge.y0 - 2 or qa[:, 1].max() > edge.y1 + 2):
            problems.append((a, None, "off the figure"))
        for b, qb in found[i + 1:]:
            if _touch(qa, qb):
                problems.append((a, b, "overlap"))
    return problems


def report(figure, name: str = "", edges: bool = False) -> int:
    """Print each text collision in `figure`; returns how many."""
    problems = overlaps(figure, edges)
    for a, b, why in problems:
        other = f" <-> {b.get_text()[:40]!r}" if b is not None else ""
        print(f"TEXT {why.upper()} {name}: {a.get_text()[:40]!r}{other}", flush=True)
    if not problems:
        print(f"TEXT OK {name}: no overlaps", flush=True)
    return len(problems)


# ----------------------------------------------------------------------------- fixing

def _wrapped(s: str) -> str:
    """s on two lines, split at the space nearest its middle (never inside $...$)."""
    if "\n" in s:
        return s
    gap = re.search(r"(?<=\S) {2,}(?=\S)", s)
    if gap and s[:gap.start()].count("$") % 2 == 0:
        return f"{s[:gap.start()]}\n{s[gap.end():]}"
    spaces, inside = [], False
    for i, ch in enumerate(s):
        if ch == "$":
            inside = not inside
        elif ch == " " and not inside and 0 < i < len(s) - 1:
            spaces.append(i)
    if not spaces:
        return s
    visible = len(re.sub(r"\$[^$]*\$", "xx", s))
    middle = visible / 2 * len(s) / max(visible, 1)
    cut = min(spaces, key=lambda i: abs(i - middle))
    head, tail = s[:cut].rstrip(), s[cut:].lstrip()
    return f"{head}\n{tail}"


def wrap(figure) -> int:
    """Two lines for any panel title, axis label or colour-bar label longer
    than its panel or bar that also touches other text. Returns how many."""
    touching = {id(t) for a, b, _ in overlaps(figure) for t in (a, b) if t is not None}
    renderer = _renderer(figure)
    count = 0

    def fit_to(text, length, along_x=True):
        nonlocal count
        box = _extent(text, renderer)
        size = box.width if along_x else box.height
        if id(text) in touching and text.get_text().strip() and size > length * 1.02:
            new = _wrapped(text.get_text())
            if new != text.get_text():
                text.set_text(new)
                count += 1

    for text in figure.texts:
        tag = getattr(text, "_panel", None)
        if tag is not None and tag["kind"] == "title":
            fit_to(text, tag["axis"].get_window_extent(renderer).width)
    for axes in figure.axes:
        box = axes.get_window_extent(renderer)
        if hasattr(axes, "_colorbar"):
            vertical = getattr(axes._colorbar, "orientation", "vertical") == "vertical"
            label = axes.yaxis.label if vertical else axes.xaxis.label
            fit_to(label, box.height if vertical else box.width, along_x=not vertical)
            continue
        fit_to(axes.title, box.width)
        fit_to(axes.xaxis.label, box.width)
        fit_to(axes.yaxis.label, box.height, along_x=False)
    return count


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
                  if t is not letter and getattr(t, "_panel", {}).get("kind") != "letter"]
        own = [q for q in others if _touch(quad, q)]
        if not own:
            continue
        left = min(q[:, 0].min() for q in own)
        shift = quad[:, 0].max() - left + GAP  # px to move left
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
    labels go onto one line first, as tilted stacks still collide)."""
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
            hit = [q for t, q in _texts(figure, renderer) if id(t) not in own
                   and any(_touch(m, q) for m in mine)]
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
            legend.set_bbox_to_anchor(shifted.transformed(figure.transFigure.inverted()),
                                      transform=figure.transFigure)
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
        oa, ob = _owner(a), _owner(b)
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


def fit(figure, name: str = "", edges: bool = False, quiet: bool = False) -> int:
    """Fix colliding text in `figure` as described above; returns what is left."""
    hidden = _hide_drawing(figure)
    try:
        return _fit(figure, name, edges, quiet)
    finally:
        for artist in hidden:
            artist.set_visible(True)


def _fit(figure, name, edges, quiet):
    steps = {"wrap": wrap(figure), "letters": 0, "ticks": 0, "inside": 0, "repel": 0,
             "legends": 0, "space": 0}
    for _ in range(MAX_STEPS):
        steps["letters"] += place_letters(figure)
        steps["ticks"] += ticks(figure)
        steps["inside"] += inside(figure)
        steps["repel"] += repel(figure)
        steps["legends"] += legends(figure)
        problems = overlaps(figure, edges)
        if not problems or not space(figure, problems):
            break
        steps["space"] += 1
    if not quiet:
        done = ", ".join(f"{k} {v}" for k, v in steps.items() if v)
        if done:
            print(f"TEXT FIXED {name}: {done}", flush=True)
    return report(figure, name, edges) if not quiet else len(overlaps(figure, edges))
