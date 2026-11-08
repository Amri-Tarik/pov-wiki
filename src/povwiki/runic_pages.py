"""Runic crafting (6.0.0): the Runic Anvil, its forging rules, the special ores and their veins, the
alloys and the glyphs (harness/runic.py, from PassiveTree.RunicCraft).

- Runic crafting page: potential and the cost of an action (PotentialCost, Craft.Prepare), forging
  (Craft.DoForge), how alloys weight the roll (Craft.Validate, Craft.Mult), the glyphs' rules and
  chances (Craft.Validate, Craft.DoGlyph, Craft.Apply), the game's own refusals (runic.why.*), the
  phantom socket, and the craft tree's nodes and masteries for runic crafting.
- Ores: each special ore's vein (Veins.All), biome, pickaxe, ore per vein, the chance it comes with
  ordinary ore (OreBonus.Table) and what it smelts into (Smelting: Valheim's smelter).
- Alloys: theme, item lines, potential and dust, the ore they come from and the affixes they favour.
- Glyphs: effect, cost, first biome and drop chances (GlyphLoot).
- The anvil's building page shows its upgrades (anvil_section); craft tree pages and glossary terms
  link here (see_runic, related_terms).
Numbers the game computes are formulas (formulas/registry.toml: runic-cost, runic-alloys,
runic-glyphs, glyph-drops, unusual-ore), hidden when their code changes.
"""

import math

from .markup import plain, rel, to_md
from .pages import CRAFTING, Ctx, _effect, _footer, _kind, _name, _node_art, _option_art, _option_effect, _option_title, _table

RUNIC_PAGE = "crafting/runic.md"
ORES_PAGE = "items/runic/ores.md"
ALLOYS_PAGE = "items/runic/alloys.md"
GLYPHS_PAGE = "items/runic/glyphs.md"
ANVIL_ID = "PT_RunicAnvil"
ANVIL_PAGE = f"crafting/building/{ANVIL_ID}.md"  # building_pages.building_path
# GlyphLoot.Chance: the drop sources, highest first (the catalog's glyphSources ids).
SOURCES = ("boss", "elite-2", "elite-1", "dungeon-chest", "chest")
# Craft.Validate: glyphs that only work with forging, and the main glyphs the Norns also work with.
FORGE_ONLY = ("ThreeKnots", "Depths", "Memory")
NORNS_WITH = ("Tempering", "LastHeat")
OVERDRAFT = "PotentialOverdraft"  # Last Touch's flag (CraftMasteries)


def runic_on(data) -> bool:
    """Runic crafting exists in this version (the loot catalog has glyphs, 6.0.0)."""
    return bool(data.loot.get("glyphs"))


def nav_entry() -> tuple:
    return ("runic.title", [("runic.forging", RUNIC_PAGE), ("runic.anvil", ANVIL_PAGE), ("runic.ores", ORES_PAGE),
                            ("runic.alloys", ALLOYS_PAGE), ("runic.glyphs", GLYPHS_PAGE)])


# ---- Helpers ------------------------------------------------------------------------------------


def _craft(ctx: Ctx) -> Ctx | None:
    return next((c for c in [ctx, *ctx.others] if c.spec is CRAFTING), None)


def _biome(ctx: Ctx, b: str) -> str:
    return ctx.loc.vkey(f"biome_{b.lower()}", b)


def _pct(v: float) -> str:
    return f"{round(v * 100, 2):g}%"


def _n(v: float) -> str:
    return f"{round(v, 2):g}"


def _icon(ctx: Ctx, item: str, page: str, px: int = 32) -> str:
    from .base_pages import _icon as icon

    return icon(ctx, item, page, px)


def _defs(ctx: Ctx) -> dict[str, dict]:
    """item id -> its runic definition, with "kind" (ore, alloy, glyph) and the page it is on."""
    r, out = ctx.loc.runic, {}
    for a in r.get("alloys", []):
        out[a["id"]] = {**a, "kind": "alloy", "page": ALLOYS_PAGE}
        out[a["ore"]] = {"id": a["ore"], "name": a["oreName"], "flavor": a["oreFlavor"], "alloy": a["id"], "kind": "ore", "page": ORES_PAGE}
    for g in r.get("glyphs", []):
        out[g["id"]] = {**g, "kind": "glyph", "page": GLYPHS_PAGE}
    return out


def item_link(ctx: Ctx, item: str, page: str) -> str:
    """An ore, alloy or glyph linked to its row; any other item to its own page when it has one."""
    d = _defs(ctx).get(item)
    if d:
        return f"[{d['name']}]({rel(d['page'], page)}#{item})" if d["page"] != page else f"[{d['name']}](#{item})"
    from .base_pages import bases
    from .gear_pages import _link

    return _link(ctx, item, page, bases(ctx))


def _named(ctx: Ctx, item: str, page: str) -> str:
    return f"{_icon(ctx, item, page, 24)} {item_link(ctx, item, page)}"


def _anchor(item: str) -> str:
    return f'<span id="{item}"></span>'


def _term(ctx: Ctx, key: str, page: str, start: bool = False) -> str:
    from .formula_pages import _term as term

    return term(ctx, key, page, start=start)


def _block(ctx: Ctx, fid: str, page: str, body, level: int = 2) -> list[str]:
    """A formula's heading and body, or a note that it is being re-checked (formula_pages.formula_block)."""
    from .formula_pages import _values, shown

    ui = ctx.loc.ui
    head = "#" * level + f" {ui(f'runic.{fid}_title')} {{ #{fid} }}"
    if not shown(ctx, fid):
        return [head, "", f'!!! warning "{ui("formula.rechecking_title")}"', f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
    return [head, ""] + body(ctx, page, _values().get(fid, {})) + [""]


def _formula(text: str) -> list[str]:
    return [f'<div class="pov-formula">{text}</div>', ""]


# ---- Craft tree: the nodes and masteries for runic crafting and unusual ore ----------------------


def _runic_mod(m: dict) -> bool:
    """A stat of runic crafting (Craft.Me: RuneCraft stats, the tier-up and max-roll chances)."""
    return (m.get("subject") == "RuneCraft" or "RuneCraft" in (m.get("subjects") or [])
            or m.get("stat") in ("AffixTierUpChance", "AffixMaxRollChance"))


def _ore_mod(m: dict) -> bool:
    """OreBonus.MinerChance: extra chance for unusual ore."""
    return m.get("subject") == "UnusualOre"


def _tree_rows(ctx: Ctx, page: str, match, flags: tuple = ()) -> list[list[str]]:
    """Craft nodes (alike ones as one row, with their count) and mastery options with such a stat."""
    craft = _craft(ctx)
    if craft is None:
        return []
    groups: dict[tuple, list[dict]] = {}
    for n in craft.tree_nodes:
        if any(match(m) for m in n.get("mods") or []):
            groups.setdefault((plain(n["r"]["title"]), n["size"], tuple(n["r"]["stats"])), []).append(n)
    rows = []
    for nodes in groups.values():
        n = nodes[0]
        kind = _kind(craft, n) + (f" ×{len(nodes)}" if len(nodes) > 1 else "")
        rows.append([_node_art(craft, n, page, 40), _name(craft, n, page), kind, _effect(craft, page, n["r"])])
    for g in craft.option_groups.values():
        o = g["options"][0]
        if any(x.get("flag") in flags for x in g["options"]) or any(match(m) for m in o["raw"].get("mods") or []):
            rows.append([_option_art(craft, o, page, 40), _option_title(craft, page, o), craft.ui("mastery_option"),
                         _option_effect(craft, page, o)])
    return rows


def _option_link(ctx: Ctx, page: str, match=None, flag: str | None = None) -> str:
    """The first craft mastery option granting a flag or a matching stat, linked."""
    from .pages import option_path

    craft = _craft(ctx)
    for g in (craft.option_groups.values() if craft else []):
        o = g["options"][0]
        if (flag and any(x.get("flag") == flag for x in g["options"])) or (match and any(match(m) for m in o["raw"].get("mods") or [])):
            return f"[{plain(o['title'])}]({rel(option_path(craft, g), page)})"
    return ""


def see_runic(ctx: Ctx, page: str, mods: list, flags: list) -> list[str]:
    """For a craft node or mastery page: where runic crafting or unusual ore is explained."""
    if ctx.spec is not CRAFTING or not ctx.loc.runic:
        return []
    mods = [m for ms in mods for m in ms or []]
    links = []
    if any(_runic_mod(m) for m in mods) or OVERDRAFT in flags:
        links.append(f"[{ctx.loc.ui('runic.forging')}]({rel(RUNIC_PAGE, page)}#craft-tree)")
    if any(_ore_mod(m) for m in mods):
        links.append(f"[{ctx.loc.ui('runic.ores')}]({rel(ORES_PAGE, page)}#unusual-ore)")
    return [f"## {ctx.loc.ui('runic.title')}", "", " · ".join(links), ""] if links else []


def related_terms(ctx: Ctx) -> dict[str, list[tuple[str, str, str]]]:
    """Glossary terms -> these pages, for their "See also"."""
    if not ctx.loc.runic:
        return {}
    ui = ctx.loc.ui
    kind = ui("runic.title")
    forging, ores = (ui("runic.forging"), RUNIC_PAGE, kind), (ui("runic.ores"), ORES_PAGE, kind)
    anvil = (ui("runic.anvil"), ANVIL_PAGE, ui("buildings.kind"))
    return {"potential": [forging], "runic-anvil": [forging, anvil], "rune-crafting": [forging],
            "phantom-socket": [(ui("runic.phantom_title"), RUNIC_PAGE + "#phantom-socket", kind)],
            "unusual-ore": [ores, (ui("runic.alloys"), ALLOYS_PAGE, kind)]}


# ---- The anvil's building page -------------------------------------------------------------------


def anvil_section(ctx: Ctx, page: str) -> list[str]:
    """Anvil.Stages: the slots each stage opens and what its upgrade costs (UpgradeCost)."""
    r = ctx.loc.runic
    if not r:
        return []
    ui = ctx.loc.ui
    stages = r["anvil"]["stages"]
    md = [f"## {ui('runic.upgrades')}", "", ui("runic.upgrades_intro", max=r["maxSlots"], vise=_option_link(ctx, page, match=_slot_mod)), ""]
    rows = []
    for i, s in enumerate(stages):
        cost = "<br>".join(f"{_icon(ctx, c['item'], page, 24)} {item_link(ctx, c['item'], page)} ×{c['amount']}" for c in s["cost"])
        rows.append([f"**{s['name']}**", str(s["slots"]), ui("runic.built") if i == 0 else cost])
    md += _table([ui("runic.stage"), ui("runic.slots"), ui("runic.upgrade_cost")], rows)
    md += [ui("runic.upgrade_dust", dust=item_link(ctx, r["dust"], page)), "", ui("runic.shared"), ""]
    md += [f"## {ui('runic.title')}", "", ui("runic.anvil_links", forging=rel(RUNIC_PAGE, page), alloys=rel(ALLOYS_PAGE, page),
                                              glyphs=rel(GLYPHS_PAGE, page), ores=rel(ORES_PAGE, page)), ""]
    return md


def _slot_mod(m: dict) -> bool:
    """Runic Vise: one more slot (Craft.Me: CapacityFlat when crafting with runes)."""
    return m.get("stat") == "CapacityFlat" and m.get("subject") == "RuneCraft"


# ---- Formulas -----------------------------------------------------------------------------------


def _cost(ctx: Ctx, page: str, v: dict) -> list[str]:
    """PotentialCost.Of/Affordable/Roll, Craft.Me, Craft.Prepare, Craft.Apply."""
    ui, r = ctx.loc.ui, ctx.loc.runic
    md = [ui("runic.cost_text", base=r["baseCost"], potential=_term(ctx, "potential", page), dust=r["baseDust"],
             azurite=item_link(ctx, r["dust"], page), divine=item_link(ctx, r["divineDust"], page)), ""]
    md += _formula(ui("runic.cost_formula", base=r["baseCost"], cap=_pct(v["cut_cap"])))
    md += [ui("runic.cost_crit", crit=_pct(r["baseCrit"]), tree="#craft-tree"), "",
           ui("runic.cost_delay", delay=_pct(v["delay"]), glyph=item_link(ctx, "PT_GlyphDelay", page)), "",
           ui("runic.cost_afford", touch=_option_link(ctx, page, flag=OVERDRAFT)), ""]
    # A few sums of alloys and glyphs, without reductions: the cost and a critical craft's.
    rows = []
    for s in (0, 3, 5, 10, 20, 35):
        normal = max(1, math.ceil(r["baseCost"] + s - 0.0001))
        rows.append([str(s), str(normal), str(math.ceil(normal / 2)), str(r["potential"] // normal)])
    md += _table([ui("runic.cost_sum"), ui("runic.cost_normal"), ui("runic.cost_critical"), ui("runic.cost_actions")], rows)
    return md


def _alloys(ctx: Ctx, page: str, v: dict) -> list[str]:
    """Craft.Validate (the alloy multiplier from its share of the forge pool), Craft.Mult."""
    ui = ctx.loc.ui
    target, lo, hi = v["target"], v["min"], v["max"]
    md = [ui("runic.alloys_text", alloys=rel(ALLOYS_PAGE, page), target=_pct(target)), ""]
    md += _formula(ui("runic.alloys_formula", target=_n(target), rest=_n(1 - target), min=_n(lo), max=_n(hi)))
    rows = []
    for s in (0.01, 0.02, 0.05, 0.1, 0.2, 0.4):
        m = min(hi, max(lo, target * (1 - s) / max(0.0001, s * (1 - target))))
        rows.append([_pct(s), f"×{_n(m)}", _pct(s * m / (s * m + 1 - s))])
    md += _table([ui("runic.alloys_share"), ui("runic.alloys_mult"), ui("runic.alloys_after")], rows)
    two, three = 1 + 2 * (lo - 1), 1 + 3 * (lo - 1)
    md += [ui("runic.alloys_several", min=_n(lo), two=_n(two), three=_n(three)), "",
           ui("runic.alloys_depths", glyph=item_link(ctx, "PT_GlyphDepths", page), weight=_n(v["depths_weight"]), x=_n(v["depths"])), "",
           ui("runic.alloys_none"), ""]
    return md


def _glyph_rules(ctx: Ctx, page: str, v: dict) -> list[str]:
    """Craft.Validate (what goes with what), Craft.DoGlyph and Craft.Apply (the chances)."""
    ui, r = ctx.loc.ui, ctx.loc.runic
    md = [ui("runic.glyphs_text"), ""]
    rows = []
    for g in r["glyphs"]:
        if g["main"]:
            kind, works = ui("runic.main"), ui("runic.instead_of_forging")
        else:
            kind = ui("runic.support")
            works = (ui("runic.forging_only") if g["support"] in FORGE_ONLY else
                     ui("runic.norns_with", a=item_link(ctx, "PT_GlyphTempering", page), b=item_link(ctx, "PT_GlyphLastHeat", page))
                     if g["support"] == "Norns" else ui("runic.any_action"))
        rows.append([_named(ctx, g["id"], page), kind, works, to_md(g["effect"], ctx.loc, page)])
    md += _table([ui("runic.glyph"), ui("runic.kind"), ui("runic.works_with"), ui("col.effect")], rows)
    md += [f"- {ui('runic.rule_echo', echo=_pct(v['echo']), glyph=item_link(ctx, 'PT_GlyphEcho', page))}",
           f"- {ui('runic.rule_void', void=_pct(v['void']), glyph=item_link(ctx, 'PT_GlyphVoid', page))}",
           f"- {ui('runic.rule_last_heat', p=_pct(v['last_heat']), glyph=item_link(ctx, 'PT_GlyphLastHeat', page))}",
           f"- {ui('runic.rule_ascension', n=v['level_step'], cap=r['levelCap'], glyph=item_link(ctx, 'PT_GlyphAscension', page))}",
           f"- {ui('runic.rule_reinforce', x=_n(r['durabilityStep']), cap=v['durability_cap'], glyph=item_link(ctx, 'PT_GlyphReinforcement', page))}",
           f"- {ui('runic.rule_knots', glyph=item_link(ctx, 'PT_GlyphThreeKnots', page), pre=r['prefixes'] - 1, suf=r['suffixes'] - 1, x=_n(v['best_tier']))}",
           f"- {ui('runic.rule_memory', glyph=item_link(ctx, 'PT_GlyphMemory', page))}",
           f"- {ui('runic.rule_sifting', glyph=item_link(ctx, 'PT_GlyphSifting', page))}",
           f"- {ui('runic.rule_sealed')}", ""]
    return md


def _drops(ctx: Ctx, page: str, v: dict) -> list[str]:
    """GlyphLoot.Chance/Default/Stage/Roll/Open: one roll per source, then a glyph by weight among
    those its biome has opened (Defs.Stage)."""
    ui, r = ctx.loc.ui, ctx.loc.runic
    chances = r["glyphChances"]
    md = [ui("runic.drops_text", bosses=rel("monsters/bosses.md", page)), ""]
    md += _table([ui("runic.source"), ui("runic.chance")], [[ui(f"runic.source_{s.replace('-', '_')}"), _pct(chances[s])]
                                                              for s in SOURCES if s in chances])
    stages = r["stageNames"]
    md += [ui("runic.drops_share"), ""]
    rows = []
    for g in r["glyphs"]:
        cells = []
        for i in range(len(stages)):
            total = sum(x["weight"] for x in r["glyphs"] if x["stage"] <= i and x["weight"] > 0)
            cells.append(_pct(g["weight"] / total) if g["stage"] <= i and total and g["weight"] > 0 else "—")
        rows.append([_named(ctx, g["id"], page), _n(g["weight"]), *cells])
    md += _table([ui("runic.glyph"), ui("runic.weight"), *(_biome(ctx, s) for s in stages)], rows)
    boss = chances.get("boss", 0)
    md += [ui("runic.drops_example", boss=_pct(boss)), ""]
    return md


def _unusual(ctx: Ctx, page: str, v: dict) -> list[str]:
    """OreBonus.Drops/Chances (a unit of ordinary ore), OnOreHit and OnVeinHit (the Miner's chance)."""
    from .base_pages import _item_name

    ui, r = ctx.loc.ui, ctx.loc.runic
    md = [ui("runic.unusual_text", term=_term(ctx, "unusual-ore", page, start=True)), ""]
    rows = []
    seen = set()
    for base, table in _ordinary(ctx).items():
        name = _item_name(ctx, base)
        key = (name, tuple((t["ore"], round(t["chance"], 6)) for t in table))
        if key in seen:  # FlametalOre and FlametalOreNew: one row
            continue
        seen.add(key)
        rows.append([f"{_icon(ctx, base, page, 24)} {name}", "<br>".join(f"{_named(ctx, t['ore'], page)} {_pct(t['chance'])}" for t in table)])
    md += _table([ui("runic.ordinary_ore"), ui("runic.may_bring")], rows)
    md += [ui("runic.unusual_mist", ore=item_link(ctx, r["scarlet"], page), mist=_term(ctx, "blight-mist", page) or ui("runic.blight_mist")), "",
           ui("runic.unusual_miner", extra=_term(ctx, "extra-yield", page)), ""]
    tree = _tree_rows(ctx, page, _ore_mod)
    if tree:
        md += _table(["", ui("col.name"), ui("col.type"), ui("col.effect")], tree)
    return md


# ---- Pages --------------------------------------------------------------------------------------


def page_runic(ctx: Ctx) -> dict[str, str]:
    r = ctx.loc.runic
    if not r or not r.get("alloys"):
        return {}
    return {RUNIC_PAGE: _runic_page(ctx), ORES_PAGE: _ores_page(ctx), ALLOYS_PAGE: _alloys_page(ctx), GLYPHS_PAGE: _glyphs_page(ctx)}


def _runic_page(ctx: Ctx) -> str:
    ui, r, page = ctx.loc.ui, ctx.loc.runic, RUNIC_PAGE
    anvil = f"[{ui('runic.anvil')}]({rel(ANVIL_PAGE, page)})"
    md = [f"# {ui('runic.forging')}", "", ui("runic.intro", anvil=anvil, potential=_term(ctx, "potential", page),
                                              alloys=rel(ALLOYS_PAGE, page), glyphs=rel(GLYPHS_PAGE, page), ores=rel(ORES_PAGE, page)), ""]
    stages = r["anvil"]["stages"]
    md += [f"## {ui('runic.at_anvil')} {{ #anvil }}", "",
           ui("runic.anvil_text", anvil=anvil, slots=", ".join(f"{s['name']}: {s['slots']}" for s in stages), max=r["maxSlots"],
              vise=_option_link(ctx, page, match=_slot_mod)), "",
           ui("runic.stock"), ""]
    md += [f"## {ui('runic.potential_title')} {{ #potential }}", "",
           ui("runic.potential_text", potential=_term(ctx, "potential", page, start=True), n=r["potential"]), ""]
    md += _block(ctx, "runic-cost", page, _cost, level=3)
    md += [f"## {ui('runic.forge_title')} {{ #forging }}", "",
           ui("runic.forge_text", pre=r["prefixes"], suf=r["suffixes"], rarity=_term(ctx, "rarity", page)), ""]
    md += _block(ctx, "runic-alloys", page, _alloys, level=3)
    md += _block(ctx, "runic-glyphs", page, _glyph_rules)
    md += [f"## {ui('runic.refused_title')} {{ #refused }}", "", ui("runic.refused_text"), ""]
    keys = ("two-main", "duplicate", "slots", "alloy-main", "alloy-none", "forge-only", "norns", "echo", "memory", "no-potential",
            "potential", "unique", "not-eligible", "no-rare", "pool", "sockets", "no-tier", "max-level", "durability", "sealed-all")
    md += [f"- {plain(ctx.loc.text('@runic.why.' + k)).replace('{0}', '…').replace('{1}', '…')}" for k in keys
           if f"@runic.why.{k}" in ctx.loc.game]
    md += [""]
    md += [f"## {ui('runic.phantom_title')} {{ #phantom-socket }}", "",
           ui("runic.phantom_text", glyph=item_link(ctx, "PT_GlyphVoid", page), term=_term(ctx, "phantom-socket", page),
              sockets=_term(ctx, "sockets", page)), ""]
    rows = _tree_rows(ctx, page, _runic_mod, (OVERDRAFT,))
    if rows:
        md += [f"## {ui('runic.tree_title')} {{ #craft-tree }}", "", ui("runic.tree_text"), ""]
        md += _table(["", ui("col.name"), ui("col.type"), ui("col.effect")], rows)
    return "\n".join(md + _footer(ctx))


def _ordinary(ctx: Ctx) -> dict[str, list[dict]]:
    """OreBonus.Table without the ores no Valheim smelter takes any more (the legacy FlametalOre)."""
    smelters = (ctx.loc.valheim or {}).get("smelters") or {}
    taken = {c["from"] for s in smelters.values() for c in s.get("conversion") or []}
    return {base: t for base, t in ctx.loc.runic["oreChances"].items() if not smelters or base in taken}


def _pickaxe(ctx: Ctx, tier: int, page: str) -> str:
    """The lowest-tier pickaxe a player can craft that reaches this tool tier (Valheim's m_toolTier)."""
    vh = ctx.loc.valheim or {}
    crafted = {x["item"] for x in vh.get("recipes", []) if x.get("enabled")}
    picks = sorted((s.get("m_toolTier", -1), p) for p, s in vh.get("items", {}).items()
                   if p.startswith("Pickaxe") and p in crafted and s.get("m_toolTier", -1) >= tier)
    if not picks:
        return str(tier)
    return f"{_icon(ctx, picks[0][1], page, 24)} {item_link(ctx, picks[0][1], page)}"


def _ores_page(ctx: Ctx) -> str:
    from .base_pages import _item_name

    ui, r, page = ctx.loc.ui, ctx.loc.runic, ORES_PAGE
    p = r["veinPlacement"]
    md = [f"# {ui('runic.ores')}", "", ui("runic.ores_intro", n=len(r["alloys"]), veins=len(r["veins"]), alloys=rel(ALLOYS_PAGE, page),
                                           anvil=rel(ANVIL_PAGE, page)), ""]
    veins = {v["ore"]: v for v in r["veins"]}
    from_ore: dict[str, list[str]] = {}
    for base, table in _ordinary(ctx).items():
        for t in table:
            name = _item_name(ctx, base)
            line = f"{name} {_pct(t['chance'])}"
            if line not in from_ore.setdefault(t["ore"], []):
                from_ore[t["ore"]].append(line)
    rows = []
    for a in r["alloys"]:
        ore, v = a["ore"], veins.get(a["ore"])
        if v:
            where = f"**{v['name']}**<br>" + "<br>".join(ui("runic.per_cell", biome=_biome(ctx, x["biome"]), p=_pct(x["rate"])) for x in v["rates"])
            pick, amount = _pickaxe(ctx, v["tier"], page), f"{v['min']}–{v['max']}"
        else:  # scarlet tin: tin inside a Blight Mist
            where, pick, amount = ui("runic.in_mist"), "—", "—"
        name = f"{_anchor(ore)}**{a['oreName']}**<br><small>*{a['oreFlavor']}*</small>"
        rows.append([_icon(ctx, ore, page, 40), name, where, pick, amount, "<br>".join(from_ore.get(ore, [])) or "—",
                     _named(ctx, a["id"], page)])
    md += _table(["", ui("runic.ore"), ui("runic.vein"), ui("runic.pickaxe"), ui("runic.per_vein"), ui("runic.from_ordinary"),
                  ui("runic.smelts_into")], rows)
    md += [f"## {ui('runic.veins_title')} {{ #veins }}", "",
           ui("runic.veins_text", cell=_n(p["cell"]), gap=_n(p["buildGap"]), slope=_n(p["maxSlope"]), shift=_n(p["shift"])), ""]
    smelter = ((ctx.loc.valheim or {}).get("smelters") or {}).get("smelter") or {}
    if smelter:
        md += [f"## {ui('runic.smelting_title')} {{ #smelting }}", "",
               ui("runic.smelting_text", smelter=ctx.loc.vkey("piece_smelter", "Smelter"), fuel=_item_name(ctx, smelter["fuel"]),
                  n=smelter["fuelPerProduct"], s=_n(smelter["secPerProduct"]), max=smelter["maxOre"]), ""]
    md += _block(ctx, "unusual-ore", page, _unusual)
    return "\n".join(md + _footer(ctx))


def _alloys_page(ctx: Ctx) -> str:
    from .item_pages import mod_path

    ui, r, page = ctx.loc.ui, ctx.loc.runic, ALLOYS_PAGE
    md = [f"# {ui('runic.alloys')}", "", ui("runic.alloys_intro", ores=rel(ORES_PAGE, page), forging=rel(RUNIC_PAGE, page)), ""]
    rows = []
    for a in r["alloys"]:
        name = f"{_anchor(a['id'])}**{a['name']}**<br><small>*{a['flavor']}*</small>"
        theme = a["theme"]["name"] if a.get("theme") else "—"
        rows.append([_icon(ctx, a["id"], page, 40), name, theme, to_md(a["lines"][0], ctx.loc, page), str(a["cost"]), str(a["dust"]),
                     _named(ctx, a["ore"], page), str(len(_favoured(ctx, a)))])
    md += _table(["", ui("runic.alloy"), ui("runic.theme"), ui("col.effect"), ui("runic.potential_col"), ui("runic.dust_col"),
                  ui("runic.smelted_from"), ui("runic.favoured")], rows)
    md += [ui("runic.alloys_rule", link=f"{rel(RUNIC_PAGE, page)}#runic-alloys"), ""]
    md += [f"## {ui('runic.favoured_title')} {{ #favoured }}", "", ui("runic.favoured_text"), ""]
    for a in r["alloys"]:
        found = _favoured(ctx, a)
        if not found:
            continue
        links = " · ".join(f"[{t}]({rel(mod_path(x), page)})" for t, x in found)
        # Links to every favoured mod: long (54 KB in Russian), and each mod is searchable on its own page.
        md += [f'??? note "{a["name"]} ({len(found)})"', "", '    <div data-search-exclude markdown="1">', "",
               f"    {links}", "", "    </div>", ""]
    return "\n".join(md + _footer(ctx))


def _favoured(ctx: Ctx, a: dict) -> list[tuple[str, dict]]:
    """The item mods an alloy favours, one per name (a mod's tiers and slot variants share it)."""
    from .item_pages import _title

    affixes = {x["id"]: x for x in ctx.loc.loot.get("affixes", [])}
    return sorted({_title(affixes[i]): affixes[i] for i in a["affixes"] if i in affixes}.items())


def _glyphs_page(ctx: Ctx) -> str:
    ui, r, page = ctx.loc.ui, ctx.loc.runic, GLYPHS_PAGE
    md = [f"# {ui('runic.glyphs')}", "", ui("runic.glyphs_intro", forging=rel(RUNIC_PAGE, page), divine=item_link(ctx, r["divineDust"], page)), ""]
    rows = []
    for g in r["glyphs"]:
        name = f"{_anchor(g['id'])}**{g['name']}**<br><small>*{g['flavor']}*</small>"
        kind = ui("runic.main") if g["main"] else ui("runic.support")
        rows.append([_icon(ctx, g["id"], page, 40), name, to_md(g["effect"], ctx.loc, page), kind, str(g["cost"]), str(g["dust"]),
                     str(g["divine"]) if g["divine"] else "—", _biome(ctx, g["firstBiome"])])
    md += _table(["", ui("runic.glyph"), ui("col.effect"), ui("runic.kind"), ui("runic.potential_col"), ui("runic.dust_col"),
                  ui("runic.divine_col"), ui("runic.first_biome")], rows)
    md += [ui("runic.glyphs_rules", link=f"{rel(RUNIC_PAGE, page)}#runic-glyphs"), ""]
    md += _block(ctx, "glyph-drops", page, _drops)
    return "\n".join(md + _footer(ctx))


# ---- Socket kinds (the sockets glossary page) ----------------------------------------------------

_BLIGHT_SIGILS = ("PT_SigilOathDevourer", "PT_SigilCrimsonBrood")  # ItemSockets.Sigils with Blight = true


def socket_kinds(ctx: Ctx, page: str) -> list[str]:
    """The kinds of sockets (ItemSockets: runic, divine, corrupted, phantom), what each takes and
    how it is made, then how dropped items get sockets. On the sockets glossary page."""
    from .formula_pages import _values, shown

    if not shown(ctx, "socket-kinds"):
        return []
    ui, v = ctx.loc.ui, _values()["socket-kinds"]
    pct = lambda x: f"{round(x * 100, 2):g}%"  # noqa: E731
    punch = {k: _named(ctx, f"PT_{k}Punch", page) for k in ("Runic", "Divine", "Corrupted")}
    blight = ", ".join(_named(ctx, s, page) for s in _BLIGHT_SIGILS)
    rows = [
        [f"**{ui('sockets.runic')}**", ui("sockets.takes_any"), "—",
         ui("sockets.runic_how", punch=punch["Runic"], up=pct(v["punch_up"]), down=pct(1 - v["punch_up"]))],
        [f"**{ui('sockets.divine')}**", ui("sockets.takes_any"), ui("sockets.divine_effect", more=pct(v["divine"] - 1)),
         ui("sockets.divine_how", punch=punch["Divine"], runic=punch["Runic"])],
        [f"**{ui('sockets.corrupted')}**", ui("sockets.takes_blight", sigils=blight), "—",
         ui("sockets.corrupted_how", punch=punch["Corrupted"])],
        [f"**{_term(ctx, 'phantom-socket', page, start=True)}**", ui("sockets.takes_any"), "—",
         ui("sockets.phantom_how", page=rel(RUNIC_PAGE, page) + "#phantom-socket")],
    ]
    md = [f"## {ui('sockets.kinds')}", ""]
    md += _table([ui("sockets.col_kind"), ui("sockets.col_takes"), ui("sockets.col_effect"), ui("sockets.col_how")], rows)
    md += ['!!! note ""', "    " + ui("sockets.blight_note", sigils=blight), "",
           ui("sockets.punch_rules"), "",
           ui("sockets.corruption", term=_term(ctx, "corruption", page), more=pct(v["corrupt_sigils"]), most=v["max"]), ""]
    md += [f"## {ui('sockets.drops')}", "",
           ui("sockets.drops_text", normal=pct(v["drop_normal"]), magic=pct(v["drop_magic"]), rare=pct(v["drop_rare"]),
              unique=pct(v["drop_unique"]), one=pct(v["how_many"][0]), two=pct(v["how_many"][1]), three=pct(v["how_many"][2])), ""]
    return md

