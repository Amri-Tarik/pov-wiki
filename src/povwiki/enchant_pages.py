"""Enchantments at the Runecarver Table (6.0: Enchants, EnchantLoot, harness/enchant.py).

- Index: the Enchant tab's lists by item kind (Enchants.Tabs, Enchants.OnTab), each enchantment
  with its tiers T5..T1 (and T0), in the window's order (EnchantWindow: theme rows before boss
  rows, prefixes before suffixes, themes in Enchants.Themes order); how enchanting works
  (Enchants.Why / Apply / Remove, ItemSeal.Seal); the costs per tier (Enchants.CostOf).
- A page per enchantment: every tier's line as the window writes it (EnchantWindow.Range), its
  cost, the scroll that opens it, the item kinds it goes on and the item mods behind it.
- Scrolls: the three scroll items (EnchantLoot.Prefabs), what each opens (Enchants.LearnTheme /
  LearnBoss / LearnZero, Open) and where it drops (formula "enchant-scrolls": EnchantLoot.Roll,
  BossDrop, GlyphLoot.Stage).
"""

from .markup import plain, rel, to_md
from .pages import Ctx, _footer, _table

ENCHANT_PAGE = "items/enchantments.md"
SCROLLS_PAGE = "items/enchantments/scrolls.md"
_ROMAN = ("", "I", "II", "III", "IV", "V")
_SCROLL, _BOSS_SCROLL, _EXALTED = "PT_EnchantScroll", "PT_EnchantScrollBoss", "PT_EnchantScrollExalted"
# Glyphs that take properties away (GlyphOp: RemovePrefix, RemoveSuffix, Cleansing, Sifting).
_REMOVING_GLYPHS = ("PT_GlyphUnbindPrefix", "PT_GlyphUnbindSuffix", "PT_GlyphCleansing", "PT_GlyphSifting")
_built: set[str] = set()  # data versions with enchantment pages (for the navigation)


def enchant_path(row_id: str) -> str:
    return f"items/enchantment/{row_id}.md"


def enchant_built() -> bool:
    return bool(_built)


_cache: dict[tuple[str, str], dict] = {}


def data(ctx: Ctx) -> dict:
    """The rendered enchantments (harness/enchant.py), or {} before 6.0. Read once per version and
    language: GameData.rendered reads the whole file on every call."""
    key = (ctx.data.version, ctx.loc.lang.mod)
    if key not in _cache:
        _cache[key] = ctx.loc.data.rendered(ctx.loc.lang.mod).get("enchant") or {}
    return _cache[key]


def _rows(d: dict) -> list[dict]:
    """EnchantWindow's order: theme rows first, prefixes before suffixes, themes in their order."""
    themes = [t["id"] for t in d["themes"]]
    return sorted(d["rows"], key=lambda r: (r["boss"] is not None, r["place"] != "prefix",
                                            themes.index(r["theme"]) if r["theme"] in themes else 99))


def _theme(d: dict, tid: str | None) -> dict | None:
    return next((t for t in d["themes"] if t["id"] == tid), None)


def _boss(d: dict, prefab: str | None) -> dict | None:
    return next((b for b in d["bosses"] if b["prefab"] == prefab), None)


def _name(ctx: Ctx, r: dict, page: str) -> str:
    """An enchantment as the Enchant tab names it (EnchantLoot.RowName: its line with # for the value)."""
    return f"[{plain(r['name'])}]({rel(enchant_path(r['id']), page)})"


def _opened_by(ctx: Ctx, d: dict, r: dict, page: str) -> str:
    """The scroll that opens a row: its theme's Scroll of Enchantment, or its boss's Scroll of Ancient Will."""
    if r["boss"]:
        b = _boss(d, r["boss"])
        return f"[{b['name'] if b else r['boss']}]({rel(SCROLLS_PAGE, page)}#boss)"
    t = _theme(d, r["theme"])
    return f"[{t['name'] if t else r['theme']}]({rel(SCROLLS_PAGE, page)}#theme-{r['theme']})"


def _t0_name(text: str) -> str:
    """A T0 line's name, the words before its colon ("First Blood: ..."), or the whole line."""
    head, sep, _ = plain(text).partition(":")
    return head if sep and len(head) <= 40 else plain(text)


def _place(ctx: Ctx, r: dict) -> str:
    return ctx.loc.ui(f"enchant.{r['place']}")


def _kinds(d: dict, row_id: str) -> list[dict]:
    return [t for t in d["tabs"] if row_id in t["rows"]]


def _affixes(ctx: Ctx) -> dict[str, dict]:
    return {a["id"]: a for a in ctx.loc.loot["affixes"]}


_owners: dict[tuple[str, str], dict] = {}


def owners(ctx: Ctx) -> dict[str, dict]:
    """affix id -> the enchantment row it is a tier of (T5..T1 or T0)."""
    key = (ctx.data.version, ctx.loc.lang.mod)
    if key not in _owners:
        out: dict[str, dict] = {}
        for r in data(ctx).get("rows", []):
            for t in r["tiers"]:
                if t:
                    out.setdefault(t["owner"], r)
        _owners[key] = out
    return _owners[key]


def page_enchant(ctx: Ctx) -> dict[str, str]:
    d = data(ctx)
    if not d.get("rows"):
        return {}
    _built.add(ctx.data.version)
    pages = {ENCHANT_PAGE: _index(ctx, d), SCROLLS_PAGE: _scrolls(ctx, d)}
    for r in d["rows"]:
        pages[enchant_path(r["id"])] = _row_page(ctx, d, r)
    return pages


# ---- Index ----------------------------------------------------------------------------------------


def _how(ctx: Ctx, d: dict, page: str) -> list[str]:
    """How enchanting works (Enchants.Why, Apply, Remove; ItemSeal.Seal; Craft glyph ops)."""
    from .building_pages import building_path
    from .gear_pages import currency_path

    ui, loc = ctx.loc.ui, ctx.loc
    table = f"[{loc.text('@piece.PT_RuneCarverTable.name')}]({rel(building_path('PT_RuneCarverTable'), page)})"
    dust = f"[{loc.loot['items'].get('PT_AzuriteDust', {}).get('name', 'PT_AzuriteDust')}]({rel(currency_path('PT_AzuriteDust'), page)})"
    seal = f"[{loc.loot['items'].get('PT_RuneOfCrimsonSeal', {}).get('name', 'PT_RuneOfCrimsonSeal')}]({rel(currency_path('PT_RuneOfCrimsonSeal'), page)})"
    glyphs = ", ".join(loc.text(f"@item.{g}.name") for g in _REMOVING_GLYPHS)
    md = [f"## {ui('enchant.how')} {{ #how }}", ""]
    md += [f"- {ui('enchant.how_learn', table=table, tab=d['text'].get('enchant.ui.tab') or ui('enchant.title'), scrolls=rel(SCROLLS_PAGE, page))}",
           f"- {ui('enchant.how_one')}",
           f"- {ui('enchant.how_any_level')}",
           f"- {ui('enchant.how_not')}",
           f"- {ui('enchant.how_roll', mods=rel('items/mods.md', page))}",
           f"- {ui('enchant.how_remove', n=d['removeCost'], dust=dust, glyphs=glyphs, anvil=loc.text('@piece.runicanvil.name'))}",
           f"- {ui('enchant.how_seal', seal=seal)}", ""]
    return md


def _costs(ctx: Ctx, d: dict, page: str) -> list[str]:
    from .gear_pages import currency_path

    ui, loot = ctx.loc.ui, ctx.loc.loot["items"]
    dust = f"[{loot.get('PT_AzuriteDust', {}).get('name', '')}]({rel(currency_path('PT_AzuriteDust'), page)})"
    divine = f"[{loot.get('PT_DivineAzuriteDust', {}).get('name', '')}]({rel(currency_path('PT_DivineAzuriteDust'), page)})"
    md = [f"## {ui('enchant.cost')} {{ #cost }}", "", ui("enchant.cost_intro"), ""]
    md += _table([ui("enchant.tier"), dust, divine], [[c["label"], str(c["dust"]), str(c["divine"]) if c["divine"] else "—"]
                                                     for c in reversed(d["costs"])])
    md += [ui("enchant.remove_cost", n=d["removeCost"], dust=dust), ""]
    return md


def _index(ctx: Ctx, d: dict) -> str:
    ui, page = ctx.loc.ui, ENCHANT_PAGE
    md = [f"# {ui('enchant.title')}", "", ui("enchant.intro", scrolls=rel(SCROLLS_PAGE, page)), ""]
    md += _how(ctx, d, page)
    md += _costs(ctx, d, page)
    md += [f"## {ui('enchant.by_kind')}", "", ui("enchant.by_kind_intro"), ""]
    md += [" · ".join(f"[{t['name']}](#{t['id']})" for t in d["tabs"] if t["rows"]), ""]
    rows = _rows(d)
    for tab in d["tabs"]:
        mine = [r for r in rows if r["id"] in tab["rows"]]
        if not mine:
            continue
        md += [f"### {tab['name']} ({len(mine)}) {{ #{tab['id']} }}", ""]
        md += _table([ui("enchant.enchantment"), ui("enchant.place"), ui("enchant.opened_by"), "T5", "T4", "T3", "T2", "T1", "T0"],
                     [[_name(ctx, r, page), _place(ctx, r), _opened_by(ctx, d, r, page),
                       *(t["number"] if t else "—" for t in r["tiers"][:5]),
                       _t0_name(r["tiers"][5]["text"]) if r["tiers"][5] else "—"] for r in mine])
    return "\n".join(md + _footer(ctx))


# ---- One enchantment ------------------------------------------------------------------------------


def _row_page(ctx: Ctx, d: dict, r: dict) -> str:
    from .item_pages import _title, mod_path

    ui, loc, page = ctx.loc.ui, ctx.loc, enchant_path(r["id"])
    md = [f"# {plain(r['name'])}", ""]
    kinds = ", ".join(f"[{t['name']}]({rel(ENCHANT_PAGE, page)}#{t['id']})" for t in _kinds(d, r["id"])) or "—"
    md += [f"<b>{_place(ctx, r)}</b> · {ui('enchant.goes_on', kinds=kinds)}", ""]
    if r["boss"]:
        b = _boss(d, r["boss"])
        md += [ui("enchant.row_boss", scroll=f"[{b['scroll'] if b else r['boss']}]({rel(SCROLLS_PAGE, page)}#boss)"), ""]
    else:
        t = _theme(d, r["theme"])
        md += [ui("enchant.row_theme", theme=f"[{t['name'] if t else r['theme']}]({rel(SCROLLS_PAGE, page)}#theme-{r['theme']})"), ""]

    def opened(i: int) -> str:
        if i == 5:
            return f"[{r.get('zeroScroll') or loc.ui('enchant.exalted')}]({rel(SCROLLS_PAGE, page)}#exalted)"
        if r["boss"]:
            b = _boss(d, r["boss"])
            return f"[{b['scroll'] if b else r['boss']}]({rel(SCROLLS_PAGE, page)}#boss)"
        t = _theme(d, r["theme"])
        return f"[{t['scrolls'][i] if t else _ROMAN[i + 1]}]({rel(SCROLLS_PAGE, page)}#theme-{r['theme']})"

    md += [f"## {ui('enchant.tiers')}", ""]
    md += _table([ui("enchant.tier"), ui("enchant.value"), ui("enchant.dust"), ui("enchant.divine"), ui("enchant.scroll")],
                 [[t["label"], to_md(t["text"], loc, page), str(t["dust"]), str(t["divine"]) if t["divine"] else "—", opened(i)]
                  for i, t in reversed(list(enumerate(r["tiers"]))) if t])
    affixes = _affixes(ctx)
    scaled = [a for a in {t["owner"] for t in r["tiers"][:5] if t} if affixes.get(a, {}).get("scaled")]
    if scaled:
        md += [ui("enchant.scaled_note", mod=rel(mod_path(affixes[scaled[0]]), page)), ""]
    mods = []
    for owner in dict.fromkeys(t["owner"] for t in r["tiers"] if t):
        if a := affixes.get(owner):
            mods.append(f"[{_title(a)}]({rel(mod_path(a), page)})")
    if mods:
        md += [f"## {ui('enchant.item_mods')}", "", ui("enchant.item_mods_intro"), "", ", ".join(mods), ""]
    return "\n".join(md + _footer(ctx))


# ---- Scrolls --------------------------------------------------------------------------------------


def _scroll_head(ctx: Ctx, d: dict, prefab: str, anchor: str, page: str) -> list[str]:
    from .base_pages import _icon

    # The item's own description is left out: it says the scroll is read when picked up, but it
    # is learned by using it (EnchantLoot.Use; EnchantLoot.Pickup only checks its owner).
    item = d["items"].get(prefab, {})
    md = [f"## {item.get('name') or prefab} {{ #{anchor} }}", ""]
    if art := _icon(ctx, prefab, page, 64):
        md += [art, ""]
    return md


def _scrolls(ctx: Ctx, d: dict) -> str:
    from .formula_pages import shown
    from .monster_pages import creature_link

    ui, page = ctx.loc.ui, SCROLLS_PAGE
    md = [f"# {ui('enchant.scrolls_title')}", "", ui("enchant.scrolls_intro", use=d["text"].get("enchant.scroll.use", ""),
                                                      index=rel(ENCHANT_PAGE, page)), ""]
    drops = shown(ctx, "enchant-scrolls")
    if not drops:
        md += [f'!!! warning "{ui("formula.rechecking_title")}"', f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
    rows = _rows(d)

    # Theme scrolls: one per theme with enchantments, five stages (Enchants.LearnTheme).
    md += _scroll_head(ctx, d, _SCROLL, "theme", page)
    md += [ui("enchant.theme_intro"), ""]
    md += _table([ui("enchant.stage"), ui("enchant.opens")], [[_ROMAN[i + 1], e] for i, e in enumerate(d["effects"]["theme"])])
    if drops:
        md += _theme_drops(ctx, d, page)
    for t in d["themes"]:
        mine = [r for r in rows if r["theme"] == t["id"]]
        if not mine:
            continue
        md += [f'### {t["name"]} {{ #theme-{t["id"]} }}', "", " · ".join(t["scrolls"]), ""]
        md += _table([ui("enchant.enchantment"), ui("enchant.place"), ui("enchant.goes_on_col")],
                     [[_name(ctx, r, page), _place(ctx, r), ", ".join(k["name"] for k in _kinds(d, r["id"]))] for r in mine])
    empty = [t["name"] for t in d["themes"] if not any(r["theme"] == t["id"] for r in rows)]
    if empty:
        md += [ui("enchant.empty_themes", themes=", ".join(empty)), ""]

    # Boss scrolls (Enchants.LearnBoss: every tier of the boss's rows).
    md += _scroll_head(ctx, d, _BOSS_SCROLL, "boss", page)
    md += [ui("enchant.boss_intro", effect=d["effects"]["boss"]), ""]
    if drops:
        md += [ui("enchant.boss_drop", range=f"{d['bossRange']:g}", foreign=d["text"].get("enchant.scroll.foreign", "")), ""]
    md += _table([ui("enchant.boss"), ui("enchant.scroll"), ui("enchant.enchantments")],
                 [[creature_link(ctx, b["prefab"], page), b["scroll"],
                   "<br>".join(_name(ctx, r, page) for r in rows if r["boss"] == b["prefab"])]
                  for b in d["bosses"] if b["rows"]])

    # Exalted scrolls (Enchants.LearnZero: one row's T0).
    md += _scroll_head(ctx, d, _EXALTED, "exalted", page)
    md += [ui("enchant.exalted_intro", effect=d["effects"]["zero"]), ""]
    if drops:
        from .formula_pages import _anchor

        chance = (ctx.data.loot.get("enchant") or {}).get("perfect", 0.08)
        md += [ui("enchant.exalted_drop", level=d["exaltedAbove"], chance=f"{round(chance * 100, 2):g}%",
                  range=f"{d['bossRange']:g}", link=_anchor("creature-level", page)), ""]
    zero = [r for r in rows if r["tiers"][5]]
    md += _table([ui("enchant.enchantment"), "T0", ui("enchant.scroll")],
                 [[_name(ctx, r, page), to_md(r["tiers"][5]["text"], ctx.loc, page), r.get("zeroScroll", "")] for r in zero])
    return "\n".join(md + _footer(ctx))


def _theme_drops(ctx: Ctx, d: dict, page: str) -> list[str]:
    """EnchantLoot.Roll: a chance per loot drop by source, the scroll stage of the drop's biome
    level (GlyphLoot.Stage), a theme you don't know at that stage yet."""
    from .monster_pages import _biome_name

    ui = ctx.loc.ui
    sources = (ctx.data.loot.get("enchant") or {}).get("sources") or {}
    md = [f"### {ui('enchant.theme_drop')} {{ #theme-drops }}", "", ui("enchant.theme_drop_intro"), ""]
    names = {"boss": ui("gear.source.boss"), "elite-2": ui("enchant.elite2"), "elite-1": ui("enchant.elite1"),
             "dungeon-chest": ui("gear.source.dungeon-chest"), "chest": ui("gear.source.chest")}
    md += _table([ui("enchant.source"), ui("enchant.chance")],
                 [[names.get(k, k), f"{round(v * 100, 2):g}%"] for k, v in sources.items()])
    biomes = {b["id"]: b["level"] for b in ctx.loc.loot.get("biomes") or []}
    by_stage: dict[int, list[str]] = {}
    for biome, stage in sorted(d["stages"].items(), key=lambda kv: (biomes.get(kv[0], 0), kv[0])):
        if biome != "Ocean":
            by_stage.setdefault(stage, []).append(_biome_name(ctx, biome))
    md += [ui("enchant.stage_intro"), ""]
    md += _table([ui("enchant.stage"), ui("enchant.biomes")], [[_ROMAN[s], ", ".join(bs)] for s, bs in sorted(by_stage.items())])
    md += [ui("enchant.theme_drop_rule"), ""]
    return md


# ---- Links from other pages -----------------------------------------------------------------------


def boss_scroll_link(ctx: Ctx, prefab: str, page: str) -> str | None:
    """A boss's Scroll of Ancient Will, linked, for its row on the bosses page."""
    d = data(ctx)
    b = _boss(d, prefab) if d else None
    if not b or not b["rows"]:
        return None
    return f"[{b['scroll']}]({rel(SCROLLS_PAGE, page)}#boss)"


def enchant_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """For a currency page: what an item has to do with enchanting (dust pays, the seal frees)."""
    d = data(ctx)
    if not d.get("rows"):
        return []
    ui = ctx.loc.ui
    link = rel(ENCHANT_PAGE, page)
    if item == "PT_AzuriteDust":
        text = ui("enchant.on_dust", link=link, n=d["removeCost"])
    elif item == "PT_DivineAzuriteDust":
        tiers = ", ".join(c["label"] for c in reversed(d["costs"]) if c["divine"])
        text = ui("enchant.on_divine", link=link, tiers=tiers)
    elif item == "PT_RuneOfCrimsonSeal":
        text = ui("enchant.on_seal", link=f"{link}#how")
    else:
        return []
    return [f"## {ui('enchant.title')}", "", text, ""]


def table_section(ctx: Ctx, page: str) -> list[str]:
    """For the Runecarver Table's page: its Enchant tab."""
    d = data(ctx)
    if not d.get("rows"):
        return []
    ui = ctx.loc.ui
    return [f"## {ui('enchant.title')}", "",
            ui("enchant.on_table", tab=d["text"].get("enchant.ui.tab") or ui("enchant.title"), link=rel(ENCHANT_PAGE, page),
               scrolls=rel(SCROLLS_PAGE, page)), ""]


def mod_section(ctx: Ctx, affix_id: str, page: str) -> list[str]:
    """For an item mod's page: the enchantment it is a tier of."""
    r = owners(ctx).get(affix_id)
    if not r:
        return []
    labels = ", ".join(t["label"] for t in r["tiers"] if t and t["owner"] == affix_id)
    return [f"## {ctx.loc.ui('enchant.enchantment')}", "",
            ctx.loc.ui("enchant.on_mod", link=f"[{plain(r['name'])}]({rel(enchant_path(r['id']), page)})", tiers=labels), ""]
