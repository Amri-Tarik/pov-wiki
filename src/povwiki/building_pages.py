"""The mod's buildings (harness/buildings.py), on top of the Valheim pieces they copy.

- Cost: the copied piece's (pieces.json), plus what the mod adds; the Rune Carver Table has its
  own. Station: the copied piece's, unless the mod moves it.
- Unlock: the craft masteries whose option grants the building's flag (the craft tree's
  "flag"); each of those mastery pages links back.
- What it does: the kiln's conversions on the smelter's fuel and timing; what the rune carver
  table crafts; the vacuum chest's radius and categories; the plants Wild Sowing can replant.
- Materials link to their item pages, and those list the buildings they go into.
"""

from collections import defaultdict

from .base_pages import _icon, _item_name, _station, bases
from .gear_pages import _link, currency_path
from .markup import glossary_path, plain, rel
from .pages import CRAFTING, Ctx, _footer, _img, _table, option_path

BUILDINGS_PAGE = "crafting/buildings.md"
WILD = "PT_wild_"
# Overview line for the pieces the game gives no description.
SUMMARIES = {WILD: "buildings.wild_summary", "PT_RuneCarverTable": "buildings.table_summary"}


def building_path(building_id: str) -> str:
    return f"crafting/building/{building_id.rstrip('_')}.md"


def _craft_ctx(ctx: Ctx) -> Ctx | None:
    return next((c for c in [ctx, *ctx.others] if c.spec is CRAFTING), None)


def _piece(ctx: Ctx, prefab: str) -> dict:
    return (ctx.loc.valheim or {}).get("pieces", {}).get(prefab) or {}


def display_name(ctx: Ctx, b: dict) -> str:
    if b["id"] == WILD:  # not a piece: the mod's wiki names it
        return plain(ctx.loc.wiki.get("craft-wild-sowing", {}).get("title") or ctx.loc.ui("buildings.wild_sowing"))
    return b["name"] or ctx.loc.vtext(_piece(ctx, b["source"]).get("name")) or b["id"]


def _art(ctx: Ctx, b: dict, page: str, px: int) -> str:
    if not ctx.icons:
        return ""
    icon = b.get("icon") or (f"vh:{_piece(ctx, b['source'])['icon'].removesuffix('.png')}"
                             if _piece(ctx, b["source"]).get("icon") else None)
    if b["id"] == WILD:
        icon = "vh:Cultivator"
    return _img(ctx.icons.path(icon), page, px)


def cost(ctx: Ctx, b: dict) -> list[dict]:
    """What it takes to build: its own cost, or the copied piece's plus the mod's extra."""
    if "resources" in b:
        return b["resources"]
    return [*(_piece(ctx, b["source"]).get("resources") or []), *(b.get("extra") or [])]


def _station_md(ctx: Ctx, b: dict, page: str) -> str:
    station = b["station"] if "station" in b else _piece(ctx, b["source"]).get("station")
    if not station:
        return ctx.loc.ui("buildings.no_station")
    if station.startswith("PT_"):  # one of the mod's own: link its page
        other = next((x for x in ctx.loc.buildings if x["id"] == station), None)
        if other:
            return f"[{display_name(ctx, other)}]({rel(building_path(station), page)})"
    return _station(ctx, {"station": station})


def unlocked_by(ctx: Ctx) -> dict[str, list[dict]]:
    """building flag -> the craft mastery option groups that grant it."""
    craft, found = _craft_ctx(ctx), defaultdict(list)
    if craft is None:
        return found
    for g in craft.option_groups.values():
        flags = {o.get("flag") for o in g["options"]} - {None}
        for flag in flags:
            found[flag].append(g)
    return found


def building_of_flag(ctx: Ctx) -> dict[str, dict]:
    """flag -> building, for the mastery pages that unlock one."""
    return {b["unlock"]: b for b in ctx.loc.buildings if b.get("unlock")}


def building_link(ctx: Ctx, b: dict, page: str) -> str:
    return f"[{display_name(ctx, b)}]({rel(building_path(b['id']), page)})"


def used_to_build(ctx: Ctx) -> dict[str, list[dict]]:
    """material -> buildings that cost it (for item pages)."""
    uses: dict[str, list[dict]] = defaultdict(list)
    for b in ctx.loc.buildings:
        for r in cost(ctx, b):
            if b not in uses[r["item"]]:
                uses[r["item"]].append(b)
    return uses


def wild_plants(ctx: Ctx, b: dict) -> list[dict]:
    """WildSowing.Build: a sapling for each wild plant that regrows (not a planted crop) and gives
    food, an herb or a crop with a seed of the mod. Planted with that seed, else the crop."""
    vh = ctx.loc.valheim or {}
    items, plants = vh.get("items", {}), {}
    for prefab, p in sorted((vh.get("pickables") or {}).items()):
        item = p.get("item")
        if " (" in prefab or not item or p.get("plant") or p.get("respawn", 0) <= 0 or prefab in b["excluded"]:
            continue  # " (n)": copies placed in a scene, not prefabs
        s = items.get(item) or {}
        if not (s.get("m_food", 0) > 0 or s.get("m_foodStamina", 0) > 0 or s.get("m_foodEitr", 0) > 0
                or item in b["herbs"] or item in b["seeds"]):
            continue
        plants.setdefault(item, {"item": item, "seed": b["seeds"].get(item), "minutes": p["respawn"]})
    return list(plants.values())


def page_buildings(ctx: Ctx) -> dict[str, str]:
    buildings, ui, page = ctx.loc.buildings, ctx.loc.ui, BUILDINGS_PAGE
    if not buildings:
        return {}
    md = [f"# {ui('buildings.title')}", "", ui("buildings.intro"), ""]
    rows = []
    for b in buildings:
        what = b["description"] or ui(SUMMARIES.get(b["id"], "buildings.no_summary"))
        rows.append([_art(ctx, b, page, 40), f"**{building_link(ctx, b, page)}**", what])
    md += _table(["", ui("col.name"), ui("col.effect")], rows)
    md += [ui("buildings.vanilla_note"), ""]
    pages = {page: "\n".join(md + _footer(ctx))}
    found, unlocks = bases(ctx), unlocked_by(ctx)
    for b in buildings:
        pages[building_path(b["id"])] = _building_page(ctx, b, found, unlocks)
    return pages


def _building_page(ctx: Ctx, b: dict, found: dict, unlocks: dict) -> str:
    ui, page = ctx.loc.ui, building_path(b["id"])
    md = [f"# {display_name(ctx, b)}", ""]
    if art := _art(ctx, b, page, 96):
        md += [art, ""]
    tool = _link(ctx, b.get("tool", "Hammer"), page, found)
    md += [f"<b>{ui('buildings.kind')}</b> · {ui('buildings.built_with', tool=tool)}", ""]
    if b["description"]:
        md += [f"*{b['description']}*", ""]
    source = ctx.loc.vtext(_piece(ctx, b["source"]).get("name")) or b["source"]
    if b["id"] != WILD:
        md += [ui("buildings.copied_from", piece=source), ""]

    if b["id"] == WILD:
        md += _wild_section(ctx, b, page, found)
    else:
        md += [f"## {ui('buildings.cost')}", "", f"{ui('buildings.station')}: {_station_md(ctx, b, page)}", ""]
        md += _table(["", ui("items.material"), ui("buildings.amount")], [
            [_icon(ctx, r["item"], page, 32), _link(ctx, r["item"], page, found), str(r["amount"])]
            for r in cost(ctx, b)])

    if groups := unlocks.get(b.get("unlock")):
        craft = _craft_ctx(ctx)
        md += [f"## {ui('buildings.unlock')}", "", ui("buildings.unlock_note"), ""]
        md += [f"- [{g['options'][0]['title']}]({rel(option_path(craft, g), page)}) "
               f"<small>({ui('buildings.offered_by', n=len(g['nodes']))})</small>" for g in groups]
        md += [""]

    if b["id"] == "PT_AzuriteKiln":
        md += _kiln_section(ctx, b, page, found)
    elif b["id"] == "PT_RuneCarverTable":
        md += _crafted_here(ctx, b, page, found)
    elif b["id"] == "PT_VacuumBox":
        r0, r1, r2 = b["radius"]
        md += [f"## {ui('buildings.how_it_works')}", ""]
        md += [f"- {ui('buildings.vacuum_radius', min=_num(r0), max=_num(r2), default=_num(r1))}",
               f"- {ui('buildings.vacuum_every', s=_num(b['every']), n=b['feedPerTick'])}",
               f"- {ui('buildings.vacuum_categories', list=', '.join(b['categories']))}", ""]
    elif b["id"] == "PT_GoldlightGate":
        md += [f"## {ui('buildings.how_it_works')}", "", f"- {ui('buildings.gate_max', n=b['maxGates'])}", ""]
    return "\n".join(md + _footer(ctx))


def _num(v: float) -> str:
    return f"{v:g}"


def _kiln_section(ctx: Ctx, b: dict, page: str, found: dict) -> list[str]:
    ui = ctx.loc.ui
    smelter = ((ctx.loc.valheim or {}).get("smelters") or {}).get(b["source"]) or {}
    md = [f"## {ui('buildings.how_it_works')}", "", ui("buildings.kiln_note"), ""]
    md += _table(["", ui("buildings.input"), "", ui("buildings.output"), ui("buildings.amount")], [
        [_icon(ctx, c["from"], page, 32), _link(ctx, c["from"], page, found),
         _icon(ctx, c["to"], page, 32), _link(ctx, c["to"], page, found), f"×{c['yield']}"]
        for c in b["conversion"]])
    if smelter:
        fuel = _link(ctx, smelter["fuel"], page, found)
        md += [f"- {ui('buildings.kiln_fuel', fuel=fuel, n=smelter['fuelPerProduct'], max=smelter['maxFuel'])}",
               f"- {ui('buildings.kiln_time', s=_num(smelter['secPerProduct']), max=smelter['maxOre'])}", ""]
    return md


def _station_id(info: dict) -> str | None:
    station = ((info.get("mod") or {}).get("recipe") or {}).get("station")
    return station.get("id") if isinstance(station, dict) else station


def _crafted_here(ctx: Ctx, b: dict, page: str, found: dict) -> list[str]:
    ui, made = ctx.loc.ui, []
    made += [i for i, info in ctx.loc.loot["items"].items() if info.get("recipe")]  # runes (Runes.Recipes)
    made += [i for i, info in ctx.loc.items.items() if _station_id(info) == b["id"]]  # rings, belts...
    md = [f"## {ui('buildings.crafted_here')} ({len(made)})", ""]
    md += _table(["", ui("col.name")], [[_icon(ctx, i, page, 32), _link(ctx, i, page, found)] for i in made])
    return md


def _wild_section(ctx: Ctx, b: dict, page: str, found: dict) -> list[str]:
    ui, plants = ctx.loc.ui, wild_plants(ctx, b)
    md = [ui("buildings.wild_intro", sowing=rel(glossary_path("craft-wild-sowing"), page),
             cuttings=rel(glossary_path("craft-cuttings"), page)), ""]
    md += [f"## {ui('buildings.plants')} ({len(plants)})", ""]
    rows = []
    for p in plants:
        seed = b["seedNames"].get(p["seed"]) if p["seed"] else _item_name(ctx, p["item"])
        rows.append([_icon(ctx, p["item"], page, 32), _link(ctx, p["item"], page, found), seed,
                     ui("buildings.minutes", n=_num(p["minutes"]))])
    md += _table(["", ui("buildings.plant"), ui("buildings.planted_with"), ui("buildings.regrows")], rows)
    return md
