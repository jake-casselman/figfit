"""figfont command line.

  figfont check FIGURE[@WIDTH] ...   printed text size of figure files (WIDTH in inches, default --width)
  figfont paper PAPER.pdf ...        figure text in compiled papers (vector text only)
  figfont scale TARGET DRAWN_WIDTH PRINTED_WIDTH   font size to draw at to print at TARGET pt
"""
from __future__ import annotations

import argparse
import json

from . import compare, measure, scale


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="figfont", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="figure files at their printed width")
    c.add_argument("figures", nargs="+")
    c.add_argument("--width", type=float, default=scale.latex_length_in(372),
                   help="printed width in inches (default: 372 pt, a Springer Nature text width)")
    c.add_argument("--journal")
    c.add_argument("--json", action="store_true")
    p = sub.add_parser("paper", help="compiled paper PDFs")
    p.add_argument("pdfs", nargs="+")
    p.add_argument("--journal")
    p.add_argument("--json", action="store_true")
    s = sub.add_parser("scale", help="font size to draw at")
    s.add_argument("target_pt", type=float)
    s.add_argument("drawn_width", type=float)
    s.add_argument("printed_width", type=float)
    a = ap.parse_args(argv)

    if a.cmd == "scale":
        print(f"{scale.drawn_pt_for(a.target_pt, a.drawn_width, a.printed_width):.2f} pt")
        return 0
    if a.cmd == "check":
        results = []
        for arg in a.figures:
            path, _, width = arg.rpartition("@") if "@" in arg else (arg, "", "")
            results.append(measure.figure(path or arg, float(width) if width else a.width))
    else:
        results = [measure.pdf_figure_text(p) for p in a.pdfs]
    rows = [compare.verdict(r, a.journal) for r in results]
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    ref = compare.reference(a.journal)
    print(f"published papers: median {ref['median_pt']} pt, middle half of papers "
          f"{ref['paper_medians_p25_p75'][0]}-{ref['paper_medians_p25_p75'][1]} pt")
    for r in rows:
        if r["median_pt"] is None:
            print(f"  {r['name']:32s} no text found")
            continue
        print(f"  {r['name']:32s} median {r['median_pt']:5.2f} pt ({scale.cap_height_mm(r['median_pt']):.1f} mm caps)"
              f"  p10 {r['p10_pt']:5.2f}  {r['verdict'].upper():6s} x{r['scale_to_reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
