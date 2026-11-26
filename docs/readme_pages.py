"""Split README.md into the pages of the docs site, so the README stays the one source.

Writes docs/index.md, docs/guide/*.md, docs/cli.md, docs/limits.md and docs/development.md
(all gitignored). Run before `mkdocs build` or `mkdocs serve`:

    python docs/readme_pages.py && mkdocs serve
"""
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RAW = "https://raw.githubusercontent.com/jake-casselman/figfit/main/docs/"
BLOB = "https://github.com/jake-casselman/figfit/blob/main/docs/"

# README "## " section -> page. Sections not listed go on the page of the section before them.
PAGES = {
    None: "index.md",                      # everything before the first numbered section
    "1. Work out the size": "guide/size.md",
    "2. Measure what prints": "guide/measure.md",
    "3. Compare with published papers": "guide/compare.md",
    "4. Set the printed sizes": "guide/set-sizes.md",
    "5. Pick a size for small panels": "guide/small-panels.md",
    "6. Find colliding text": "guide/find-collisions.md",
    "7. Fix colliding text": "guide/fix-collisions.md",
    "8. Check colours for colour-blind readers": "guide/colour.md",
    "Command line": "cli.md",
    "All functions": "functions.md",
    "Accuracy and limits": "limits.md",
    "Development": "development.md",
}


def slug(title):
    """GitHub's and MkDocs' heading anchor: lower case, punctuation dropped, spaces to hyphens."""
    s = re.sub(r"[^\w\- ]", "", title.strip().lower())
    return s.replace(" ", "-")


def rel(target, page):
    """Link from `page` to `target` (both relative to docs/)."""
    return posixpath.relpath(target, posixpath.dirname(page) or ".")


def split(readme):
    """[(page, lines)] in README order; headings promoted one level on every page but the index."""
    out, page, in_code = {}, PAGES[None], False
    for line in readme.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^## (.+)$", line)
        if m and m.group(1).strip() in PAGES:
            page = PAGES[m.group(1).strip()]
        out.setdefault(page, []).append(line)
    return out


def anchors(pages):
    """README anchor -> 'page' or 'page#anchor' on the site."""
    where = {}
    for page, lines in pages.items():
        in_code = False
        for line in lines:
            if line.startswith("```"):
                in_code = not in_code
            m = None if in_code else re.match(r"^(#{2,4}) (.+)$", line)
            if m:
                a = slug(m.group(2))
                top = m.group(1) == "##" and page != "index.md" and PAGES.get(m.group(2).strip()) == page
                where[a] = page if top else f"{page}#{a}"
    return where


def html_target(path):
    """What a raw-HTML href must point at once the site is built (MkDocs only rewrites Markdown links)."""
    base, _, frag = path.partition("#")
    if base.endswith((".md", ".ipynb")):
        base = base.rsplit(".", 1)[0] + ".html"
    return base + ("#" + frag if frag else "")


def fix_links(text, page, where):
    def target(t):
        if t.startswith("#") and t[1:] in where:
            dpage, _, frag = where[t[1:]].partition("#")
            if dpage == page:
                return "#" + frag if frag else "#"
            return rel(dpage, page) + ("#" + frag if frag else "")
        for prefix in (RAW, BLOB):
            if t.startswith(prefix):
                return rel(t[len(prefix):], page)
        if t.startswith("docs/"):
            return rel(t[len("docs/"):], page)
        return t

    text = re.sub(r"\]\(([^)\s]+)\)", lambda m: f"]({target(m.group(1))})", text)
    text = re.sub(r'(href|src)="([^"]+)"',
                  lambda m: f'{m.group(1)}="{html_target(target(m.group(2))) if m.group(1) == "href" else target(m.group(2))}"',
                  text)
    return text


def promote(lines):
    """'## x' -> '# x', '### x' -> '## x', outside code blocks."""
    out, in_code = [], False
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^#{2,6} ", line):
            line = line[1:]
        out.append(line)
    return out


def main():
    readme = (ROOT / "README.md").read_text()
    pages = split(readme)
    where = anchors(pages)
    for page, lines in pages.items():
        if page != "index.md":
            lines = promote(lines)
        text = fix_links("\n".join(lines).strip() + "\n", page, where)
        note = "<!-- Generated from README.md by docs/readme_pages.py: edit the README, not this file. -->\n"
        dest = DOCS / page
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(note + text)
        print("wrote", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
