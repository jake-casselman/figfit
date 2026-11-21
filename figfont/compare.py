"""Compare measured sizes with published papers."""
from __future__ import annotations

import json
from importlib import resources

from .measure import Result


def reference(journal: str | None = None) -> dict:
    ref = json.loads(resources.files("figfont").joinpath("reference.json").read_text())
    return ref["journals"].get(journal, ref["all"]) if journal else ref["all"]


def verdict(result: Result, journal: str | None = None, smallest_ok: float = 6.0) -> dict:
    """ok / small / large for one figure, against the middle half of published papers.

    A figure is "small" if its median prints below the 25th percentile of paper medians,
    or a tenth of its text below `smallest_ok` pt; "large" above the 75th percentile.
    """
    ref = reference(journal)
    low, high = ref["paper_medians_p25_p75"]
    out = result.summary() | {"reference_median_pt": ref["median_pt"], "reference_range_pt": [low, high]}
    if not result.sizes:
        return out | {"verdict": "no text found"}
    if result.median < low or (result.percentile(10) or 0) < smallest_ok:
        v = "small"
    elif result.median > high:
        v = "large"
    else:
        v = "ok"
    return out | {"verdict": v, "scale_to_reference": round(ref["median_pt"] / result.median, 2)}
