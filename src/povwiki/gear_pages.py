"""Currency, jewels and unique items.

- Currency: the mod's own items (Runes.All, rendered in the loot section): what each does, its
  recipe at the rune carver table, how it drops (LootCatalog.Currency: family, tier, weight,
  item level; boss loot tables) and what uses it. Essences also list the mods they can add
  (LootRoller.AddEssence: their element family up to their tier cap, or their boss family).
- Jewels: base jewels by type, with the mods each type rolls (catalog jewel.base.* pools); how
  often a drop is a jewel, by source (LootCatalog.Sources).
- Uniques: unique jewels and belts with their lines (harness/gear.py), radius and limit, and where
  they drop (LootCatalog.Uniques, boss loot tables, a jewel's own global weight).
"""

from collections import defaultdict

from .base_pages import _icon, _item_name, _mods_section, base_path, bases
from .item_pages import _title, biome, mod_path
from .markup import rel, to_md
from .pages import Ctx, _badge, _footer, _img, _table

CURRENCY_PAGE = "items/currency.md"
JEWELS_PAGE = "items/jewels.md"
UNIQUES_PAGE = "items/uniques.md"
# Currency groups, in page order: Runes.Kind.Cat, then what the mod leaves uncategorised.
_GROUPS = ("Rune", "Great", "Corrupted", "Essence", "Sigil", "Punch", "Material", "Trophy")


def currency_path(item: str) -> str:
    return f"items/currency/{item}.md"


def jewel_path(item: str) -> str:
    return f"items/jewel/{item}.md"


def unique_path(item: str) -> str:
    return f"items/unique/{item}.md"


def _pct(v: float) -> str:
    return f"{v * 100:.3g}%"


def _group(item: str, info: dict) -> str:
    cat = info.get("cat") or "None"
    if cat != "None":
        return cat
    if item.startswith("PT_EssenceOf"):
        return "Essence"
    return "Trophy" if info.get("trophy") else "Material"


def _recipe_parts(recipe: str | None) -> list[tuple[str, int]]:
    """Runes.Kind.Recipe: "Prefab:amount,Prefab:amount"."""
    parts = []
    for part in (recipe or "").split(","):
        if ":" in part:
            item, amount = part.split(":", 1)
            parts.append((item.strip(), int(amount)))
    return parts


def _link(ctx: Ctx, item: str, page: str, found: dict) -> str:
    """An item's name, linked to its page when it has one."""
    name = _item_name(ctx, item)
    if item in ctx.loc.loot["items"]:
        return f"[{name}]({rel(currency_path(item), page)})"
    if item in found:
        return f"[{name}]({rel(base_path(item), page)})"
    return name


def _used_in(ctx: Ctx) -> dict[str, list[str]]:
    """material -> items whose recipe uses it (currency, the mod's gear, Valheim's recipes)."""
    uses: dict[str, list[str]] = defaultdict(list)
    for item, info in ctx.loc.loot["items"].items():
        for material, _ in _recipe_parts(info.get("recipe")):
            uses[material].append(item)
    for item, info in ctx.loc.items.items():
        recipe = (info.get("mod") or {}).get("recipe")
        for res in (recipe or {}).get("resources") or []:
            uses[res["item"]].append(item)
    for r in (ctx.loc.valheim or {}).get("recipes", []):
        if r["enabled"]:
            for res in r["resources"]:
                if res["item"].startswith("PT_"):
                    uses[res["item"]].append(r["item"])
    return uses


def _tables_with(ctx: Ctx, item: str) -> list[list[str]]:
    """Boss loot tables (LootCatalog.Tables) that can drop this item: creature, chance, amount."""
    ui, rows = ctx.loc.ui, []
    for t in ctx.data.loot.get("tables") or []:
        for e in t["entries"]:
            if e["id"] != item:
                continue
            total = sum(x["weight"] for x in t["entries"]) or 1
            chance = t["chance"] * e["weight"] / total
            amount = f"{e.get('stackMin', 1)}–{e.get('stackMax', 1)}" if e.get("stackMax", 1) > e.get("stackMin", 1) else str(e.get("stackMin", 1))
            first = ui("gear.first_drop", n=_num(t["firstDrop"])) if t.get("firstDrop", 1) > 1 else ""
            for creature in t["creatures"]:
                rows.append([ctx.loc.creature(creature), _pct(chance), amount, first])
    return rows


def _num(v: float) -> str:
    return f"{v:g}"


def _drop_table(ctx: Ctx, rows: list[list[str]]) -> list[str]:
    ui = ctx.loc.ui
    return _table([ui("gear.creature"), ui("gear.chance"), ui("gear.amount"), ""], rows)


# ---- Currency -----------------------------------------------------------------------------------


def page_currency(ctx: Ctx) -> dict[str, str]:
    loot, gear, ui, page = ctx.loc.loot, ctx.loc.gear, ctx.loc.ui, CURRENCY_PAGE
    if not gear.get("currency"):
        return {}
    catalog = {c["id"]: c for c in ctx.data.loot.get("currency") or []}
    found = bases(ctx)
    groups: dict[str, list[str]] = defaultdict(list)
    for item, info in gear["currency"].items():
        if item in loot["items"]:
            groups[_group(item, info)].append(item)

    md = [f"# {ui('gear.currency')}", "", ui("gear.currency_intro"), ""]
    for g in _GROUPS:
        if g not in groups:
            continue
        md += [f"## {ui(f'gear.group.{g}')} ({len(groups[g])})", ""]
        rows = []
        for item in sorted(groups[g], key=lambda i: (-(catalog.get(i, {}).get("weight") or 0), _item_name(ctx, i))):
            info = loot["items"][item]
            rows.append([_icon(ctx, item, page, 40), f"[**{info['name']}**]({rel(currency_path(item), page)})",
                         to_md(info.get("action") or "", ctx.loc, page), _obtained(ctx, item, catalog)])
        md += _table(["", ui("col.name"), ui("col.effect"), ui("gear.obtained")], rows)
    pages = {page: "\n".join(md + _footer(ctx))}
    uses = _used_in(ctx)
    for item in (i for items in groups.values() for i in items):
        pages[currency_path(item)] = _currency_page(ctx, item, catalog, uses, found)
    return pages


def _obtained(ctx: Ctx, item: str, catalog: dict) -> str:
    ui, parts = ctx.loc.ui, []
    if ctx.loc.loot["items"][item].get("recipe"):
        parts.append(ui("gear.crafted"))
    if (c := catalog.get(item)) and c.get("weight", 0) > 0:
        level = max(1, c.get("minLevel") or 0)
        parts.append(ui("gear.drops_from", biome=biome(ctx, level)))
    bosses = sorted({ctx.loc.creature(cr) for t in ctx.data.loot.get("tables") or []
                     if any(e["id"] == item for e in t["entries"]) for cr in t["creatures"]})
    if bosses:
        parts.append(ui("gear.drops_bosses", bosses=", ".join(bosses)))
    return "; ".join(parts) or "—"


def _currency_page(ctx: Ctx, item: str, catalog: dict, uses: dict, found: dict) -> str:
    loc, ui, page = ctx.loc, ctx.loc.ui, currency_path(item)
    info = loc.loot["items"][item]
    md = [f"# {info['name']}", ""]
    if art := _icon(ctx, item, page, 96):
        md += [art, ""]
    md += [f"<b>{ui('gear.group.' + _group(item, loc.gear['currency'].get(item, {})))}</b>", ""]
    if info.get("action"):
        md += [to_md(info["action"], loc, page), ""]
    if info.get("flavor"):
        md += [f"*{info['flavor']}*".replace("\n", " "), ""]

    if parts := _recipe_parts(info.get("recipe")):
        from .building_pages import building_path

        table = f"[{loc.text('@piece.PT_RuneCarverTable.name', 'Rune Carver Table')}]({rel(building_path('PT_RuneCarverTable'), page)})"
        md += [f"## {ui('items.recipe')}", "", table, ""]
        md += _table(["", ui("items.material"), ui("items.craft")],
                     [[_icon(ctx, m, page, 32), _link(ctx, m, page, found), str(n)] for m, n in parts])

    md += _currency_drops(ctx, item, catalog)
    md += _essence_section(ctx, item, page)
    if used := sorted(set(uses.get(item, [])), key=lambda i: _item_name(ctx, i)):
        md += [f"## {ui('gear.used_in')}", ""]
        md += [", ".join(_link(ctx, u, page, found) for u in used), ""]
    md += buildings_section(ctx, item, page)
    return "\n".join(md + _footer(ctx))


def buildings_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """The mod's buildings an item goes into, and the kiln that grinds or makes it."""
    from .building_pages import building_link, used_to_build

    ui, md = ctx.loc.ui, []
    if built := used_to_build(ctx).get(item):
        md += [f"## {ui('buildings.used_to_build')}", "", ", ".join(building_link(ctx, b, page) for b in built), ""]
    for b in ctx.loc.buildings:
        for c in b.get("conversion") or []:
            if item in (c["from"], c["to"]):
                key = "buildings.ground_into" if item == c["from"] else "buildings.ground_from"
                other = c["to"] if item == c["from"] else c["from"]
                md += [ui(key, building=building_link(ctx, b, page), item=_link(ctx, other, page, {}), n=c["yield"]), ""]
    return md


def _currency_drops(ctx: Ctx, item: str, catalog: dict) -> list[str]:
    ui, md = ctx.loc.ui, []
    c = catalog.get(item)
    tables = _tables_with(ctx, item)
    if not (c and c.get("weight", 0) > 0) and not tables:
        return []
    md += [f"## {ui('gear.drops')}", ""]
    if c and c.get("weight", 0) > 0:
        family = [x for x in catalog.values() if x.get("family") == c.get("family") and x.get("weight", 0) > 0]
        level = max(1, c.get("minLevel") or 0)
        rows = [
            [ui("gear.family_label"), ui(f"gear.family.{c['family']}") if ui(f"gear.family.{c['family']}") != f"gear.family.{c['family']}" else c["family"]],
            [ui("items.tier"), str(c.get("tier", 1))],
            [ui("items.weight"), _num(c["weight"])],
            [ui("gear.family_share"), _pct(c["weight"] / sum(x["weight"] for x in family))],
            [ui("items.min_level"), f"{biome(ctx, level)} <small>({level})</small>"],
        ]
        if c.get("stackMax", 1) > 1:
            rows.append([ui("gear.amount"), f"{c.get('stackMin', 1)}–{c['stackMax']}"])
        if c.get("corrupted"):
            rows.append([ui("gear.corrupted_only"), ui("gear.corrupted_only_note")])
        md += [ui("gear.currency_drop_note"), ""] + _table([ui("col.property"), ui("col.value")], rows)
    if tables:
        md += [ui("gear.boss_tables"), ""] + _drop_table(ctx, tables)
    return md


def _essence_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """The mods an essence can add (LootRoller.AddEssence): rolling mods of its element family at
    tier cap or worse (T3 = cap 3), and every mod of its boss family."""
    e = ctx.loc.loot["essences"].get(item)
    if not e:
        return []
    ui, md = ctx.loc.ui, []

    def tier_ok(t: dict) -> bool:
        n = int(t["id"][1:]) if t["id"][1:].isdigit() else 1
        return not t["special"] and n >= e["cap"]

    element = [a for a in ctx.loc.loot["affixes"] if a["generation"] and e["family"] in a["families"]
               and any(tier_ok(t) for t in a["tiers"])]
    boss = [a for a in ctx.loc.loot["affixes"] if e.get("boss") and e["boss"] in a["families"]]
    md += [f"## {ui('gear.essence_mods')}", "", ui("gear.essence_note", cap=e["cap"]), ""]
    for title, chosen in ((ui("gear.essence_boss_mods"), boss), (ui("gear.essence_element_mods", n=len(element)), element)):
        if chosen:
            md += [f"### {title}", ""]
            md += [", ".join(f"[{_title(a)}]({rel(mod_path(a), page)})" for a in sorted(chosen, key=_title)), ""]
    return md


# ---- Jewels -------------------------------------------------------------------------------------


def _jewel_icon(ctx: Ctx, jewel: dict, page: str, px: int) -> str:
    return _img(ctx.icons.path(jewel["icon"]), page, px) if ctx.icons else ""


def page_jewels(ctx: Ctx) -> dict[str, str]:
    jewels, ui, page = ctx.loc.gear.get("jewels") or {}, ctx.loc.ui, JEWELS_PAGE
    if not jewels:
        return {}
    md = [f"# {ui('gear.jewels')}", "", ui("gear.jewels_intro"), ""]
    sources = ctx.data.loot.get("sources") or []
    if sources:
        md += [f"### {ui('gear.jewel_chance')}", "", ui("gear.jewel_chance_note"), ""]
        md += _table([ui("gear.source_label"), ui("gear.chance")], [
            [ui(f"gear.source.{s['id']}") if ui(f"gear.source.{s['id']}") != f"gear.source.{s['id']}" else s["id"],
             _pct(s.get("jewel", 0) / (s.get("gear", 0) + s.get("currency", 0) + s.get("jewel", 0)))]
            for s in sources])

    base = {k: j for k, j in jewels.items() if j["base"]}
    md += [f"## {ui('gear.base_jewels')} ({len(base)})", ""]
    rows, pages = [], {}
    for k, j in sorted(base.items(), key=lambda kv: (len(kv[1]["base"]), kv[1]["base"])):
        tags = {"jewel", f"jewel.{j['base']}"}
        count = sum(1 for a in ctx.loc.loot["affixes"] if a["generation"] and _fits_tags(a, tags))
        rows.append([_jewel_icon(ctx, j, page, 40), f"[**{j['name']}**]({rel(jewel_path(k), page)})",
                     ui(f"tag.jewel.{j['base']}"), str(count)])
        pages[jewel_path(k)] = _jewel_page(ctx, k, j)
    md += _table(["", ui("col.name"), ui("col.type"), ui("items.mods")], rows)

    uniques = {k: j for k, j in jewels.items() if k in ctx.loc.gear.get("uniques", {})}
    md += [f"## {ui('gear.unique_jewels')} ({len(uniques)})", ""]
    md += _table(["", ui("col.name"), ui("gear.radius"), ui("gear.limit")], [
        [_jewel_icon(ctx, j, page, 40), f"[**{j['name']}**]({rel(unique_path(k), page)})", j["radius"] or "—",
         str(j["limit"]) if j["limit"] else "—"]
        for k, j in sorted(uniques.items(), key=lambda kv: kv[1]["name"])])

    unused = {k: j for k, j in jewels.items() if j["placeholder"]}
    if unused:
        md += [f"## {ui('page.unimplemented')} ({len(unused)})", "", ui("gear.placeholder_jewels"), ""]
        md += [", ".join(f"{_jewel_icon(ctx, j, page, 32)} {j['name']}" for j in unused.values()), ""]
    pages[page] = "\n".join(md + _footer(ctx))
    return pages


def _fits_tags(affix: dict, tags: set[str]) -> bool:
    from .base_pages import _fits

    return _fits(affix, tags)


def _jewel_page(ctx: Ctx, item: str, j: dict) -> str:
    ui, page = ctx.loc.ui, jewel_path(item)
    md = [f"# {j['name']}", ""]
    if art := _jewel_icon(ctx, j, page, 96):
        md += [art, ""]
    kind = ui(f"tag.jewel.{j['base']}")
    md += [f"<b>{kind}</b>", "", ui("gear.base_jewel_note"), ""]
    md += _mods_section(ctx, {"info": {"tags": ["jewel", f"jewel.{j['base']}"]}}, page)
    return "\n".join(md + _footer(ctx))


# ---- Uniques ------------------------------------------------------------------------------------


def page_uniques(ctx: Ctx) -> dict[str, str]:
    gear, ui, page = ctx.loc.gear, ctx.loc.ui, UNIQUES_PAGE
    uniques = gear.get("uniques") or {}
    if not uniques:
        return {}
    catalog = {u["id"]: u for u in ctx.data.loot.get("uniques") or []}
    md = [f"# {ui('gear.uniques')}", "", ui("gear.uniques_intro"), ""]
    rows, pages = [], {}
    for item in sorted(uniques, key=lambda i: _unique_name(ctx, i)):
        rows.append([_unique_icon(ctx, item, page, 40), f"[**{_unique_name(ctx, item)}**]({rel(unique_path(item), page)})",
                     _unique_kind(ctx, item), _unique_sources(ctx, item, catalog)])
        pages[unique_path(item)] = _unique_page(ctx, item, catalog)
    md += _table(["", ui("col.name"), ui("col.type"), ui("gear.obtained")], rows)
    pages[page] = "\n".join(md + _footer(ctx))
    return pages


def _unique_name(ctx: Ctx, item: str) -> str:
    j = ctx.loc.gear.get("jewels", {}).get(item)
    return j["name"] if j else _item_name(ctx, item)


def _unique_icon(ctx: Ctx, item: str, page: str, px: int) -> str:
    j = ctx.loc.gear.get("jewels", {}).get(item)
    return _jewel_icon(ctx, j, page, px) if j else _icon(ctx, item, page, px)


def _unique_kind(ctx: Ctx, item: str) -> str:
    if item in ctx.loc.gear.get("jewels", {}):
        return ctx.loc.ui("tag.jewel").capitalize()
    tags = ctx.loc.items.get(item, {}).get("tags") or []
    return ctx.loc.ui("tag.belt").capitalize() if "belt" in tags else "—"


def _unique_sources(ctx: Ctx, item: str, catalog: dict) -> str:
    """Where a unique drops, in words: catalog sources, a jewel's own global weight, boss tables."""
    ui, parts = ctx.loc.ui, []
    entry = catalog.get(item)
    j = ctx.loc.gear.get("jewels", {}).get(item) or {}
    mod = ctx.loc.items.get(item, {}).get("mod") or {}
    if entry and entry.get("weight", 0) > 0:
        level = max(1, entry.get("minLevel") or 0)
        for s in entry.get("sources") or ["global"]:
            kind, _, what = s.partition(":")
            if kind == "global":
                parts.append(ui("gear.src_global", biome=biome(ctx, level), level=level))
            elif kind == "biome":
                parts.append(ui("gear.src_biome", biome=ctx.loc.vkey(f"biome_{what.lower()}", what)))
            elif kind == "creature":
                parts.append(ui("gear.src_creature", creature=ctx.loc.creature(what)))
    elif j.get("globalWeight") or mod.get("globalMinLevel"):
        level = max(1, j.get("globalMinLevel") or mod.get("globalMinLevel") or 0)
        parts.append(ui("gear.src_global", biome=biome(ctx, level), level=level))
    bosses = sorted({ctx.loc.creature(cr) for t in ctx.data.loot.get("tables") or []
                     if any(e["id"] == item for e in t["entries"]) for cr in t["creatures"]})
    if bosses:
        parts.append(ui("gear.drops_bosses", bosses=", ".join(bosses)))
    return "; ".join(parts) or _badge(ui("badge.broken"), ui("gear.no_source"))


def _line_md(ctx: Ctx, line: dict, page: str) -> list[str]:
    """One unique line as Markdown list items (alternatives nested under it)."""
    ui, loc = ctx.loc.ui, ctx.loc
    count = f"{line['count']} × " if line.get("count", 1) > 1 else ""
    if "oneOf" in line:
        total = sum(o["weight"] for o in line["oneOf"]) or 1
        out = [f"- {ui('gear.one_of')}"]
        for o in line["oneOf"]:
            out += ["    " + s for s in _line_md(ctx, o, page)]
            out[-1] += f" <small>({_pct(o['weight'] / total)})</small>"
        return out
    if "pool" in line:
        total = sum(p["weight"] for p in line["pool"]) or 1
        head = ui("gear.pool_distinct" if line.get("distinct") and line.get("count", 1) > 1 else "gear.pool")
        if len(line["pool"]) == 1:
            return [f"- {count}{to_md(line['pool'][0]['text'], loc, page)}"]
        out = [f"- {count}{head}"]
        out += [f"    - {to_md(p['text'], loc, page)} <small>({_pct(p['weight'] / total)})</small>" for p in line["pool"]]
        return out
    if "template" in line:
        pick = ui(f"gear.pick.{line.get('pick')}")
        note = ui("gear.pick_distinct") if line.get("count", 1) > 1 and line.get("distinct") else ""
        return [f"- {count}{to_md(line['template'].replace('{0}', f'<i>{pick}</i>'), loc, page)}" + (f" <small>({note})</small>" if note else "")]
    return [f"- {count}{to_md(line['text'], loc, page)}"]


def _unique_page(ctx: Ctx, item: str, catalog: dict) -> str:
    ui, page = ctx.loc.ui, unique_path(item)
    j = ctx.loc.gear.get("jewels", {}).get(item)
    md = [f"# {_unique_name(ctx, item)}", ""]
    if art := _unique_icon(ctx, item, page, 96):
        md += [art, ""]
    md += [f"<b>{ui('gear.unique')} {_unique_kind(ctx, item).lower()}</b>", ""]
    facts = []
    if j and j.get("radiusLine"):
        facts.append(j["radiusLine"])
    if j and j.get("limit"):
        facts.append(f"{ui('gear.limit')}: {j['limit']}")
    if facts:
        md += [" · ".join(facts), ""]
    md += [f"## {ui('gear.lines')}", ""]
    for line in ctx.loc.gear["uniques"][item]["lines"]:
        md += _line_md(ctx, line, page)
    md += [""]
    flavor = j["flavor"] if j else (ctx.loc.items.get(item, {}).get("mod") or {}).get("shared", {}).get("m_description", "")
    if flavor:
        md += [f"*{flavor}*".replace("\n", " "), ""]
    sources = _unique_sources(ctx, item, catalog)
    md += [f"## {ui('gear.drops')}", "", sources[:1].upper() + sources[1:] + ".", ""]
    if tables := _tables_with(ctx, item):
        md += [ui("gear.boss_tables"), ""] + _drop_table(ctx, tables)
    if item in ctx.loc.items and (ctx.loc.items[item].get("mod") or {}).get("kind"):
        md += [ui("gear.see_base", link=f"[{_unique_name(ctx, item)}]({rel(base_path(item), page)})"), ""]
    return "\n".join(md + _footer(ctx))


# ---- Keyword references (for glossary pages) ----------------------------------------------------


def _texts(lines: list[dict]):
    for line in lines:
        yield from (t for t in (line.get("text"), line.get("template")) if t)
        yield from (p["text"] for p in line.get("pool") or [])
        yield from _texts(line.get("oneOf") or [])


def uniques_by_keyword(ctx: Ctx) -> dict[str, list[str]]:
    """keyword slug -> unique items whose lines link it."""
    from .markup import slugs

    found: dict[str, list[str]] = defaultdict(list)
    for item, u in (ctx.loc.gear.get("uniques") or {}).items():
        for slug in {s for t in _texts(u["lines"]) for s in slugs(t)}:
            found[slug].append(item)
    return found


def keyword_uniques_section(ctx: Ctx, items: list[str], page: str) -> list[str]:
    links = sorted((_unique_name(ctx, i), unique_path(i)) for i in items)
    return [f"#### {ctx.loc.ui('gear.uniques')} ({len(items)})", "",
            ", ".join(f"[{name}]({rel(path, page)})" for name, path in links), ""]
