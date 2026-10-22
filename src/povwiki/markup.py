"""Convert the game's rich text (Unity TextMeshPro tags) to Markdown/HTML for the site."""

import html
import posixpath
import re

from .i18n import Localizer

_TAG = re.compile(r'<link="([^"]+)">(.*?)</link>|<color=([#\w]+)>(.*?)</color>|<b>(.*?)</b>|<[^>]*>', re.S)
_ANY_TAG = re.compile(r"<[^>]+>")
_MD_SPECIAL = re.compile(r"([\\`*\[\]])")

TOOLTIP_CHARS = 300


def plain(s: str) -> str:
    """Strip all markup (for tooltips, summaries)."""
    return _ANY_TAG.sub("", s)


# Keywords whose glossary page is merged into another page about the same thing (a mastery
# option, a keystone, a weapon type): slug -> that page. The same in every language, set once
# before the languages are built (pages.merged_terms).
_merged: dict[str, str] = {}


def set_merged(merged: dict[str, str]) -> None:
    _merged.clear()
    _merged.update(merged)


def merged_into(page: str) -> list[str]:
    """The keywords merged into this page."""
    return [slug for slug, target in _merged.items() if target == page]


def is_merged(slug: str) -> bool:
    return slug in _merged


def glossary_path(slug: str) -> str:
    """Where a keyword is explained: its glossary page, or the page it is merged into."""
    return _merged.get(slug) or f"glossary/{slug}.md"


def rel(target: str, page: str) -> str:
    """Link from one docs page to another, both given relative to the docs root."""
    return posixpath.relpath(target, posixpath.dirname(page) or ".")


def summary(term: dict, limit: int = TOOLTIP_CHARS) -> str:
    text = plain(" ".join(term["text"]))
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _text(s: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", html.escape(s, quote=False))


def to_md(s: str, loc: Localizer, page: str) -> str:
    """Game text -> inline Markdown for the docs page `page`. Keywords become links to their
    glossary page, with the definition on hover."""
    out, pos = [], 0
    for m in _TAG.finditer(s):
        out.append(_text(s[pos : m.start()]))
        pos = m.end()
        slug, inner = m.group(1), m.group(2)
        if slug is not None:
            text = to_md(inner, loc, page)
            if term := loc.wiki.get(slug):
                tip = summary(term).replace('"', "”")
                out.append(f'[{text}]({rel(glossary_path(slug), page)} "{tip}"){{ .pov-kw }}')
            else:  # e.g. pt.scale:* (in-game scaling tooltips), nothing to link to
                out.append(text)
        elif m.group(3) is not None:
            out.append(f'<span style="color:{m.group(3)}">{to_md(m.group(4), loc, page)}</span>')
        elif m.group(5) is not None:
            out.append(f"<b>{to_md(m.group(5), loc, page)}</b>")
        # any other tag is dropped
    out.append(_text(s[pos:]))
    return "".join(out)


def to_html(s: str) -> str:
    """Game text -> inline HTML without links (for the tree viewer's tooltips)."""
    out, pos = [], 0
    for m in _TAG.finditer(s):
        out.append(html.escape(s[pos : m.start()], quote=False))
        pos = m.end()
        if m.group(1) is not None:
            out.append(f'<span class="pov-kw">{to_html(m.group(2))}</span>')
        elif m.group(3) is not None:
            out.append(f'<span style="color:{m.group(3)}">{to_html(m.group(4))}</span>')
        elif m.group(5) is not None:
            out.append(f"<b>{to_html(m.group(5))}</b>")
    out.append(html.escape(s[pos:], quote=False))
    return "".join(out)


def slugs(s: str) -> list[str]:
    """Keyword slugs linked from a piece of game text."""
    return re.findall(r'<link="([^"]+)">', s)
