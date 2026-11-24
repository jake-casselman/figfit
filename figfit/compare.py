"""Compare measured sizes with published papers."""
from __future__ import annotations

import json
from importlib import resources

from .measure import Result


def _load() -> dict:
    return json.loads(resources.files("figfit").joinpath("reference.json").read_text())


def reference(journal: str | None = None, field: str | None = None) -> dict:
    """Figure text sizes in published papers: all of them, one journal, or one field.

    A journal that has no entry of its own falls back to all papers. `journals()` and
    `fields()` list the names.
    """
    ref = _load()
    if journal:
        return ref["journals"].get(journal, ref["all"])
    if field:
        return ref["fields"][field]
    return ref["all"]


def journals() -> list[str]:
    """The journals that have their own entry in the reference."""
    return sorted(_load()["journals"])


def fields() -> list[str]:
    """The fields that have their own entry in the reference."""
    return sorted(_load()["fields"])


def verdict(result: Result, journal: str | None = None, smallest_ok: float = 6.0, field: str | None = None) -> dict:
    """ok / small / large for one figure, against the middle half of published papers.

    A figure is "small" if its median prints below the 25th percentile of paper medians,
    or a tenth of its text below `smallest_ok` pt; "large" above the 75th percentile.
    """
    ref = reference(journal, field)
    low, high = ref["paper_medians_p25_p75"]
    out = result.summary() | {"reference_median_pt": ref["median_pt"], "reference_range_pt": [low, high]}
    if not result.sizes:
        return out | {"verdict": "no text found"}
    # 0.05 pt of slack: a PDF stores 6 pt text as 5.99 pt
    if result.median < low or (result.percentile(10) or 0) < smallest_ok - 0.05:
        v = "small"
    elif result.median > high:
        v = "large"
    else:
        v = "ok"
    return out | {"verdict": v, "scale_to_reference": round(ref["median_pt"] / result.median, 2)}
