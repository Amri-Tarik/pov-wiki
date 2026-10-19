"""Convert the game's rich text (Unity TextMeshPro tags) to HTML for the site."""

import html
import re

from .i18n import Localizer

# Matched on html-escaped text, so anything that is not one of these tags stays escaped.
_LINK = re.compile(r'&lt;link="([^"]+)"&gt;(.*?)&lt;/link&gt;')
_COLOR = re.compile(r"&lt;color=([#\w]+)&gt;(.*?)&lt;/color&gt;")
_BOLD = re.compile(r"&lt;b&gt;(.*?)&lt;/b&gt;")
_ANY_TAG = re.compile(r"<[^>]+>")


def plain(s: str) -> str:
    """Strip all markup (for tooltips, search text)."""
    return _ANY_TAG.sub("", s)


def to_html(s: str, loc: Localizer) -> str:
    out = html.escape(s, quote=False)
    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _COLOR.sub(r'<span style="color:\1">\2</span>', out)

    def link(m: re.Match) -> str:
        slug, text = m.group(1), m.group(2)
        # Keywords link to the mod's own wiki entries; the definition shows on hover.
        tip = loc.game.get(f"@wiki.{slug}.text")
        title = f' title="{html.escape(plain(tip), quote=True)}"' if tip else ""
        return f'<span class="pov-kw" data-kw="{slug}"{title}>{text}</span>'

    return _LINK.sub(link, out)
