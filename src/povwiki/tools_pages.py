"""Tools: calculators for what is tedious to find out by playing (javascripts/<tool>.js).

Each tool is a page with an empty container the script fills in, and a data file next to it,
written per language by the build (names and labels in that language).
"""

import json

from .pages import Ctx, _footer

ASCENSION_PAGE = "tools/ascension.md"
ASCENSION_DATA = "assets/data/ascension.json"


def page_tools(ctx: Ctx) -> dict[str, str]:
    from .ascension import calculator_data
    from .formula_pages import LOOT_PAGE, formula_block, shown
    from .markup import rel

    data = calculator_data(ctx) if shown(ctx, "ascension") else {}
    if not data:
        return {}
    ui = ctx.loc.ui
    page = ASCENSION_PAGE
    md = [f"# {ui('tools.ascension.title')}", "",
          ui("tools.ascension.intro", link=f"{rel(LOOT_PAGE, page)}#ascension"), "",
          # Relative to the page's file, like a link: the site generator adjusts it to the page's URL.
          f'<div id="pov-ascension" data-src="{rel(ASCENSION_DATA, page)}"><noscript>{ui("tools.noscript")}</noscript></div>', ""]
    md += formula_block(ctx, "ascension", page, anchor=False, heading=ui("formula.mechanics"))
    return {page: "\n".join(md + _footer(ctx)),
            ASCENSION_DATA: json.dumps(data, ensure_ascii=False, separators=(",", ":"))}
