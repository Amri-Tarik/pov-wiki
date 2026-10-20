"""Items section: mods (affixes) first. Bases, item classes and mod pools come later
(notes/items-plan.md).

Mod text, tiers and values come from the game (harness/loot.py renders each tier like the item
tooltip); roll rules are the mod's item tags, put into words with the wiki's tag labels.
"""

import json
import re
from collections import defaultdict

from .markup import plain, rel, to_md
from .pages import Ctx, _badge, _cell, _footer, _table

MODS_PAGE = "items/mods.md"
# Item tags -> the item class a rule is about (for grouping the mods list).
_CLASS_OF = {
    "weapon": "weapons", "melee": "weapons", "ranged": "weapons", "spell": "weapons", "magical": "weapons",
    "shooting": "weapons", "throwing": "weapons", "uses.stamina": "weapons",
    "armour": "armour", "shield": "shields", "jewel": "jewels", "trinket": "trinkets", "belt": "belts", "ring": "rings",
    "tool": "tools", "fishing": "tools", "builds": "tools",
}
_CLASS_PREFIX = {"kind.": "weapons", "slot.": "armour", "def.": "armour", "shield.": "shields", "jewel.": "jewels"}
_CLASS_ORDER = ["weapons", "armour", "shields", "jewels", "rings", "trinkets", "belts", "tools"]
# Which slot multipliers matter for a mod, by the classes it rolls on (LootRoller.SlotMult).
_SLOTS_FOR = {"weapons": ["one_handed", "two_handed"], "armour": ["chest", "legs"], "shields": ["tower", "buckler"]}
_RANGE = re.compile(r"\(([-−]?\d+(?:[.,]\d+)?)–([-−]?\d+(?:[.,]\d+)?)\)")


def mod_path(affix: dict) -> str:
    return f"items/mod/{affix['id']}.md"


def _classes(affix: dict) -> list[str]:
    found = set()
    for tag in affix["allowAll"] + affix["allowAny"]:
        cls = _CLASS_OF.get(tag) or next((c for p, c in _CLASS_PREFIX.items() if tag.startswith(p)), None)
        if cls:
            found.add(cls)
    return [c for c in _CLASS_ORDER if c in found]


def _tags(ctx: Ctx, tags: list[str], joiner: str) -> str:
    labels = [ctx.loc.ui(f"tag.{t}") for t in tags]
    if len(labels) < 2:
        return "".join(labels)
    return ", ".join(labels[:-1]) + f" {joiner} " + labels[-1]


def _rule(ctx: Ctx, affix: dict) -> str:
    """The roll rule in words: all of the allowAll tags, one of allowAny, none of denyAny."""
    ui = ctx.loc.ui
    parts = []
    if affix["allowAll"]:
        parts.append(ui("items.rule_all", tags=_tags(ctx, affix["allowAll"], "and")))
    if affix["allowAny"]:
        parts.append(ui("items.rule_any", tags=_tags(ctx, affix["allowAny"], "or")))
    if affix["denyAny"]:
        parts.append(ui("items.rule_not", tags=_tags(ctx, affix["denyAny"], "or")))
    return "; ".join(parts) or ui("items.any_item")


def _title(affix: dict) -> str:
    """A mod's name: its line with the numbers as #, like "+# to maximum health"."""
    line = plain(affix["tiers"][0]["text"]["base"]) if affix["tiers"] else plain(affix["text"])
    return re.sub(r"[-−]?\d+(?:[.,]\d+)?", "#", _RANGE.sub("#", line))


def _min_level(affix: dict) -> int:
    """Item levels start at 1 (CraftLevel.Of, loot levels), so a tier from 0 is a tier from 1."""
    return max(1, min((t["minLevel"] for t in affix["tiers"]), default=affix["minLevel"]))


def _group_key(affix: dict) -> tuple:
    """Index section: the item classes a mod rolls on; jewel mods also by jewel type."""
    classes = tuple(_classes(affix))
    if classes == ("jewels",):
        return classes + tuple(sorted({t for t in affix["allowAll"] + affix["allowAny"] if t.startswith("jewel.")}))
    return classes


def _values(text: str) -> str:
    """Just the numbers of a line ("(8–14)"), for tables where the wording repeats."""
    found = re.findall(r"\([^()]*–[^()]*\)|[-−]?\d+(?:[.,]\d+)?%?", plain(text))
    return ", ".join(found) if found else plain(text)


def biome(ctx: Ctx, level: int) -> str:
    """An item level as the biome it belongs to (the mod's BiomeLevels): the highest biome whose
    level it reaches. Ocean shares Mistlands' level and isn't a progression step, so it's skipped."""
    steps = [b for b in ctx.loc.loot["biomes"] if b["id"] != "Ocean"]
    found = steps[0]
    for b in steps:
        if b["level"] <= level:
            found = b
    return ctx.loc.vkey(f"biome_{found['id'].lower()}", found["id"])


def _levels(ctx: Ctx, lo: int, hi: int | None) -> str:
    """An item level range as biomes, the numbers kept small: "Swamp – Plains (43–129)"."""
    lo = max(1, lo)
    if hi:
        a, b = biome(ctx, lo), biome(ctx, hi)
        names = a if a == b else f"{a} – {b}"
        return f"{names} <small>({ctx.loc.ui('items.level_range', min=lo, max=hi)})</small>"
    return f"{biome(ctx, lo)}+ <small>({ctx.loc.ui('items.level_from', min=lo)})</small>"


def _place(ctx: Ctx, affix: dict) -> str:
    return ctx.loc.ui(f"items.{affix['place']}")


def _essences_for(ctx: Ctx, affix: dict) -> list[str]:
    loot = ctx.loc.loot
    return [loot["items"].get(e, {}).get("name", e) for e, d in loot["essences"].items() if d["boss"] in affix["bossFamilies"]]


def _source(ctx: Ctx, affix: dict) -> str:
    ui = ctx.loc.ui
    if affix["source"] == "essence":
        return ui("items.source_essence", items=", ".join(_essences_for(ctx, affix)))
    if affix["source"] == "none":
        return _badge(ui("badge.broken"), ui("items.not_generated_tip"))
    return ui("items.source_loot")


def page_mods(ctx: Ctx) -> dict[str, str]:
    """All item mods: an index grouped by what they roll on, and a page per mod."""
    loc, affixes = ctx.loc, ctx.loc.loot["affixes"]
    ui = loc.ui
    pages = {}

    def rows(items: list[dict]) -> list[list[str]]:
        return [[
            f"[{_cell(_title(a))}]({rel(mod_path(a), MODS_PAGE)})",
            _place(ctx, a),
            _cell(_rule(ctx, a)),
            f"{biome(ctx, _min_level(a))} <small>({_min_level(a)})</small>",
            str(len(a["tiers"])),
            f"{a['weight']:g}",
        ] for a in sorted(items, key=lambda a: (a["place"], _title(a).lower()))]

    header = [ui("items.mod"), ui("items.place"), ui("items.rolls_on"), ui("items.min_level"), ui("items.tiers"), ui("items.weight")]
    groups = defaultdict(list)
    for a in affixes:
        if a["source"] == "loot":
            groups[_group_key(a)].append(a)
    md = [f"# {ui('items.mods')}", "", ui("items.mods_intro"), ""]
    def order(key: tuple) -> tuple:
        classes = [c for c in key if c in _CLASS_ORDER]
        return [_CLASS_ORDER.index(c) for c in classes] or [99], len(classes), key

    for key in sorted(groups, key=order):
        classes = [c for c in key if c in _CLASS_ORDER]
        title = " & ".join(ui(f"class.{c}") for c in classes) or ui("items.other")
        if len(key) > len(classes):  # jewel types
            title += ": " + ", ".join(ui(f"tag.{t}") for t in key[len(classes):])
        md += [f"## {title} ({len(groups[key])})", ""] + _table(header, rows(groups[key]))
    for source, title, note in (("essence", "essence_only", "essence_only_note"), ("none", "not_generated", "not_generated_note")):
        chosen = [a for a in affixes if a["source"] == source]
        if chosen:
            md += [f"## {ui('items.' + title)} ({len(chosen)})", "", ui("items." + note), ""] + _table(header, rows(chosen))
    pages[MODS_PAGE] = "\n".join(md + _footer(ctx))

    for a in affixes:
        pages.update(_mod_page(ctx, a))
    return pages


def _mod_page(ctx: Ctx, a: dict) -> dict[str, str]:
    loc, page = ctx.loc, mod_path(a)
    ui = loc.ui
    md = [f"# {_cell(_title(a))}", "", f"<b>{_place(ctx, a)}</b> · {_cell(_rule(ctx, a))}", ""]
    if a["source"] == "none":
        md += [f'!!! warning "{ui("page.unimplemented")}"', f"    {ui('items.not_generated_note')}", ""]

    info = [[ui("items.rolls_on"), _cell(_rule(ctx, a))], [ui("items.source"), _source(ctx, a)]]
    if a["families"]:
        info.append([ui("items.families"), ", ".join(a["families"])])
    if a["group"]:
        info.append([ui("items.group"), f"`{a['group']}` — {ui('items.group_note')}"])
    md += _table([loc.ui("col.property"), loc.ui("col.value")], info)

    # Tiers, as a regular item rolls them.
    total = sum(t["weight"] for t in a["tiers"]) or 1
    md += [f"## {ui('items.tiers')}", ""]
    md += _table(
        [ui("items.tier"), ui("items.item_level"), ui("items.value"), ui("items.weight"), ui("items.share")],
        [[t["id"], _levels(ctx, t["minLevel"], t["maxLevel"]), _cell(to_md(t["text"]["base"], loc, page)),
          f"{t['weight']:g}", f"{100 * t['weight'] / total:.1f}%"] for t in a["tiers"]],
    )

    # The same tiers on the slots this mod can roll on, when values scale with the slot.
    slots = [s for c in _classes(a) for s in _SLOTS_FOR.get(c, [])]
    if not a["scaled"]:
        md += [f"*{ui('items.local_note')}*", ""]
    elif slots:
        md += [f"## {ui('items.slot_values')}", "", ui("items.slot_values_note"), ""]
        md += _table(
            [ui("items.tier"), ui("slot.base"), *(ui(f"slot.{s}") for s in slots)],
            [[t["id"], *(_cell(_values(t["text"][s])) for s in ["base", *slots])] for t in a["tiers"]],
        )

    from .patch_pages import history

    md += history(ctx, "mods", [a["id"]], page)
    raw = {k: a[k] for k in ("id", "place", "target", "families", "group", "allowAll", "allowAny", "denyAny", "weight", "generation")}
    raw["tiers"] = [{k: t[k] for k in ("id", "min", "max", "step", "minLevel", "maxLevel", "weight")} for t in a["tiers"]]
    md += [f'??? abstract "{ui("page.game_data")}"', "", "    ```json"]
    md += ["    " + line for line in json.dumps(raw, ensure_ascii=False, indent=2).splitlines()]
    md += ["    ```", ""]
    return {page: "\n".join(md + _footer(ctx))}


# ---- Keyword references (for glossary pages) ----------------------------------------------------


def mods_by_keyword(ctx: Ctx) -> dict[str, list[dict]]:
    """keyword slug -> the mods whose text links it (any tier, any slot), as the game words them."""
    from .markup import slugs

    found: dict[str, list[dict]] = defaultdict(list)
    for a in ctx.loc.loot["affixes"]:
        texts = [a["text"]] + [txt for t in a["tiers"] for txt in t["text"].values()]
        for slug in {s for txt in texts for s in slugs(txt)}:
            found[slug].append(a)
    return found


def keyword_mods_section(ctx: Ctx, mods: list[dict], page: str) -> list[str]:
    """The mods that mention a keyword: a table, folded away when it is long."""
    ui = ctx.loc.ui
    rows = [[
        f"[{_cell(_title(a))}]({rel(mod_path(a), page)})",
        _place(ctx, a),
        _cell(_rule(ctx, a)),
        _source(ctx, a) if a["source"] != "loot" else f"{biome(ctx, _min_level(a))} <small>({_min_level(a)})</small>",
    ] for a in sorted(mods, key=lambda a: (a["source"] != "loot", _title(a).lower()))]
    table = _table([ui("items.mod"), ui("items.place"), ui("items.rolls_on"), ui("items.min_level")], rows)
    title = f"{ui('items.mods')} ({len(mods)})"
    if len(mods) <= 12:
        return [f"#### {title}", ""] + table
    return [f'??? note "{title}"', ""] + ["    " + line if line else "" for line in table]
