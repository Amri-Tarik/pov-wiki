"""Currency, jewels and unique items.

- Currency: the mod's own items (Runes.All, rendered in the loot section): what each does, its
  recipe at the rune carver table, how it drops (LootCatalog.Currency: family, tier, weight,
  item level; boss loot tables) and what uses it. Essences also list the mods they can add
  (LootRoller.AddEssence: their element family up to their tier cap, or their boss family).
- Jewels: base jewels by type, with the mods each type rolls (catalog jewel.base.* pools); how
  often a drop is a jewel, by source (LootCatalog.Sources).
- Uniques: unique jewels and belts with their lines (harness/gear.py), radius and limit, and where
  they drop (LootCatalog.Uniques, boss and chest loot tables, a jewel's own global weight). Unique
  equipment (UniqueGear, 6.0) adds its base: the donor item, item level, defence, stats and implicit.
"""

from collections import defaultdict

from .base_pages import _icon, _item_name, _mods_section, base_path, bases
from .item_pages import _title, biome, mod_path
from .markup import rel, to_md
from .pages import Ctx, _badge, _footer, _img, _table

CURRENCY_PAGE = "items/currency.md"
JEWELS_PAGE = "items/jewels.md"
UNIQUES_PAGE = "items/uniques.md"
# Currency groups, in page order: Runes.Kind.Cat, then what the mod leaves uncategorised. Each has
# its own page (found first when searching for the kind: its title is the kind's name).
_GROUPS = ("Rune", "Great", "Corrupted", "Essence", "Sigil", "Punch", "Material", "Trophy")
GROUP_SLUGS = {"Rune": "runes", "Great": "great-runes", "Corrupted": "corrupted-runes", "Essence": "essences",
               "Sigil": "sigils", "Punch": "punches", "Material": "materials", "Trophy": "trophies"}


def group_path(group: str) -> str:
    return f"items/{GROUP_SLUGS[group]}.md"


def currency_path(item: str) -> str:
    return f"items/currency/{item}.md"


def jewel_path(item: str) -> str:
    return f"items/jewel/{item}.md"


def unique_path(item: str) -> str:
    return f"items/unique/{item}.md"


def _one_in(ctx: Ctx, v: float) -> str:
    """An expected count per kill, as "1 in N" when it is below one."""
    if 0 < v < 1:
        return ctx.loc.ui("gear.one_in", n=f"{round(1 / v):,}".replace(",", ctx.loc.ui("gear.thousands")))
    return f"{v:.2g}" if v else "—"


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


def _tables_with(ctx: Ctx, item: str, page: str) -> list[list[str]]:
    """Boss loot tables (LootCatalog.Tables) that can drop this item: creature, chance, amount."""
    from .monster_pages import creature_link

    ui, rows = ctx.loc.ui, []
    for t in ctx.data.loot.get("tables") or []:
        for e in t["entries"]:
            if e["id"] != item:
                continue
            total = sum(x["weight"] for x in t["entries"]) or 1
            chance = t["chance"] * e["weight"] / total
            amount = f"{e.get('stackMin', 1)}–{e.get('stackMax', 1)}" if e.get("stackMax", 1) > e.get("stackMin", 1) else str(e.get("stackMin", 1))
            first = ui("gear.first_drop", n=_num(t["firstDrop"])) if t.get("firstDrop", 1) > 1 else ""
            for creature in t.get("creatures") or []:
                rows.append([creature_link(ctx, creature, page), _pct(chance), amount, first])
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
    pages = {}
    for g in (g for g in _GROUPS if g in groups):
        md += [f"## [{ui(f'gear.group.{g}')}]({rel(group_path(g), page)}) ({len(groups[g])})", ""]
        md += _group_table(ctx, groups[g], catalog, page)
        pages[group_path(g)] = _group_page(ctx, g, groups[g], catalog)
    pages[page] = "\n".join(md + _footer(ctx))
    uses = _used_in(ctx)
    for item in (i for items in groups.values() for i in items):
        pages[currency_path(item)] = _currency_page(ctx, item, catalog, uses, found)
    return pages


def _group_table(ctx: Ctx, items: list[str], catalog: dict, page: str) -> list[str]:
    """A currency group's items: name, what it does (a sigil: in each kind of item), how to get it."""
    loot, ui, rows = ctx.loc.loot, ctx.loc.ui, []
    for item in sorted(items, key=lambda i: (-(catalog.get(i, {}).get("weight") or 0), _item_name(ctx, i))):
        info = loot["items"][item]
        effect = "<br>".join(_sigil_lines(ctx, item, page)) or to_md(info.get("action") or "", ctx.loc, page)
        rows.append([_icon(ctx, item, page, 40), f"[**{info['name']}**]({rel(currency_path(item), page)})",
                     effect, _obtained(ctx, item, catalog, page)])
    return _table(["", ui("col.name"), ui("col.effect"), ui("gear.obtained")], rows)


def _group_page(ctx: Ctx, group: str, items: list[str], catalog: dict) -> str:
    ui, page = ctx.loc.ui, group_path(group)
    md = [f"# {ui(f'gear.group.{group}')}", ""]
    intro = ui(f"gear.group_intro.{group}")
    md += [intro if intro != f"gear.group_intro.{group}" else ui("gear.currency_intro"), ""]
    if group == "Sigil" and (note := _divine_socket(ctx, page)):
        md += [f'!!! tip "{ui("gear.divine_socket")}"', f"    {note}", ""]
    md += _group_table(ctx, items, catalog, page)
    md += [ui("gear.all_currency", link=rel(CURRENCY_PAGE, page)), ""]
    return "\n".join(md + _footer(ctx))


def _divine_socket(ctx: Ctx, page: str) -> str:
    """The Divine Punch and what its socket does to a sigil, in its own words."""
    punch = ctx.loc.loot["items"].get("PT_DivinePunch")
    if not punch or not punch.get("action"):
        return ""
    return f"[{punch['name']}]({rel(currency_path('PT_DivinePunch'), page)}): {to_md(punch['action'], ctx.loc, page)}"


# Sigils whose effect is about a keyword its text doesn't link (both pages link each other).
SIGIL_KEYWORDS = {"PT_SigilAshenCrown": ("aura",)}


def _sigil_lines(ctx: Ctx, item: str, page: str) -> list[str]:
    """A sigil's effect in each kind of item it works in, as its tooltip lists them; a line that
    allocates a passive links it. A sigil with no line yet says so, in the game's words."""
    from .pages import _badge, _name

    gear = ctx.loc.gear
    sigil = gear.get("currency", {}).get(item, {}).get("sigil")
    if sigil is None:
        return []
    if not sigil:
        none = gear.get("sigilNoEffect", "")
        return [f"{_badge(ctx.loc.ui('badge.broken'), none)} {none}"]
    out = []
    for line in sigil:
        text = line["text"]
        if line.get("node") and (n := ctx.by_id.get(line["node"])):
            text = text.replace(line["node"], _name(ctx, n, page))
        out.append(f"**{line['slots']}:** {text}")
    return out


def _obtained(ctx: Ctx, item: str, catalog: dict, page: str = CURRENCY_PAGE) -> str:
    ui, parts = ctx.loc.ui, []
    if ctx.loc.loot["items"][item].get("recipe"):
        parts.append(ui("gear.crafted"))
    if (c := catalog.get(item)) and c.get("weight", 0) > 0:
        level = max(1, c.get("minLevel") or 0)
        parts.append(ui("gear.drops_from", biome=biome(ctx, level)))
    from .monster_pages import creature_link

    bosses = sorted({cr for t in ctx.data.loot.get("tables") or []
                     if any(e["id"] == item for e in t["entries"]) for cr in t.get("creatures") or []}, key=ctx.loc.creature)
    if bosses:
        parts.append(ui("gear.drops_bosses", bosses=", ".join(creature_link(ctx, cr, page) for cr in bosses)))
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

    if lines := _sigil_lines(ctx, item, page):
        md += [f"## {ui('page.effect')}", "", "<br>".join(lines), ""]
        if ctx.loc.gear["currency"][item]["sigil"] and (note := _divine_socket(ctx, page)):
            md += [note, ""]
    if item in SIGIL_KEYWORDS:
        from .pages import _keywords_section

        md += _keywords_section(ctx, page, [], [], SIGIL_KEYWORDS[item])
    from .gem_pages import sigil_gems_section

    md += sigil_gems_section(ctx, item, page)
    md += _mining_section(ctx, item, page, found)
    md += _made_section(ctx, item, page, found)
    md += _currency_drops(ctx, item, catalog)
    md += _essence_section(ctx, item, page)
    md += _ascension_line(ctx, item, page)
    md += _dismantling_line(ctx, item, page)
    from .enchant_pages import enchant_section

    md += enchant_section(ctx, item, page)
    from .halls_pages import currency_section

    md += currency_section(ctx, item, page)  # map runes, the merchant's rune, unique rooms' rewards
    used = sorted(set(uses.get(item, [])), key=lambda i: _item_name(ctx, i))
    ground = _ground_into(ctx, item, page, found)
    if used or ground:
        md += [f"## {ui('gear.used_in')}", ""]
        md += [", ".join([_link(ctx, u, page, found) for u in used] + ground), ""]
    md += buildings_section(ctx, item, page)
    from .monster_pages import summons_section

    md += summons_section(ctx, item, page)
    from .world_pages import renewal_section

    md += renewal_section(ctx, item, page)  # the Rune of Renewed Trade: the merchants it renews
    from .patch_pages import history

    md += history(ctx, "currency", [item], page)
    return "\n".join(md + _footer(ctx))


def buildings_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """The mod's buildings an item goes into."""
    from .building_pages import building_link, used_to_build

    if built := used_to_build(ctx).get(item):
        return [f"## {ctx.loc.ui('buildings.used_to_build')}", "", ", ".join(building_link(ctx, b, page) for b in built), ""]
    return []


def _chisels_for(ctx: Ctx, kind: int) -> list[str]:
    veins = ctx.loc.veins
    return [c["id"] for c in veins["chisels"] if c["tier"] >= veins["needTier"][kind]]


def _mining_section(ctx: Ctx, item: str, page: str, found: dict) -> list[str]:
    """Where an azurite ore is mined (harness render_veins): its vein kind, biomes and chisel."""
    from .monster_pages import CREATURES_PAGE

    veins, ui = ctx.loc.veins, ctx.loc.ui
    if item not in veins.get("ores", []):
        return []
    kind, names = veins["ores"].index(item), lambda bs: ", ".join(ctx.loc.vkey(f"biome_{b.lower()}", b) for b in bs)
    md = [f"## {ui('veins.mining')}", ""]
    if kind == 0:
        md += [ui("veins.plain", biomes=names(veins["plainBiomes"]), dense=names([veins["denseBiome"]])), ""]
    elif kind == 1:
        md += [ui("veins.corrupted", link=rel(CREATURES_PAGE, page) + "#blight"), ""]
    else:
        from .formula_pages import shown

        if not shown(ctx, "azurite-veins"):
            return md + [f'!!! warning "{ui("formula.rechecking_title")}"',
                         f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
        s, chances = veins["strike"], veins["strikeChance"]
        by_chance: dict[float, list[str]] = {}
        for b, c in chances.items():
            if c > 0:
                by_chance.setdefault(round(c, 4), []).append(b)
        first = next(b for b, c in chances.items() if c > 0)
        parts = "; ".join(f"{names(bs)}: {_pct(c)}" for c, bs in sorted(by_chance.items()))
        md += [ui("veins.divine", first=names([first]), reach=s["reach"], chances=parts,
                  pity=names(veins["pityBiomes"]), misses=s["pity"] - 1), ""]
        if touch := _divine_touch(ctx, page):
            md += [ui("veins.divine_touch", mastery=touch), ""]
    chisels = " / ".join(_link(ctx, c, page, found) for c in _chisels_for(ctx, kind))
    md += [ui("veins.chisel", chisels=chisels), ""]
    if veins["hardness"][kind] != 1:
        md += [ui("veins.hardness", x=f"{veins['hardness'][kind]:g}"), ""]
    return md


def _divine_touch(ctx: Ctx, page: str) -> str | None:
    """The craft mastery that turns plain veins divine while you cut them, linked."""
    from .building_pages import _craft_ctx
    from .pages import option_path

    craft, name = _craft_ctx(ctx), ctx.loc.veins.get("divineTouch")
    for g in (craft.option_groups.values() if craft else []):
        if any(o["raw"].get("name") == name for o in g["options"]):
            return f"[{g['options'][0]['title']}]({rel(option_path(craft, g), page)})"
    return None


def chisel_section(ctx: Ctx, prefab: str, page: str) -> list[str]:
    """On a rune chisel's page: the azurite veins it can cut."""
    veins = ctx.loc.veins
    chisel = next((c for c in veins.get("chisels", []) if c["id"] == prefab), None)
    if chisel is None:
        return []
    ores = [o for kind, o in enumerate(veins["ores"]) if chisel["tier"] >= veins["needTier"][kind]]
    md = [f"## {ctx.loc.ui('veins.cuts')}", "", ", ".join(_link(ctx, o, page, {}) for o in ores), ""]
    return md + _quarrying(ctx, page)


def _quarrying(ctx: Ctx, page: str) -> list[str]:
    """The craft mastery that lets rune chisels mine like pickaxes (5.1.2: flag "Quarrying"), linked,
    with its own text."""
    from .building_pages import _craft_ctx
    from .pages import option_path

    craft = _craft_ctx(ctx)
    for g in (craft.option_groups.values() if craft else []):
        o = g["options"][0]
        if o.get("flag") == "Quarrying":
            text = " ".join(to_md(s, ctx.loc, page) for s in o["stats"] + o["extra"])
            return [ctx.loc.ui("veins.quarrying", mastery=f"[{o['title']}]({rel(option_path(craft, g), page)})", text=text), ""]
    return []


def _made_section(ctx: Ctx, item: str, page: str, found: dict) -> list[str]:
    """How an item is made: its recipe at the rune carver table, or the kiln that grinds it."""
    from .building_pages import building_link, building_path

    loc, ui, md = ctx.loc, ctx.loc.ui, []
    if parts := _recipe_parts(loc.loot["items"][item].get("recipe")):
        table = f"[{loc.text('@piece.PT_RuneCarverTable.name', 'Rune Carver Table')}]({rel(building_path('PT_RuneCarverTable'), page)})"
        md += [f"{ui('items.station')}: {table}", ""]
        md += _table(["", ui("items.material"), ui("items.craft")],
                     [[_icon(ctx, m, page, 32), _link(ctx, m, page, found), str(n)] for m, n in parts])
    for b in loc.buildings:
        for c in b.get("conversion") or []:
            if c["to"] == item:
                md += [f"{ui('items.station')}: {building_link(ctx, b, page)}", ""]
                md += _table(["", ui("items.material"), ui("buildings.amount"), ui("buildings.gives")],
                             [[_icon(ctx, c["from"], page, 32), _link(ctx, c["from"], page, found), "1", f"×{c['yield']}"]])
    return [f"## {ui('items.how_made')}", ""] + md if md else []


def _ground_into(ctx: Ctx, item: str, page: str, found: dict) -> list[str]:
    """What the kiln grinds an item into, for its "Used to make" list."""
    from .building_pages import display_name

    return [f"{_link(ctx, c['to'], page, found)} <small>({display_name(ctx, b)}, ×{c['yield']})</small>"
            for b in ctx.loc.buildings for c in b.get("conversion") or [] if c["from"] == item]


def _currency_drops(ctx: Ctx, item: str, catalog: dict) -> list[str]:
    ui, md = ctx.loc.ui, []
    c = catalog.get(item)
    tables = _tables_with(ctx, item, currency_path(item))
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


def _dismantling_line(ctx: Ctx, item: str, page: str) -> list[str]:
    """Azurite and divine dust: dismantling items gives them (Disenchant.Returns)."""
    from .formula_pages import _anchor, shown

    if item not in ("PT_AzuriteDust", "PT_DivineAzuriteDust", "PT_CorruptedAzuriteDust") or not shown(ctx, "dismantling"):
        return []
    ui = ctx.loc.ui
    key = "corrupted_link" if item == "PT_CorruptedAzuriteDust" else "dust_link"  # Disenchant.Returns, 6.0
    return [ui(f"formula.dismantling.{key}", title=ui("formula.dismantling.title"), link=_anchor("dismantling", page)), ""]


def _ascension_line(ctx: Ctx, item: str, page: str) -> list[str]:
    """A Lord's Brand's ascension (ItemAscension.Targets; boss essences in 5.3), linked to how it works."""
    from .formula_pages import _anchor, shown

    b = (ctx.loc.loot.get("ascension") or {}).get(item)
    if not b or not shown(ctx, "ascension"):
        return []
    ui = ctx.loc.ui
    return [ui("formula.ascension.brand_link", biome=ctx.loc.vkey(f"biome_{b['biome'].lower()}", b["biome"]), level=b["level"],
               title=ui("formula.ascension.title"), link=_anchor("ascension", page)), ""]


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
    from .formula_pages import loot_per_kill, shown

    sources = ctx.data.loot.get("sources") or []
    if sources and shown(ctx, "loot"):
        md += [f"### {ui('gear.jewel_chance')}", "", ui("gear.jewel_chance_note"), ""]
        md += _table([ui("gear.source_label"), ui("gear.jewels_per_kill")], [
            [ui(f"gear.source.{s['id']}") if ui(f"gear.source.{s['id']}") != f"gear.source.{s['id']}" else s["id"],
             _one_in(ctx, loot_per_kill(ctx, s)["gems"])] for s in sources])

    base = {k: j for k, j in jewels.items() if j["base"]}
    md += [f"## {ui('gear.base_jewels')} ({len(base)})", ""]
    rows, pages = [], {}
    implicit = any(j.get("implicits") for j in base.values())
    for k, j in sorted(base.items(), key=lambda kv: (len(kv[1]["base"]), kv[1]["base"])):
        tags = {"jewel", f"jewel.{j['base']}"}
        count = sum(1 for a in ctx.loc.loot["affixes"] if a["generation"] and _fits_tags(a, tags))
        row = [_jewel_icon(ctx, j, page, 40), f"[**{j['name']}**]({rel(jewel_path(k), page)})",
               ui(f"tag.jewel.{j['base']}")]
        if implicit:
            row.append("<br>".join(i["text"] for i in j.get("implicits") or []) or "—")
        rows.append(row + [str(count)])
        pages[jewel_path(k)] = _jewel_page(ctx, k, j)
    md += _table(["", ui("col.name"), ui("col.type")] + ([ui("items.implicits")] if implicit else []) + [ui("items.mods")], rows)

    uniques = {k: j for k, j in jewels.items() if k in ctx.loc.gear.get("uniques", {})}
    md += [f"## {ui('gear.unique_jewels')} ({len(uniques)})", ""]
    md += _table(["", ui("col.name"), ui("gear.radius"), ui("gear.limit")], [
        [_jewel_icon(ctx, j, page, 40), f"[**{j['name']}**]({rel(unique_path(k), page)})", j["radius"] or "—",
         str(j["limit"]) if j["limit"] else "—"]
        for k, j in sorted(uniques.items(), key=lambda kv: kv[1]["name"])])

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
    if implicits := j.get("implicits"):
        md += [f"## {ui('items.implicits')}", "", ui("gear.jewel_implicits_note"), ""]
        md += [f"- {i['text']}" for i in implicits] + [""]
    md += _mods_section(ctx, {"info": {"tags": ["jewel", f"jewel.{j['base']}"]}}, page)
    return "\n".join(md + _footer(ctx))


# ---- Uniques ------------------------------------------------------------------------------------


def page_uniques(ctx: Ctx) -> dict[str, str]:
    """Unique items by kind (jewels, belts...), each with its icon, its lines in short and where it
    drops; one page per unique with its lines in full."""
    gear, ui, page = ctx.loc.gear, ctx.loc.ui, UNIQUES_PAGE
    uniques = gear.get("uniques") or {}
    if not uniques:
        return {}
    catalog = {u["id"]: u for u in ctx.data.loot.get("uniques") or []}
    md = [f"# {ui('gear.uniques')}", "", ui("gear.uniques_intro"), ""]
    kinds: dict[str, list[str]] = defaultdict(list)
    for item in sorted(uniques, key=lambda i: _unique_name(ctx, i)):
        kinds[ui(f"class.{_unique_class(ctx, item)}")].append(item)
    pages = {}
    for kind, items in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        md += [f"## {kind} ({len(items)})", ""] + unique_table(ctx, items, page, catalog)
        pages.update({unique_path(item): _unique_page(ctx, item, catalog) for item in items})
    pages[page] = "\n".join(md + _footer(ctx))
    return pages


# UniqueGear.Def.Kind -> the class it is listed under on the uniques page.
_GEAR_CLASS = {"helmet": "armour", "chest": "armour", "legs": "armour", "cape": "armour", "shield": "shields",
               "ring": "rings", "belt": "belts", "quiver": "quivers", "tool": "tools"}


def _gear(ctx: Ctx, item: str) -> dict | None:
    """A unique equipment item (UniqueGear, 6.0), as harness/gear.py renders it."""
    return (ctx.loc.gear.get("uniqueGear") or {}).get(item)


def gear_owners(ctx: Ctx) -> dict[str, list[str]]:
    """unique.* affix id -> the unique equipment items with a row of it (UniqueGear.Def.Rows, at their tier U-<key>)."""
    out: dict[str, list[str]] = defaultdict(list)
    for item, g in (ctx.loc.gear.get("uniqueGear") or {}).items():
        for line in g["lines"]:
            out[line["affix"]].append(item)
    return out


def unique_links(ctx: Ctx, items: list[str], page: str) -> str:
    """Uniques by name, linked to their pages."""
    return ", ".join(f"[{_unique_name(ctx, i)}]({rel(unique_path(i), page)})" for i in sorted(items, key=lambda i: _unique_name(ctx, i)))


def _unique_class(ctx: Ctx, item: str) -> str:
    if item in ctx.loc.gear.get("jewels", {}):
        return "jewels"
    if g := _gear(ctx, item):
        return _GEAR_CLASS.get(g["kind"], "weapons")
    return "belts" if "belt" in (ctx.loc.items.get(item, {}).get("tags") or []) else "utility"


def _unique_name(ctx: Ctx, item: str) -> str:
    j = ctx.loc.gear.get("jewels", {}).get(item) or _gear(ctx, item)
    return j["name"] if j else _item_name(ctx, item)


def _unique_icon(ctx: Ctx, item: str, page: str, px: int) -> str:
    j = ctx.loc.gear.get("jewels", {}).get(item)
    return _jewel_icon(ctx, j, page, px) if j else _icon(ctx, item, page, px)


def _unique_kind(ctx: Ctx, item: str) -> str:
    if g := _gear(ctx, item):
        return ctx.loc.ui(f"uniques.kind.{g['kind']}")
    if item in ctx.loc.gear.get("jewels", {}):
        return ctx.loc.ui("tag.jewel").capitalize()
    tags = ctx.loc.items.get(item, {}).get("tags") or []
    return ctx.loc.ui("tag.belt").capitalize() if "belt" in tags else "—"


def _unique_sources(ctx: Ctx, item: str, catalog: dict, page: str) -> str:
    """Where a unique drops, in words: catalog sources, a jewel's own global weight, boss and chest tables."""
    from .monster_pages import CREATURES_PAGE, creature_link

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
            elif kind == "monolith":
                chance = ctx.loc.gear.get("monolithUniqueChance")
                parts.append(ui("gear.src_monolith", chance=_pct(chance)) if chance else ui("gear.src_monolith_kills"))
                parts += _hall_source(ctx, "monolith", page)
            elif kind == "corrupted":  # LootDrops.InMist: kills of blighted creatures in a Blight Mist
                parts.append(ui("uniques.src_corrupted", link=rel(CREATURES_PAGE, page) + "#blight"))
                parts += _hall_source(ctx, "corrupted", page)
            elif kind == "creature":
                parts.append(ui("gear.src_creature", creature=creature_link(ctx, what, page)))
    elif j.get("globalWeight") or mod.get("globalMinLevel"):
        level = max(1, j.get("globalMinLevel") or mod.get("globalMinLevel") or 0)
        parts.append(ui("gear.src_global", biome=biome(ctx, level), level=level))
    from .formula_pages import _anchor, _values

    # WombOfCorruption.Drops: Blight Mist kills only. Not tied to the loot formula being shown, so that
    # older versions (whose formulas count as unchecked) still have it in patch comparisons.
    if item == "PT_Jewel_WombOfCorruption":
        parts.append(ui("gear.src_mist", chance=_pct(_values().get("loot", {}).get("womb_chance", 0)), link=_anchor("loot", page)))
    bosses = sorted({cr for t in ctx.data.loot.get("tables") or []
                     if any(e["id"] == item for e in t["entries"]) for cr in t.get("creatures") or []}, key=ctx.loc.creature)
    if bosses:
        parts.append(ui("gear.drops_bosses", bosses=", ".join(creature_link(ctx, cr, page) for cr in bosses)))
    chests = sorted({_chest_name(ctx, c) for t in ctx.data.loot.get("tables") or []
                     if any(e["id"] == item for e in t["entries"]) for c in t.get("chests") or []})
    if chests:  # LootDrops.Roll: a table's chests (6.0), rolled when one is opened
        parts.append(ui("uniques.src_chests", places=", ".join(chests)))
    return "; ".join(parts) or _badge(ui("badge.broken"), ui("gear.no_source"))


def _chest_name(ctx: Ctx, chest: str) -> str:
    """A dungeon's treasure chest by its location's name (TreasureChest_<location>: Valheim's
    "location_<location>"), else the wiki's own name for it."""
    where = chest.removeprefix("TreasureChest_")
    return ctx.loc.vkey(f"location_{where}", ctx.loc.ui(f"uniques.chests.{where}"))


def _hall_source(ctx: Ctx, source: str, page: str) -> list[str]:
    """The halls maps' unique rooms that give a source's uniques (HallMapRun: the Blighted Hall's
    chests, LootDrops.SourceUnique("corrupted") at hmap.blight-unique; the Hall of Three Monoliths'
    won trials, SourceUnique("monolith") at monolith.unique-chance). Shown while checked."""
    from .formula_pages import _values, shown

    if not shown(ctx, "unique-gear-sources"):
        return []
    from .halls_pages import ROOMS_PAGE

    link = rel(ROOMS_PAGE, page) + "#unique-rooms"
    if source == "corrupted":
        hall = ctx.loc.text("@enc.hmap.unique.blighthall", "Blighted Hall")
        return [ctx.loc.ui("uniques.src_blight_hall", hall=f"[{hall}]({link})",
                           chance=_pct(_values().get("unique-gear-sources", {}).get("blight_hall", 0)))]
    chance = ctx.loc.gear.get("monolithUniqueChance")
    hall = ctx.loc.text("@enc.hmap.unique.monolithhall", "Hall of Three Monoliths")
    return [ctx.loc.ui("uniques.src_monolith_hall", hall=f"[{hall}]({link})", chance=_pct(chance))] if chance else []


def unique_table(ctx: Ctx, items: list[str], page: str, catalog: dict | None = None, keyword: str | None = None) -> list[str]:
    """Uniques as a table: icon, name, their lines in short, where they drop. On a keyword's page,
    a stat pool names the stats that mention the keyword."""
    ui, uniques = ctx.loc.ui, ctx.loc.gear.get("uniques") or {}
    if catalog is None:
        catalog = {u["id"]: u for u in ctx.data.loot.get("uniques") or []}
    rows = [[_unique_icon(ctx, item, page, 64), f"[**{_unique_name(ctx, item)}**]({rel(unique_path(item), page)})",
             "<br>".join(_line_short(ctx, line, page, keyword) for line in uniques[item]["lines"]),
             _unique_sources(ctx, item, catalog, page)]
            for item in sorted(items, key=lambda i: _unique_name(ctx, i))]
    return _table(["", ui("col.name"), ui("col.effect"), ui("gear.obtained")], rows)


def _line_short(ctx: Ctx, line: dict, page: str, keyword: str | None = None) -> str:
    """One unique line on one row, for tables: a stat pool as "one of N stats", alternatives
    joined (the unique's own page lists them in full)."""
    ui, loc = ctx.loc.ui, ctx.loc
    count = f"{line['count']} × " if line.get("count", 1) > 1 else ""
    if "oneOf" in line:
        return f"{ui('gear.one_of')} " + " / ".join(_line_short(ctx, o, page, keyword) for o in line["oneOf"])
    if "pool" in line:
        if len(line["pool"]) == 1:
            return f"{count}{to_md(line['pool'][0]['text'], loc, page)}"
        short = f"{count}<i>{ui('gear.pool_short', n=len(line['pool']))}</i>"
        if keyword:  # name the stats this keyword's page is about
            from .markup import slugs

            hits = [to_md(p["text"], loc, page) for p in line["pool"] if keyword in slugs(p["text"])]
            if hits:
                short += f" {ui('gear.pool_including')} " + "; ".join(hits)
        return short
    if "template" in line:
        pick = ui(f"gear.pick.{line.get('pick')}")
        return f"{count}{to_md(line['template'].replace('{0}', f'<i>{pick}</i>'), loc, page)}"
    return f"{count}{to_md(line['text'], loc, page)}"


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


def _rift_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """What Eye Between Worlds does (JewelReveal.Refresh and BecomeRift): the portals it can point
    at (Rifts.Targets: every portal but the jewel slots), and the rift it opens beside its socket.
    Shown while the "eye-rift" formula's code is as checked."""
    from .formula_pages import shown
    from .pages import _name, _tree_link

    classes = ctx.loc.gear["uniques"][item].get("classes")
    if classes is None:
        return []
    ui = ctx.loc.ui
    md = [f"## {ui('gear.rift.title')}", ""]
    if not shown(ctx, "eye-rift"):
        return md + [f'!!! warning "{ui("formula.rechecking_title")}"',
                     f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
    md += [ui("gear.rift.targets"), ""]
    for n in sorted((n for n in ctx.tree_nodes if n["size"] == "Portal"), key=lambda n: n["id"]):
        need = sorted({classes.get(m.get("subject"), m.get("subject")) for m in n.get("mods") or []
                       if m["stat"] == "SubclassReveal"})
        hidden = f" <small>({ui('gear.rift.hidden', classes=', '.join(need))})</small>" if need else ""
        md.append(f"- {_name(ctx, n, page)} · {_tree_link(ctx, n, page)}{hidden}")
    return md + ["", ui("gear.rift.text"), ""]


def _chest_tables_with(ctx: Ctx, item: str) -> list[list[str]]:
    """Chest loot tables (LootCatalog.Tables "chests", 6.0) that can hold this item, per chest opened."""
    rows = []
    for t in ctx.data.loot.get("tables") or []:
        for e in t["entries"]:
            if e["id"] != item:
                continue
            total = sum(x["weight"] for x in t["entries"]) or 1
            first = ctx.loc.ui("gear.first_drop", n=_num(t["firstDrop"])) if t.get("firstDrop", 1) > 1 else ""
            rows += [[_chest_name(ctx, c), _pct(t["chance"] * e["weight"] / total), str(e.get("stackMin", 1)), first]
                     for c in t.get("chests") or []]
    return rows


def _global_extras(ctx: Ctx, item: str, catalog: dict, page: str) -> list[str]:
    """A unique of the global pool can also be a unique treasure map's prize (LootDrops.TreasureRewards:
    LootDrops.UniquePool at the chest) and one of the Keeper of Forgotten Sagas' gifts (Wanderer.Pool:
    global uniques only). Each part shown while its world formula is checked."""
    from .formula_pages import shown
    from .world_pages import MERCHANTS_PAGE, TREASURE_PAGE

    entry = catalog.get(item) or {}
    if entry.get("weight", 0) <= 0 or "global" not in (entry.get("sources") or ["global"]):
        return []
    parts = []
    if shown(ctx, "treasure-maps"):
        tmap = ctx.loc.text("@enc.tmap.kind.unique", "Unique Treasure Map")
        parts.append(ctx.loc.ui("uniques.also_tmap", tmap=f"[{tmap}]({rel(TREASURE_PAGE, page)}#chest)"))
    if shown(ctx, "merchants"):
        keeper = ctx.loc.text("@enc.wand.name", "Keeper of Forgotten Sagas")
        parts.append(ctx.loc.ui("uniques.also_keeper", keeper=f"[{keeper}]({rel(MERCHANTS_PAGE, page)}#keeper)"))
    return [ctx.loc.ui("uniques.also", parts=ctx.loc.ui("uniques.and").join(parts)), ""] if parts else []


def _gear_head(ctx: Ctx, item: str, g: dict, page: str) -> list[str]:
    """A unique equipment item's base, as its tooltip heads it: the item it is made from (UniqueGear.Def.Donor),
    its fixed item level (EnsureRolled: GearEnvelope.ItemLevel) and defence base (pov.defence.base)."""
    ui, donor = ctx.loc.ui, g["donor"]
    name = _item_name(ctx, donor)
    facts = [ui("uniques.base", link=f"[{name}]({rel(base_path(donor), page)})" if donor in bases(ctx) else name),
             ui("uniques.item_level", level=g["level"], biome=biome(ctx, g["level"]))]
    if g.get("defence"):
        facts.append(ui("uniques.defence_base", kind=ui(f"uniques.defence.{g['defence']}")))
    md = [" · ".join(facts), ""]
    if not g.get("loot", True):  # UniqueGear.Def.Loot: registered, never dropped
        md += [f'!!! warning "{ui("page.unimplemented")}"', f"    {ui('uniques.not_loot')}", ""]
        if g.get("pending"):
            md += [f"    {ui('uniques.pending', what=g['pending'])}", ""]
    return md


def _gear_stats(ctx: Ctx, item: str, g: dict, page: str) -> list[str]:
    """Its implicit (UniqueGear.RegisterImplicits) and stats: the donor's data with UniqueGear.ApplyBase
    (harness/gear.py), at its only quality, and its base roll (ItemBaseRolls: crit chance, armour
    break coefficient, bleed duration)."""
    from .base_pages import _rolled, _stats, base_rolls
    from .formula_pages import _term

    ui, md = ctx.loc.ui, []
    implicits = [i for i in g.get("implicits") or [] if "text" in i]
    if implicits:
        md += [f"## {ui('items.implicits')}", "", ui("items.implicits_note"), ""]
        md += [f"- {i['text']}" for i in implicits] + [""]
    if not g.get("shared"):
        return md
    roll = base_rolls(ctx).get(item) or {}
    b = {"shared": _rolled(g["shared"], roll), "info": {"tags": g.get("tags") or [], "defences": g.get("defences") or []}}
    rows = _stats(ctx, b)
    base = g.get("base") or {}
    attack = g["shared"].get("m_attack") or {}

    def sec(v: float) -> str:
        return ui("uniques.seconds", n=_num(v))

    if "drawSeconds" in base:
        rows.append([ui("uniques.draw"), sec(attack.get("m_drawDurationMin", base["drawSeconds"]))])
    if "reloadSeconds" in base:
        rows.append([ui("uniques.reload"), sec(attack.get("m_reloadTime", base["reloadSeconds"]))])
    if "raisedMovement" in base:  # UniqueGear.RaisedMovement: jog speed while blocking with it (RaisedJog)
        rows.append([ui("uniques.raised"), f"×{_num(min(1.0, max(0.05, base['raisedMovement'])))}"])
    if roll.get("critChance", -1) >= 0:  # CriticalHits.Weapon: in place of the weapon kind's base
        rows.append([ui("uniques.crit", crit=_term(ctx, "crit", page)), _pct(roll["critChance"])])
    if "armourBreakCoefficient" in roll:  # ItemBaseRolls.BreakCoefficient
        rows.append([ui("uniques.break", brk=_term(ctx, "corrosion", page, start=True)), f"×{_num(roll['armourBreakCoefficient'])}"])
    if roll.get("bleedSeconds"):  # ItemBaseRolls.BleedSeconds
        rows.append([ui("uniques.bleed", bleed=_term(ctx, "bleed", page, start=True)), sec(roll["bleedSeconds"])])
    if rows:
        md += [f"## {ui('items.stats')}", ""] + _table([ui("items.stat"), ui("col.value")], rows)
    if base.get("noEquipEffect", 0) > 0.5:  # ApplyBase: the donor's equip status effect is dropped
        md += [ui("uniques.no_equip_effect", donor=_item_name(ctx, g["donor"])), ""]
    return md


# SkeletonForms (6.0.3): the jewel that turns skeleton minions into a form, and the form.
_SKELETON_FORMS = {"PT_Jewel_BarrowVolley": "archer", "PT_Jewel_SeidrOfTheSilent": "mage"}


def _skeleton_form_section(ctx: Ctx, item: str, j: dict | None, page: str) -> list[str]:
    """What a skeleton form jewel makes of your skeletons (SkeletonForms.Keep/Apply/Make), with the
    form's tunables (skeleton-form.*)."""
    from .formula_pages import _values, shown

    form = _SKELETON_FORMS.get(item)
    if not form or not shown(ctx, "skeleton-forms"):
        return []
    ui, v = ctx.loc.ui, _values()["skeleton-forms"]
    knobs = (ctx.loc.difficulty or {}).get("knobs") or {}
    k = lambda key, default: f"{(knobs.get(key) or {}).get('value', default):g}"  # noqa: E731
    others = ", ".join(f"[{_unique_name(ctx, o)}]({rel(unique_path(o), page)})" for o in _SKELETON_FORMS if o != item)
    md = [f"## {ui('gear.skeleton.title')}", "",
          ui("gear.skeleton.text", summons=rel("mechanics/summons.md", page), others=others), ""]
    if form == "archer":
        md += [ui("gear.skeleton.archer", x=k("skeleton-form.archer-damage", 1)), ""]
    else:
        md += [ui("gear.skeleton.mage", x=k("skeleton-form.mage-damage", 1), interval=k("skeleton-form.mage-interval", 4),
                  blast=k("skeleton-form.mage-blast", 2.5)), ""]
    md += [ui("gear.skeleton.damage", default=f"{v['default_damage']:g}"), ""]
    return md


def _unique_page(ctx: Ctx, item: str, catalog: dict) -> str:
    ui, page = ctx.loc.ui, unique_path(item)
    j = ctx.loc.gear.get("jewels", {}).get(item)
    md = [f"# {_unique_name(ctx, item)}", ""]
    if art := _unique_icon(ctx, item, page, 96):
        md += [art, ""]
    g = _gear(ctx, item)
    md += [f"<b>{_unique_kind(ctx, item)}</b>" if g else f"<b>{ui('gear.unique')} {_unique_kind(ctx, item).lower()}</b>", ""]
    if g:
        md += _gear_head(ctx, item, g, page)
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
    if g:
        flavor = g["flavor"] + (f" <i>{g['quote']}</i>" if g.get("quote") else "")
    else:
        flavor = j["flavor"] if j else (ctx.loc.items.get(item, {}).get("mod") or {}).get("shared", {}).get("m_description", "")
    if flavor:
        md += [f"*{flavor}*".replace("\n", " "), ""]
    if g:
        md += _gear_stats(ctx, item, g, page)
    md += _rift_section(ctx, item, page)
    md += _skeleton_form_section(ctx, item, j, page)
    sources = _unique_sources(ctx, item, catalog, page)
    md += [f"## {ui('gear.drops')}", "", sources[:1].upper() + sources[1:] + ".", ""]
    if tables := _tables_with(ctx, item, page):
        md += [ui("gear.boss_tables"), ""] + _drop_table(ctx, tables)
    if chests := _chest_tables_with(ctx, item):
        md += [ui("uniques.chest_tables"), ""] + _table([ui("uniques.chest"), ui("gear.chance"), ui("gear.amount"), ""], chests)
    md += _global_extras(ctx, item, catalog, page)
    if item in ctx.loc.items and (ctx.loc.items[item].get("mod") or {}).get("kind"):
        md += [ui("gear.see_base", link=f"[{_unique_name(ctx, item)}]({rel(base_path(item), page)})"), ""]
    from .formula_pages import _anchor, shown

    if j and j.get("unique") and shown(ctx, "jewel-dismantling"):  # Disenchant.Returns: dust by item level (5.3.0)
        md += [ui("formula.jewel-dismantling.jewel_link", title=ui("formula.jewel-dismantling.title"),
                  link=_anchor("jewel-dismantling", page)), ""]
    from .patch_pages import history

    md += history(ctx, "uniques", [item], page)
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


def keyword_uniques_section(ctx: Ctx, items: list[str], page: str, keyword: str | None = None) -> list[str]:
    """The uniques that mention a keyword, as on the Uniques page."""
    return [f"#### {ctx.loc.ui('gear.uniques')} ({len(items)})", ""] + unique_table(ctx, items, page, keyword=keyword)
