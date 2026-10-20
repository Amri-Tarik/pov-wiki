"""What search engines and link previews see.

- Descriptions: every page gets its own meta description, taken from the summary right under its
  title (a node's type and effect, a mod's rule, an item's description...). Generated and
  hand-written pages alike; a page with its own front matter keeps it.
- Preview image: the page's own icon (front matter "image"). overrides/main.html turns these into
  Open Graph / Twitter tags, and points each page's language alternates at the same page in the
  other languages (the theme links their home pages).
- Site root: robots.txt pointing at every language's sitemap.
"""

import html
import json
import posixpath
import re
from pathlib import Path

DESCRIPTION_CHARS = 158
_TAG = re.compile(r"<[^>]+>")
_ART = re.compile(r'<img class="pov-art"[^>]*src="([^"]+)"')
_TREE_LINK = re.compile(r'<a href="[^"]*#[^"]*">[^<]*</a>')  # "Show on tree", in any language
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)(\{[^}]*\})?")
_SKIP = re.compile(r"^(    |\s*(\||!!!|\?\?\?|<div|</div|```|---|\{))")  # tables, admonitions and their body, blocks


def describe(md: str) -> str:
    """The summary under a page's title, as plain text, cut at a word near 158 characters."""
    lines = md.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if line.startswith("# ")), 0)
    parts = []
    for line in lines[start:]:
        if line.startswith("#"):  # the next heading ends the summary
            break
        if not line.strip():
            continue
        if _SKIP.match(line):
            if parts:  # the summary is the text before the first table or box
                break
            continue
        text = _LINK.sub(r"\1", _IMAGE.sub("", _TREE_LINK.sub("", line)))
        text = _TAG.sub(" ", text)
        text = html.unescape(re.sub(r"[*_`]", "", text))
        text = re.sub(r"\s+", " ", text).strip(" ·")
        if text:
            parts.append(text if text[-1] in ".!?:;" else text + ".")
        if sum(len(p) for p in parts) > DESCRIPTION_CHARS:
            break
    text = " ".join(parts)
    if len(text) > DESCRIPTION_CHARS:
        text = text[:DESCRIPTION_CHARS].rsplit(" ", 1)[0].rstrip(",;:·") + "…"
    return text


def with_description(md: str, fallback: str, page: str, base_url: str) -> str:
    """The page with front matter for search results and link previews: its description, and
    its own icon (the first node/item art on it) as the preview image. page: the Markdown file's
    path in the docs; base_url: the language's root URL. A page with its own front matter keeps
    it."""
    if md.startswith("---"):
        return md
    text = describe(md)
    if len(text) < 60:  # too short to stand alone in a search result
        text = f"{text} {fallback}".strip()
    meta = [f"description: {json.dumps(text, ensure_ascii=False)}"]
    if art := _ART.search(md):  # relative to the Markdown file, like the site generator reads it
        image = posixpath.normpath(posixpath.join(posixpath.dirname(page), art.group(1)))
        meta.append(f"image: {json.dumps(base_url.rstrip('/') + '/' + image)}")
    return "---\n" + "\n".join(meta) + "\n---\n\n" + md


def write_root(site: Path, langs: list[str], site_url: str) -> None:
    """robots.txt at the site root, listing every language's sitemap."""
    root = site_url.rstrip("/")
    lines = ["User-agent: *", "Allow: /", ""] + [f"Sitemap: {root}/{code}/sitemap.xml" for code in langs]
    (site / "robots.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
