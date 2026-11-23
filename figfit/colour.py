"""Colour-blind check: can a reader with colour-vision deficiency tell a figure's colours apart?

About 1 man in 12 and 1 woman in 200 sees colour differently. Most of them confuse red and green
(protan and deutan types); a few confuse blue and yellow (tritan). The check simulates each type
with the matrices of Machado, Oliveira and Fernandes (2009, IEEE TVCG 15, 1291-1298) at full
severity, and measures how far apart two colours look in OKLab (difference x 100, so about 1 is
just noticeable and 8 or more reads as clearly different side by side in a legend).

Three ways in:
  colour_problems(fig)       a matplotlib figure: the colours that name things (lines, points, bars,
                             legend entries) and the colour maps
  image_problems(path)       any PNG or PDF, for figures you only have as a file
  sheet(path, out)           the figure as each kind of reader sees it, side by side
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

# Machado et al. (2009), severity 1.0, applied to linear RGB.
KINDS = {
    "protan": np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779],
                        [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}
NAMES = {"normal": "normal vision", "protan": "red-blind (protan)", "deutan": "green-blind (deutan)",
         "tritan": "blue-blind (tritan)"}

MIN_DE = 8.0       # two colours that name different things should differ by at least this
SAME_DE = 2.5      # closer than this the figure uses one colour twice, on purpose


def _linear(srgb):
    c = np.clip(np.asarray(srgb, dtype=float), 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb(linear):
    c = np.clip(linear, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def simulate(colours, kind: str):
    """`colours` (sRGB 0-1, last axis RGB) as a reader of `kind` sees them; "normal" returns them."""
    colours = np.asarray(colours, dtype=float)[..., :3]
    if kind == "normal":
        return colours
    return _srgb(_linear(colours) @ KINDS[kind].T)


def oklab(colours):
    """sRGB 0-1 -> OKLab (L 0-1)."""
    lin = _linear(np.asarray(colours, dtype=float)[..., :3])
    lms = lin @ np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                          [0.2119034982, 0.6806995451, 0.1073969566],
                          [0.0883024619, 0.2817188376, 0.6299787005]]).T
    lms = np.cbrt(lms)
    return lms @ np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                           [1.9779984951, -2.4285922050, 0.4505937099],
                           [0.0259040371, 0.7827717662, -0.8086757660]]).T


def difference(a, b, kind: str = "normal") -> float:
    """How different colours `a` and `b` look to a reader of `kind` (OKLab distance x 100)."""
    return float(100 * np.linalg.norm(oklab(simulate(a, kind)) - oklab(simulate(b, kind))))


def worst(a, b) -> tuple[str, float]:
    """The kind of reader for whom `a` and `b` look most alike, and how different they look."""
    return min(((k, difference(a, b, k)) for k in KINDS), key=lambda kv: kv[1])


def hex_of(colour) -> str:
    return "#" + "".join(f"{round(float(v) * 255):02x}" for v in np.asarray(colour)[:3])


@dataclass
class Problem:
    """Two colours that some readers can't tell apart, or a colour map that misleads them."""
    what: str                      # e.g. "panel (a): 'ERA5' and 'CMIP6 mean'"
    why: str                       # plain sentence
    kind: str = ""                 # reader type it fails for
    difference: float | None = None
    colours: list[str] = field(default_factory=list)
    serious: bool = True           # False: also told apart another way (line style, marker), so only a note

    def __str__(self):
        flag = "COLOUR" if self.serious else "colour note"
        return f"{flag}: {self.what}: {self.why}"


# --- matplotlib figures -------------------------------------------------------------------------

def _rgba(c):
    from matplotlib.colors import to_rgba
    return np.array(to_rgba(c))


def _single(colours):
    """The one colour of an artist, or None when it has several (a colour-mapped artist) or none."""
    arr = np.atleast_2d(np.asarray(colours, dtype=float)) if len(colours) else np.empty((0, 4))
    if len(arr) == 0 or arr[:, 3].max() == 0:
        return None
    first = arr[0]
    return first if np.allclose(arr, first, atol=1e-3) else None


def _keys(ax):
    """[(name, rgba, style)] for the things in panel `ax` that a reader tells apart by colour."""
    from matplotlib.collections import PathCollection, PolyCollection
    from matplotlib.container import BarContainer
    found = []

    def label(artist, fallback):
        text = artist.get_label() if artist is not None else ""
        return repr(text) if text and not text.startswith("_") else fallback

    for line in ax.get_lines():
        drawn = np.asarray(line.get_xdata(), dtype=object).size >= 2 and line.get_linestyle() not in ("None", " ", "")
        marked = line.get_marker() not in ("None", None, "", " ")
        if not line.get_visible() or not (drawn or marked):
            continue
        rgba = _rgba(line.get_color())
        style = (line.get_linestyle(), str(line.get_marker()))
        found.append((label(line, f"line {hex_of(rgba)}"), rgba, style))
    for container in ax.containers:
        if isinstance(container, BarContainer) and container.patches:
            rgba = _rgba(container.patches[0].get_facecolor())
            hatch = container.patches[0].get_hatch() or ""
            found.append((label(container, f"bars {hex_of(rgba)}"), rgba, ("bar", hatch)))
    for coll in ax.collections:
        if not coll.get_visible() or coll.get_array() is not None:
            continue  # colour-mapped: checked with the colour maps
        if isinstance(coll, (PathCollection, PolyCollection)):
            face = _single(coll.get_facecolor())
            if face is not None and face[3] > 0.15:
                kind = "points" if isinstance(coll, PathCollection) else "area"
                found.append((label(coll, f"{kind} {hex_of(face)}"), face, (kind, "")))
    return found


def _legend_keys(legend):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    found = []
    handles = getattr(legend, "legend_handles", None) or getattr(legend, "legendHandles", [])
    for handle, text in zip(handles, legend.get_texts()):
        if isinstance(handle, Line2D):
            rgba = _rgba(handle.get_color())
            style = (handle.get_linestyle(), str(handle.get_marker()))
        elif isinstance(handle, Patch):
            rgba = _rgba(handle.get_facecolor())
            style = ("patch", handle.get_hatch() or "")
        else:
            try:
                rgba = _single(handle.get_facecolor())
            except AttributeError:
                rgba = None
            style = ("points", "")
        if rgba is not None and rgba[3] > 0:
            found.append((repr(text.get_text()), rgba, style))
    return found


def _pairs(keys, where, min_de):
    problems = []
    for (name_a, a, style_a), (name_b, b, style_b) in combinations(keys, 2):
        normal = difference(a, b)
        if normal < SAME_DE:
            continue  # the same colour on purpose (a series drawn twice, a shared style)
        kind, seen = worst(a, b)
        if normal < min_de:
            kind, seen = "normal", normal
        if seen >= min_de:
            continue
        other_way = style_a != style_b
        who = "anyone" if kind == "normal" else NAMES[kind] + " readers"
        why = (f"{hex_of(a)} and {hex_of(b)} look alike to {who} (difference {seen:.1f}, want {min_de:g}+)"
               + ("; they also differ by line style, marker or hatch, so this is only a note" if other_way else ""))
        problems.append(Problem(f"{where}: {name_a} and {name_b}", why, kind, round(seen, 1),
                                [hex_of(a), hex_of(b)], serious=not other_way))
    return problems


RAINBOWS = {"jet", "rainbow", "gist_rainbow", "hsv", "nipy_spectral", "gist_ncar", "turbo", "Spectral",
            "gist_stern", "prism", "flag"}


def colormap_problems(cmap, min_de: float = MIN_DE, where: str = "") -> list[Problem]:
    """What is wrong with colour map `cmap` (a name or a Colormap) for colour-blind readers."""
    import matplotlib
    cmap = matplotlib.colormaps[cmap] if isinstance(cmap, str) else cmap
    name = cmap.name.removesuffix("_r")
    where = where or f"colour map {name!r}"
    x = np.linspace(0, 1, 129)
    colours = cmap(x)[:, :3]
    problems = []
    lightness = oklab(colours)[:, 0]
    middle = int(np.argmax(lightness[16:-16])) + 16
    diverging = (lightness[middle] - max(lightness[0], lightness[-1]) > 0.15
                 and 40 <= middle <= 88)
    if name in RAINBOWS:
        problems.append(Problem(where, "a rainbow map: its lightness goes up and down, so equal steps in the data "
                                "don't look equal and colour-blind readers see false edges; use a one-hue or "
                                "two-hue map (viridis, cividis, a ColorBrewer sequential or diverging map)",
                                "", None, [hex_of(c) for c in colours[::32]]))
        return problems
    if diverging:
        for kind in KINDS:
            seen = oklab(simulate(colours, kind))
            # the same distance either side of the middle must stay two different colours
            gaps = [100 * np.linalg.norm(seen[middle - d] - seen[middle + d])
                    for d in range(12, min(middle, 128 - middle) + 1, 4)]
            if gaps and max(gaps) < min_de * 1.25:  # RdYlGn fails (5 for deutan); RdBu, PuOr, BrBG pass
                problems.append(Problem(where, f"its two sides look alike to {NAMES[kind]} readers (most "
                                        f"different pair {max(gaps):.0f}); use a blue-red or purple-green "
                                        "diverging map (RdBu, PuOr, BrBG)", kind, round(max(gaps), 1),
                                        [hex_of(colours[0]), hex_of(colours[-1])]))
                break
    else:
        steps = np.diff(lightness)
        size = abs(lightness[-1] - lightness[0])
        turns = np.sum(steps * np.sign(lightness[-1] - lightness[0]) < -0.004)
        if size < 0.25:
            problems.append(Problem(where, f"its lightness changes by only {100 * size:.0f} from end to end, so "
                                    "colour-blind readers and grey print lose the scale", "", round(100 * size, 1)))
        elif turns > 6:
            problems.append(Problem(where, "its lightness goes back and forth, so equal steps in the data don't "
                                    "look equal; use a map whose lightness changes one way", "", None))
    return problems


def colour_problems(fig, min_de: float = MIN_DE) -> list[Problem]:
    """Colour problems in matplotlib figure `fig` for colour-blind readers.

    Checks, panel by panel, every pair of colours that name things (lines, points, bars, filled areas
    and legend entries), and every colour map used for data. A pair that also differs by line style,
    marker or hatch is reported as a note only (serious=False).
    """
    from matplotlib.cm import ScalarMappable
    problems, maps = [], {}
    axes = [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]
    for number, ax in enumerate(axes):
        where = f"panel {chr(97 + number)}" if len(axes) > 1 else "the figure"
        keys = _keys(ax)
        if ax.get_legend() is not None:
            seen = {hex_of(k[1]) for k in keys}
            keys += [k for k in _legend_keys(ax.get_legend()) if hex_of(k[1]) not in seen]
        problems += _pairs(keys, where, min_de)
        for artist in [*ax.images, *ax.collections]:
            if isinstance(artist, ScalarMappable) and artist.get_array() is not None:
                maps.setdefault(artist.get_cmap().name, (artist.get_cmap(), where))
    for legend in fig.legends:
        problems += _pairs(_legend_keys(legend), "the figure legend", min_de)
    for name, (cmap, where) in maps.items():
        problems += colormap_problems(cmap, min_de, f"{where}: colour map {name!r}")
    unique, seen = [], set()
    for problem in problems:  # one line per pair of colours in a panel, however many artists share them
        key = (problem.what.split(":")[0], tuple(sorted(problem.colours)), problem.why.split(";")[0][-60:])
        if key not in seen:
            seen.add(key)
            unique.append(problem)
    return unique


# --- image files --------------------------------------------------------------------------------

def load_image(path: str | os.PathLike, dpi: int = 150) -> np.ndarray:
    """RGB 0-1 array of a PNG/JPEG, or of the first page of a PDF rendered at `dpi`."""
    path = os.fspath(path)
    if path.lower().endswith(".pdf"):
        import pymupdf
        pix = pymupdf.open(path)[0].get_pixmap(dpi=dpi, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3) / 255
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB"), dtype=float) / 255


def main_colours(image: np.ndarray, share: float = 0.0015):
    """[(rgb, share of the image)] for the flat, non-grey colours in `image`: each exact colour that
    covers at least `share` of it. Lines, markers, bars, legend keys and filled areas are flat; a
    smooth colour map spreads over many colours and drops out, so it is checked by its own rules
    (colormap_problems) instead.
    """
    pixels = (np.asarray(image)[..., :3].reshape(-1, 3) * 255).round().astype(np.int32)
    codes = (pixels[:, 0] << 16) | (pixels[:, 1] << 8) | pixels[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    keep = counts >= share * len(codes)
    rgb = np.stack([(values[keep] >> 16) & 255, (values[keep] >> 8) & 255, values[keep] & 255], axis=1) / 255
    parts = counts[keep] / len(codes)
    lab = oklab(rgb)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    kept = []
    for i in np.argsort(-parts):
        if chroma[i] > 0.04 and all(difference(rgb[i], other) >= SAME_DE for other, _ in kept):
            kept.append((rgb[i], float(parts[i])))
    return kept


def image_problems(path: str | os.PathLike, min_de: float = 6.0, distinct: float = 20.0) -> list[Problem]:
    """Flat colours in a figure file (lines, markers, bars, legend keys, filled areas) that are clearly
    different to most readers (`distinct` or more) but look alike to colour-blind ones (under
    `min_de`), worst first. It sees only colours, not what they mean, so treat each pair as a place
    to look: two colours in different panels may never need telling apart. Smooth colour maps are
    not seen here; check them with colormap_problems or look at the sheet."""
    colours = main_colours(load_image(path))
    problems = []
    for (a, share_a), (b, share_b) in combinations(colours, 2):
        if difference(a, b) < distinct:
            continue
        kind, seen = worst(a, b)
        if seen < min_de:
            problems.append(Problem(
                os.path.basename(os.fspath(path)),
                f"{hex_of(a)} ({100 * share_a:.1f} % of the figure) and {hex_of(b)} ({100 * share_b:.1f} %) look "
                f"alike to {NAMES[kind]} readers (difference {seen:.1f})", kind, round(seen, 1), [hex_of(a), hex_of(b)]))
    return sorted(problems, key=lambda p: p.difference)


def sheet(path: str | os.PathLike, out: str | os.PathLike | None = None) -> str:
    """Save the figure as seen with normal vision and by each colour-blind type, in a 2 x 2 sheet."""
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    image = load_image(path)
    out = os.fspath(out or os.path.splitext(os.fspath(path))[0] + ".colourblind.png")
    height, width = image.shape[:2]
    fig, axes = plt.subplots(2, 2, figsize=(10, 10 * height / width + 0.6), layout="constrained")
    for ax, kind in zip(axes.ravel(), ["normal", *KINDS]):
        ax.imshow(simulate(image, kind))
        ax.set_title(NAMES[kind], fontsize=11)
        ax.axis("off")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
