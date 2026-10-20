"""Monsters: the modifiers creatures can wear, and the rarity their stars give them.

- Modifiers (harness/monsters.py): each one's in-game name, description and icon, with its
  numbers at the server defaults. Some descriptions round (Swift: "half again" is 1.40×), so
  the numbers are shown beside them.
- Rarity: which star counts show as magic, rare and unique, in the game's colours.
"""

import html

from .markup import glossary_path, rel
from .pages import Ctx, _badge, _footer, _img, _table

MODS_PAGE = "monsters/mods.md"
_ELEMENTS = ("burning", "chilling", "shocking", "venomous")  # RarityMods.Fill: one per creature


def mod_anchor(mod_id: str) -> str:
    """Link target of one modifier, for pages that name it (bosses that never roll it...)."""
    return f"{MODS_PAGE}#mod-{mod_id}"


def _stars(stars: list[int], last: bool) -> str:
    if last:  # the top rarity has no ceiling
        return f"{stars[0]}+"
    return str(stars[0]) if len(stars) == 1 else f"{stars[0]}–{stars[-1]}"


def _settings(mod: dict) -> str:
    return "<br>".join(
        f'<span title="{html.escape(s["about"], quote=True)}">{s["label"]}</span>: **{s["value"]}**'
        for s in mod["settings"])


def page_monster_mods(ctx: Ctx) -> dict[str, str]:
    monsters, ui, page = ctx.loc.monsters, ctx.loc.ui, MODS_PAGE
    if not monsters.get("mods"):
        return {}
    names = {m["id"]: m["name"] for m in monsters["mods"]}
    md = [f"# {ui('monsters.mods')}", "", ui("monsters.mods_intro"), ""]

    md += [f"## {ui('monsters.rarity')}", "", ui("monsters.rarity_intro"), ""]
    tiers = monsters["rarity"]
    md += _table([ui("monsters.rarity_col"), ui("monsters.stars")], [
        [f'<span style="color:{t["color"]}">**{t["name"]}**</span>', _stars(t["stars"], t is tiers[-1])]
        for t in tiers])
    md += [ui("monsters.rarity_loot", quantity=rel(glossary_path("item-quantity"), page),
              rarity=rel(glossary_path("item-rarity"), page)), ""]

    off = set(monsters.get("bossOff") or [])
    md += [f"## {ui('monsters.modifiers')} ({len(monsters['mods'])})", "", ui("monsters.values_note"), ""]
    rows = []
    for m in monsters["mods"]:
        icon = _img(ctx.icons.path(m["icon"]), page, 40) if ctx.icons else ""
        badge = " " + _badge(ui("monsters.no_bosses"), ui("monsters.no_bosses_tip")) if m["id"] in off else ""
        rows.append([icon, f'<span id="mod-{m["id"]}"></span>**{m["name"]}**{badge}', m["about"], _settings(m) or "—"])
    md += _table(["", ui("col.name"), ui("monsters.in_game"), ui("monsters.values")], rows)

    md += [f"## {ui('monsters.rules')}", ""]
    md += [f"- {ui('monsters.rule_random')}"]
    md += [f"- {ui('monsters.rule_element', mods=', '.join(names[e] for e in _ELEMENTS if e in names))}"]
    if "blink" in names:
        md += [f"- {ui('monsters.rule_blink', mod=names['blink'])}"]
    if off:
        md += [f"- {ui('monsters.rule_bosses', mods=', '.join(names.get(i, i) for i in sorted(off, key=lambda i: names.get(i, i))))}"]
    md += [""]
    return {page: "\n".join(md + _footer(ctx))}
