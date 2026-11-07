"""Halls of Oaths: maps built from room items (PassiveTree.Encounters.HallMaps).

- How the halls work: gates and their lobbies, the Book of the Halls (board size by the gate's
  level: HallMapKnobs.RoomsFor / SizeFor, HallMapBoard.Validate), launching, sealed fights
  (HallMapRun.RoomNumber), deaths (HallMapRunDeath), ascension points (HallsPoints,
  HallMapRun.AltarAsk) and the room merchant (HallMapShop).
- Room items: the catalog's "halls-rooms" currency rows (LootCatalog.Currency) with the rooms the
  code defines (HallMapDefs.Build): what each holds (HallMapItems.Gives / RuleText) and where it
  drops (LootDrops.CurrencyHere).
- Map modifiers: the catalog's mapAffixes (HallMapAffixes: grades, the runes that act on a map,
  tiers and how a modifier's numbers roll).

Game text (names, room lines, modifier lines, merchant name) comes from the mod's localisation
(@enc.hmap.*); the wiki's own words are under [halls] in i18n/ui.
"""

from .markup import rel
from .pages import Ctx, _footer, _table

HALLS_PAGE = "halls/index.md"
ROOMS_PAGE = "halls/rooms.md"
MODIFIERS_PAGE = "halls/modifiers.md"
ASCENDANCY_PAGE = "ascendancy/index.md"  # the Ascendancy section (classes taken at the halls' altar)

# HallMapDefs.Biomes: the halls' biomes in order, as the code names them (Theme).
THEMES = ("Meadows", "Forest", "Swamp", "Mountain", "Plains", "Mist", "Ash", "North")
# Catalog sources ("biome:<Valheim biome>") -> Theme.
SOURCE_THEME = {"Meadows": "Meadows", "BlackForest": "Forest", "Swamp": "Swamp", "Mountain": "Mountain", "Plains": "Plains",
                "Mistlands": "Mist", "AshLands": "Ash", "DeepNorth": "North"}
# HallMapDefs.BossOf: the boss of a biome's boss room (the Deep North's is the halls' own herald).
BIOME_BOSS = {"Meadows": "Eikthyr", "Forest": "gd_king", "Swamp": "Bonemass", "Mountain": "Dragon", "Plains": "GoblinKing",
              "Mist": "SeekerQueen", "Ash": "Fader", "North": "PoV_HallsBoss7"}
# HallsBosses.Defs: the Deep North herald's name key.
HALLS_BOSS_NAMES = {"PoV_HallsBoss7": "@enc.halls.boss7"}
# HallMapDefs.Normal: ordinary room types in the code's order; then boss rooms.
TYPES = ("Armory", "Treasury", "Forge", "OreHall", "Burial", "Cartographer")
# HallMapItems.TypeSign: the item pictured on a room type's tablet.
TYPE_SIGN = {"Armory": "SwordIron", "Treasury": "Coins", "Forge": "Bronze", "OreHall": "CopperOre", "Burial": "TrophySkeleton",
             "BossRoom": "TrophyDraugrElite"}
# HallMapDefs.Build: the boss rooms of the halls' own bosses (their biome).
HILDIR = {"Brenna": "Forest", "Geirrhafa": "Mountain", "ZilThungr": "Plains", "Reto": "Ash"}
# HallMapDefs.Build: unique rooms -> (room type, biome, rule); HallMapItems.UniqueSign / RuleText.
UNIQUE = {"MarinerTomb": ("Burial", "Swamp", "rare-keeper"), "RuneArchive": ("Armory", "Mist", "rune-racks"),
          "MonolithHall": ("Armory", "Mountain", "monoliths"), "BlightHall": ("Burial", "Plains", "blight")}
# Items a unique room's rule names (its rewards), linked from its row and back from their pages.
UNIQUE_ITEMS = {"MonolithHall": "PT_FirstWardenVisage", "BlightHall": "PT_CorruptedWardenVisage"}
# HallMapAffixes.Runes: the runes that act on a map, in the order the page lists them.
MAP_RUNES = ("PT_RuneOfSpark", "PT_RuneOfWeaving", "PT_RuneOfChange", "PT_RuneOfJarl", "PT_RuneOfAscent",
             "PT_GreatRuneOfOblivion", "PT_GreatRuneOfFate")
RENEW_RUNE = "PT_RuneOfRenewedTrade"  # HallMapShop.RuneId
TIERS = 4  # HallsPoints.Tiers
# HallMapItems.EnglishType / BiomeOf: a room's English name when it has no localisation line.
ENGLISH_TYPE = {"Cartographer": "Cartographer's Hall", "BossRoom": "Boss Room", "Burial": "Burial Hall", "OreHall": "Ore Hall"}
ENGLISH_OF = {"Meadows": "the Meadows", "Forest": "the Black Forest", "Swamp": "the Swamp", "Mountain": "the Mountains",
              "Plains": "the Plains", "Mist": "the Mistlands", "Ash": "the Ashlands", "North": "the Deep North"}
# The section's navigation, filled when this version has the halls' maps (nav() in pages.py).
NAV: list = []


# ---- Data ---------------------------------------------------------------------------------------


def rooms(ctx: Ctx) -> list[dict]:
    """The room items the catalog drops, in its order: id, kind ("room", "boss", "unique"), type,
    biome (Theme), Hildir boss key or unique key, and its catalog row."""
    out = []
    for c in ctx.data.loot.get("currency") or []:
        if c.get("family") != "halls-rooms":
            continue
        item = c["id"]
        if item.startswith("PT_HallRoomU_"):
            key = item.removeprefix("PT_HallRoomU_")
            if key not in UNIQUE:
                continue
            kind, (rtype, theme, _) = "unique", UNIQUE[key]
        else:
            rtype, _, last = item.removeprefix("PT_HallRoom_").partition("_")
            if last in HILDIR:
                kind, key, theme = "boss", last, HILDIR[last]
            elif last in THEMES:
                kind, key, theme = ("boss" if rtype == "BossRoom" else "room"), None, last
            else:
                continue
        out.append({"id": item, "kind": kind, "type": rtype, "theme": theme, "key": key, "row": c})
    return out


def _theme_level(ctx: Ctx, theme: str) -> int:
    """A Theme's biome level (BiomeLevels.Of(HallsDefs.BiomeOf))."""
    biome = next(b for b, t in SOURCE_THEME.items() if t == theme)
    return next((b["level"] for b in ctx.loc.loot["biomes"] if b["id"] == biome), 1)


def _biome(ctx: Ctx, theme: str) -> str:
    return ctx.loc.text(f"@enc.hmap.biome.{theme.lower()}", theme)


def room_name(ctx: Ctx, r: dict) -> str:
    """HallMapItems.Name: a type and biome, a Hildir boss's hall, or a unique room's own name."""
    t = ctx.loc.text
    if r["kind"] == "unique":
        return t(f"@enc.hmap.unique.{r['key'].lower()}", r["key"])
    if r["key"]:
        return t(f"@enc.hmap.room.hildir.{r['key'].lower()}", r["key"])
    # A room without a line of its own: the code's English (L.Id's default), as in game.
    english = f"{ENGLISH_TYPE.get(r['type'], r['type'])} of {ENGLISH_OF[r['theme']]}"
    return t(f"@enc.hmap.room.{r['type'].lower()}.{r['theme'].lower()}", english)


def _level_biome(ctx: Ctx, level: int) -> str:
    """A land level as the halls' biome it belongs to (the highest whose level it reaches)."""
    found = THEMES[0]
    for theme in THEMES:
        if _theme_level(ctx, theme) <= level:
            found = theme
    return _biome(ctx, found)


def type_name(ctx: Ctx, rtype: str) -> str:
    return ctx.loc.text(f"@enc.hmap.type.{rtype.lower()}", rtype)


def room_link(ctx: Ctx, item: str, page: str) -> str:
    r = next((x for x in rooms(ctx) if x["id"] == item), None)
    if r is None:
        return item
    return f"[{room_name(ctx, r)}]({rel(ROOMS_PAGE, page)}#{item.lower()})"


def boss_of(ctx: Ctx, r: dict, page: str) -> str:
    """A boss room's boss (RoomDef.BossKey), linked to its boss page or row when it has one."""
    from .monster_pages import creature_link

    if r["key"]:
        return ctx.loc.text(f"@enc.hmap.boss.{r['key'].lower()}", r["key"])
    prefab = BIOME_BOSS[r["theme"]]
    if prefab in HALLS_BOSS_NAMES:
        return ctx.loc.text(HALLS_BOSS_NAMES[prefab], prefab)
    return creature_link(ctx, prefab, page)


def _shown(ctx: Ctx, fid: str) -> bool:
    from .formula_pages import shown

    return shown(ctx, fid)


def _values(fid: str) -> dict:
    from .formula_pages import _values as values

    return values().get(fid, {})


def _rechecking(ctx: Ctx) -> list[str]:
    ui = ctx.loc.ui
    return [f'!!! warning "{ui("formula.rechecking_title")}"', f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]


def _section(ctx: Ctx, fid: str, title: str, body, anchor: str | None = None) -> list[str]:
    """A section whose numbers the game computes (formulas/registry.toml): its body, or a note that
    it is being re-checked when its code changed."""
    head = [f"## {title} {{ #{anchor or fid} }}", ""]
    return head + (body(_values(fid)) if _shown(ctx, fid) else _rechecking(ctx))


def _num(v: float) -> str:
    return f"{v:g}"


def _round(v: float) -> float:
    """Mathf.Round (half to even, as Python's round)."""
    return float(round(v))


# ---- How the halls work -------------------------------------------------------------------------


def board_size(level: int, v: dict) -> tuple[int, int, int, int]:
    """HallMapKnobs.RoomsFor / SizeFor / MinPathOf: (cells for rooms, width, height, shortest way)."""
    import math

    lo, hi = v["level_low"], max(v["level_low"] + 1, v["level_high"])
    t = min(1.0, max(0.0, (level - lo) / (hi - lo)))
    cells = min(60, max(2, round(v["rooms_low"] + (v["rooms_high"] - v["rooms_low"]) * t)))
    share = min(0.95, max(0.2, v["open"]))
    w = min(v["w_max"], max(3, round(math.sqrt(cells / share))))
    h = min(v["h_max"] - 1, max(2, math.ceil(cells / (w * share)))) + 1
    return cells, w, h, max(1, min(v["min_path"], h - 2))


def tier_name(ctx: Ctx, tier: int) -> str:
    """HallsDefs.TierName, with its roman numeral (HallsDefs.TierRoman)."""
    name = ctx.loc.text(f"@enc.halls.tier{tier}", str(tier))
    return f"{('', 'I', 'II', 'III', 'IV')[tier]} · {name}" if tier else name


def page_halls(ctx: Ctx) -> dict[str, str]:
    if not rooms(ctx) or not ctx.data.loot.get("mapAffixes"):
        return {}
    NAV[:] = [("halls.how", HALLS_PAGE), ("halls.rooms_title", ROOMS_PAGE), ("halls.mods_title", MODIFIERS_PAGE)]
    return {HALLS_PAGE: _halls_page(ctx), ROOMS_PAGE: _rooms_page(ctx), MODIFIERS_PAGE: _modifiers_page(ctx)}


def _halls_page(ctx: Ctx) -> str:
    from .formula_pages import _anchor, FORMULA_PAGES

    ui, t, page = ctx.loc.ui, ctx.loc.text, HALLS_PAGE
    rooms_l, mods_l = rel(ROOMS_PAGE, page), rel(MODIFIERS_PAGE, page)
    book = t("@enc.hmap.book", "Book of the Halls")
    md = [f"# {ui('halls.title')}", "", ui("halls.intro", rooms=rooms_l, modifiers=mods_l), ""]

    md += [f"## {ui('halls.gates')} {{ #gates }}", "", ui("halls.gates_text"), ""]
    md += [f"> {t('@enc.hmap.gate-hint')}", ""]
    md += [ui("halls.lobby_text", book=book, merchant=f"[{t('@enc.hmap.merchant')}](#merchant)"), ""]
    hints = [(t(f"@enc.hmap.hugin.{i}.label"), t(f"@enc.hmap.hugin.{i}")) for i in range(1, 6)
             if f"@enc.hmap.hugin.{i}" in ctx.loc.game]
    if hints:
        md += [ui("halls.hugin", n=len(hints)), ""]
        md += [f"- **{label}:** {text}" for label, text in hints] + [""]

    def board(v):
        rows = []
        for theme in THEMES:
            level = _theme_level(ctx, theme)
            cells, w, h, path = board_size(level, v)
            rows.append([_biome(ctx, theme), str(level), str(cells), f"{w} × {h}", str(path)])
        out = [ui("halls.board_text", book=book), ""]
        formula = ui("halls.board_formula", low=_num(v["rooms_low"]), high=_num(v["rooms_high"]), from_=_num(v["level_low"]),
                     to=_num(v["level_high"]), open=_num(v["open"]))
        out += [f'<div class="pov-formula">{formula}</div>', ""]
        out += _table([ui("halls.gate_biome"), ui("halls.level"), ui("halls.cells"), ui("halls.board_size"), ui("halls.min_path")], rows)
        out += [ui("halls.board_rules", max=_num(v["max_rooms"])), ""]
        shapes = ", ".join(t(f"@enc.hmap.shape.{s}") for s in ("end", "line", "corner", "tee", "cross"))
        out += [ui("halls.placing", shapes=shapes), ""]
        out += [ui("halls.packing", modifiers=mods_l), ""]
        return out

    md += _section(ctx, "halls-board", ui("halls.book_title", book=book), board)

    md += [f"## {ui('halls.launch')} {{ #launch }}", "", ui("halls.launch_text", range=_num(_values("halls-board").get("party_range", 30))), ""]

    def fights(v):
        return [ui("halls.fights_text"), "",
                ui("halls.fights_numbers", mobs=_num(v["room_mobs"]), wave=_num(v["first_wave"]), cap=_num(v["cap"]),
                   elites=_num(v["elites"]), more=_num(v["party_count"] * 100), elite_per=_num(v["elite_per"]),
                   hp=_num(v["party_hp"] * 100), boss_hp=_num(v["party_boss_hp"] * 100)), "",
                ui("halls.fights_stars", elite=_num(v["elite_stars"]), chance=_num(v["elite_star_chance"] * 100), boss=_num(v["boss_stars"]),
                   crowned=f"{mods_l}#mod-boss-stars", host=f"{mods_l}#mod-stars-all"), ""]

    md += _section(ctx, "halls-fights", ui("halls.fights"), fights)
    md += [f"## {ui('halls.final')} {{ #final-boss }}", "",
           ui("halls.final_text", rooms=f"{rooms_l}#boss-rooms"), ""]

    death = ui("halls.deaths_text")
    if "permadeath" in FORMULA_PAGES:
        death += " " + ui("halls.deaths_single", link=_anchor("permadeath", page))
    md += [f"## {ui('halls.deaths')} {{ #deaths }}", "", death, ""]

    def points(v):
        levels = v["tier_levels"]
        rows = [[tier_name(ctx, 0), f"< {levels[0]}", ", ".join(_biome(ctx, th) for th in THEMES if _theme_level(ctx, th) < levels[0]), "—"]]
        for i, lv in enumerate(levels):
            upper = levels[i + 1] if i + 1 < len(levels) else None
            themes = [th for th in THEMES if _theme_level(ctx, th) >= lv and (upper is None or _theme_level(ctx, th) < upper)]
            rows.append([tier_name(ctx, i + 1), f"{lv}+", ", ".join(_biome(ctx, th) for th in themes), f"+{_num(v['per_tier'])}"])
        return [ui("halls.points_text", per=_num(v["per_tier"]), total=_num(v["per_tier"] * TIERS), ascendancy=rel(ASCENDANCY_PAGE, page)), "",
                *_table([ui("halls.tier"), ui("halls.gate_level"), ui("halls.gate_biomes"), ui("halls.points")], rows),
                ui("halls.points_who"), ""]

    md += _section(ctx, "halls-ascension", ui("halls.ascension"), points)

    def merchant(v):
        prices = [[_biome(ctx, th), _num(v["prices"][i])] for i, th in enumerate(THEMES[:-1])]
        renew = _currency_link(ctx, RENEW_RUNE, page)
        return [ui("halls.merchant_text", name=t("@enc.hmap.merchant"), count=_num(v["count"]), days=_num(v["days"]), rooms=rooms_l), "",
                ui("halls.merchant_renew", rune=renew), "",
                *_table([ui("halls.room_biome"), ui("halls.price")], prices)]

    md += _section(ctx, "halls-merchant", ui("halls.merchant"), merchant, anchor="merchant")
    return "\n".join(md + _footer(ctx))


def _currency_link(ctx: Ctx, item: str, page: str) -> str:
    from .gear_pages import currency_path

    info = ctx.loc.loot["items"].get(item)
    return f"[{info['name']}]({rel(currency_path(item), page)})" if info else item


# ---- Room items ---------------------------------------------------------------------------------


def _drops_where(ctx: Ctx, r: dict, page: str) -> str:
    """Where a room drops (LootDrops.CurrencyHere): its biome, the land level from which it drops,
    the kinds of enemies, the boss that must have fallen in the world."""
    ui, c, parts = ctx.loc.ui, r["row"], []
    for s in c.get("sources") or []:
        if s.startswith("biome:") and s[6:] in SOURCE_THEME:
            parts.append(ui("halls.drops_biome", biome=_biome(ctx, SOURCE_THEME[s[6:]])))
    if c.get("fromLevel") and not c.get("sources"):
        parts.append(ui("halls.drops_from", level=c["fromLevel"], biome=_level_biome(ctx, c["fromLevel"])))
    if kinds := c.get("kinds"):
        parts.append(ui("halls.drops_kinds", kinds=ui("halls.and").join(ui(f"halls.kind.{k}") for k in kinds)))
    if c.get("worldKey") and r["kind"] == "boss" and not r["key"]:
        parts.append(ui("halls.drops_defeated", boss=boss_of(ctx, r, page)))
    return "; ".join(parts) or "—"


def _price(ctx: Ctx, r: dict) -> str:
    """HallMapShop.Price by the room's biome; unique rooms are never sold (HallMapShop.Offerable).
    The Deep North has no price of its own (see the report)."""
    if r["kind"] == "unique":
        return ctx.loc.ui("halls.not_sold")
    prices = _values("halls-merchant").get("prices", [])
    i = THEMES.index(r["theme"])
    return _num(prices[i]) if i < len(prices) else "—"


def _anchor_cell(ctx: Ctx, r: dict) -> str:
    return f'<span id="{r["id"].lower()}"></span>**{room_name(ctx, r)}**'


def _rooms_page(ctx: Ctx) -> str:
    from .base_pages import _icon

    ui, t, page = ctx.loc.ui, ctx.loc.text, ROOMS_PAGE
    all_rooms = rooms(ctx)
    merchant = _shown(ctx, "halls-merchant")
    md = [f"# {ui('halls.rooms_title')}", "", ui("halls.rooms_intro", halls=rel(HALLS_PAGE, page), stack=_num(_values("halls-board").get("stack", 20))), ""]
    md += [f"> {t('@enc.hmap.tip.use')}", ""]

    def drops(v):
        from .gear_pages import CURRENCY_PAGE

        return [ui("halls.rooms_drops", currency=rel(CURRENCY_PAGE, page)), ""]

    md += _section(ctx, "halls-room-drops", ui("halls.rooms_drops_title"), drops)

    md += [f"## {ui('halls.types')} {{ #types }}", ""]
    md += _table(["", ui("halls.type"), ui("halls.contains")],
                 [[_icon(ctx, TYPE_SIGN[ty], page, 32) if ty in TYPE_SIGN else "", f"[**{type_name(ctx, ty)}**](#{'boss-rooms' if ty == 'BossRoom' else ty.lower()})",
                   t(f"@enc.hmap.gives.{ty.lower()}")] for ty in (*TYPES, "BossRoom")])

    head = [ui("halls.room"), ui("halls.drops_in"), ui("halls.weight")] + ([ui("halls.price")] if merchant else [])
    for ty in TYPES:
        rows = [[_anchor_cell(ctx, r), _drops_where(ctx, r, page), _num(r["row"]["weight"])] + ([_price(ctx, r)] if merchant else [])
                for r in all_rooms if r["kind"] == "room" and r["type"] == ty]
        if rows:
            md += [f"## {type_name(ctx, ty)} {{ #{ty.lower()} }}", "", t(f"@enc.hmap.gives.{ty.lower()}"), ""] + _table(head, rows)

    bosses = [r for r in all_rooms if r["kind"] == "boss"]
    if bosses:
        md += [f"## {type_name(ctx, 'BossRoom')} {{ #boss-rooms }}", "", t("@enc.hmap.gives.bossroom"), "", f"> {t('@enc.hmap.tip.top-cell')}", "",
               ui("halls.boss_rooms_text", final=rel(HALLS_PAGE, page) + "#final-boss"), ""]
        md += _table([ui("halls.room"), ui("halls.boss"), ui("halls.arena"), ui("halls.drops_in"), ui("halls.weight")]
                     + ([ui("halls.price")] if merchant else []),
                     [[_anchor_cell(ctx, r), boss_of(ctx, r, page), _biome(ctx, r["theme"]), _drops_where(ctx, r, page), _num(r["row"]["weight"])]
                      + ([_price(ctx, r)] if merchant else []) for r in bosses])

    uniques = [r for r in all_rooms if r["kind"] == "unique"]
    if uniques:
        md += [f"## {ui('halls.uniques')} {{ #unique-rooms }}", "", ui("halls.uniques_text"), ""]
        rows = []
        for r in uniques:
            rtype, theme, rule = UNIQUE[r["key"]]
            inside = t(f"@enc.hmap.rule.{rule}", rule)
            if r["key"] in UNIQUE_ITEMS:
                inside += f"<br>{_currency_link(ctx, UNIQUE_ITEMS[r['key']], page)}"
            flavor = t(f"@enc.hmap.unique.{r['key'].lower()}.flavor", "")
            rows.append([_anchor_cell(ctx, r) + (f"<br><small>*{flavor}*</small>" if flavor else ""),
                         f"{type_name(ctx, rtype)} · {_biome(ctx, theme)}", inside, _drops_where(ctx, r, page), _num(r["row"]["weight"])])
        md += _table([ui("halls.room"), ui("halls.type"), ui("halls.contains"), ui("halls.drops_in"), ui("halls.weight")], rows)
    md += [ui("halls.see_modifiers", link=rel(MODIFIERS_PAGE, page)), ""]
    return "\n".join(md + _footer(ctx))


# ---- Map modifiers ------------------------------------------------------------------------------


def _range(lo: float, hi: float) -> str:
    lo, hi = round(lo * 10) / 10, round(hi * 10) / 10
    return _num(hi) if lo == hi else f"{_num(lo)}–{_num(hi)}"


def affix_values(a: dict, i: int, side: str, v: dict | None) -> str:
    """HallMapAffixes.Values: a tier's numbers run from the next tier's (the last tier: its own ×0.8)
    up to its own, by the map's roll; "whole" rounds them, "tier" keeps the tier's own number.
    Without the formula's values (being re-checked) only the tier's own number is shown."""
    tiers = a["tiers"]
    nums = [x.get(side) for x in tiers]
    if nums[i] is None:
        return ""
    hi = nums[i]
    if v is None:
        return _num(hi)
    lo = nums[i + 1] if i + 1 < len(nums) and nums[i + 1] is not None else hi * v["last_floor"]
    how = a.get("bonusRound" if side == "bonus" else "dangerRound")
    if how == "tier":
        return _num(hi)
    if how == "whole":
        lo, hi = _round(lo), _round(hi)
    return _range(lo, hi)


def affix_anchor(a: dict) -> str:
    return f"mod-{a['id']}"


def _affix_line(ctx: Ctx, a: dict, key: str, text: str, i: int, v: dict | None) -> str:
    """A modifier's reward or danger line, its numbers shown as the tier's range."""
    line = ctx.loc.text(f"@enc.hmap.affix.{a['id']}.{key}", text or "")
    if not line:
        return ""
    bonus, danger = affix_values(a, i, "bonus", v), affix_values(a, i, "danger", v)
    return line.replace("{0}", bonus if key == "bonus" else danger).replace("{1}", danger if key == "bonus" else bonus)


def _modifiers_page(ctx: Ctx) -> str:
    ui, t, page = ctx.loc.ui, ctx.loc.text, MODIFIERS_PAGE
    affixes = ctx.data.loot["mapAffixes"]
    md = [f"# {ui('halls.mods_title')}", "", ui("halls.mods_intro", halls=rel(HALLS_PAGE, page) + "#halls-board"), ""]
    md += [f"> {t('@enc.hmap.rune-hint')}", ""]

    def grades(v):
        out = [ui("halls.grades_text", max=_num(v["max"])), ""]
        out += _table([ui("halls.grade"), ui("halls.modifiers")],
                      [[t("@enc.hmap.grade.normal"), "0"], [t("@enc.hmap.grade.magic"), f"1–{_num(v['magic_max'])}"],
                       [t("@enc.hmap.grade.rare"), f"{_num(v['magic_max'] + 1)}–{_num(v['max'])}"]])
        out += [f"### {ui('halls.runes')} {{ #runes }}", "", ui("halls.runes_text"), ""]
        out += _table(["", ui("halls.rune_col"), ui("halls.on_map")],
                      [[_rune_icon(ctx, r, page), _currency_link(ctx, r, page), ui(f"halls.rune.{r}", max=_num(v["max"]))]
                       for r in MAP_RUNES if r in ctx.loc.loot["items"]])
        out += [f"### {ui('halls.rolls')} {{ #rolls }}", "", ui("halls.rolls_text", floor=_num(v["last_floor"] * 100)), ""]
        tiers = affixes[0]["tiers"]
        out += _table([ui("halls.tier"), ui("halls.min_level"), ui("halls.tier_weight")],
                      [[x["id"], f"{x['minLevel']} <small>({_level_biome(ctx, x['minLevel'])})</small>", _num(x["weight"])] for x in tiers])
        return out

    md += _section(ctx, "halls-map-modifiers", ui("halls.grades"), grades)
    # The modifiers themselves are the catalog's: shown always, their numbers as ranges once the
    # rules above are checked (else each tier's own number).
    ranges = _values("halls-map-modifiers") if _shown(ctx, "halls-map-modifiers") else None
    md += [f"## {ui('halls.mods_list')} {{ #modifiers }}", ""]
    for a in affixes:
        md += _affix_section(ctx, a, ranges)
    md += [ui("halls.see_rooms", link=rel(ROOMS_PAGE, page)), ""]
    return "\n".join(md + _footer(ctx))


def _rune_icon(ctx: Ctx, item: str, page: str) -> str:
    from .base_pages import _icon

    return _icon(ctx, item, page, 32)


def _affix_section(ctx: Ctx, a: dict, v: dict | None) -> list[str]:
    ui, t = ctx.loc.ui, ctx.loc.text
    name = t(f"@enc.hmap.affix.{a['id']}", a["name"])
    md = [f"### {name} {{ #{affix_anchor(a)} }}", ""]
    facts = [ui("halls.mod_weight", weight=_num(a["weight"]))]
    if needs := a.get("needs"):
        facts.append(ui(f"halls.needs.{needs}", room=_needs_room(ctx, needs)))
    md += ["; ".join(facts) + ".", ""]
    rows = []
    for i, x in enumerate(a["tiers"]):
        rows.append([x["id"], str(x["minLevel"]), _num(x["weight"]), _affix_line(ctx, a, "bonus", a.get("text"), i, v),
                     _affix_line(ctx, a, "danger", a.get("dangerText"), i, v) or "—"])
    md += _table([ui("halls.tier"), ui("halls.min_level"), ui("halls.tier_weight"), ui("halls.reward"), ui("halls.danger")], rows)
    return md


def _needs_room(ctx: Ctx, needs: str) -> str:
    """HallMapAffixes.Needs: a room type on the map, linked to its rooms."""
    rtype = {"OreHall": "OreHall", "Burial": "Burial"}.get(needs)
    return f"[{type_name(ctx, rtype)}]({rel(ROOMS_PAGE, MODIFIERS_PAGE)}#{rtype.lower()})" if rtype else ""


# ---- Links from other pages ---------------------------------------------------------------------


def currency_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """On a currency page: what a map rune does to a map of the halls, the Rune of Renewed Trade's
    room merchant, or the unique room a reward comes from."""
    if not rooms(ctx) or not ctx.data.loot.get("mapAffixes"):
        return []
    ui = ctx.loc.ui
    if item in MAP_RUNES:
        if not _shown(ctx, "halls-map-modifiers"):  # its effect is being re-checked: the link only
            more = ui("halls.on_map_more", link=rel(MODIFIERS_PAGE, page) + "#halls-map-modifiers")
            return [f"## {ui('halls.on_map_title')}", "", more, ""]
        more = ui("halls.on_map_more", link=rel(MODIFIERS_PAGE, page) + "#runes")
        v = _values("halls-map-modifiers")
        return [f"## {ui('halls.on_map_title')}", "", ui(f"halls.rune.{item}", max=_num(v["max"])) + " " + more, ""]
    if item == RENEW_RUNE:
        return [f"## {ui('halls.title')}", "",
                ui("halls.renew_back", merchant=f"[{ctx.loc.text('@enc.hmap.merchant')}]({rel(HALLS_PAGE, page)}#merchant)"), ""]
    found = [k for k, it in UNIQUE_ITEMS.items() if it == item]
    if found:
        links = ", ".join(room_link(ctx, f"PT_HallRoomU_{k}", page) for k in found)
        return [f"## {ui('halls.title')}", "", ui("halls.reward_back", rooms=links), ""]
    return []


def bosses_note(ctx: Ctx, page: str) -> list[str]:
    """On the bosses page: every biome boss has a boss room in the halls."""
    if not rooms(ctx):
        return []
    return [ctx.loc.ui("halls.bosses_back", rooms=rel(ROOMS_PAGE, page) + "#boss-rooms", halls=rel(HALLS_PAGE, page)), ""]
