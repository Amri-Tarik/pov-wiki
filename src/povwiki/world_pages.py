"""World: treasure maps, burial ships and merchants (6.0).

- Treasure maps (PassiveTree.Encounters.TreasureMaps, TreasureMapCache, TreasureMapKinds): a
  currency row of the loot catalog (PoV_TreasureMap) that becomes a map of one of nine kinds
  (LootDrops.RollTreasureKind over the catalog's "treasureKind" tables), leading to a buried chest
  in the land of the map's level (TreasureMaps.TargetBiome, Find, FindWide, Valid). The chest holds
  the kind's loot (LootDrops.TreasureRewards, Kept); only the map's bearer opens it
  (TreasureMapCache.Interact).
- Burial ships (BurialShip, HallsParty.Ship*): sealed drakkars with one of six cargos, waves of the
  dead and a final guardian; the cargo decides the gifts (BurialShip.LootKind, Rolls).
- Merchants (Merchants, RagnStall, Sigrid, SigridDirector, Wanderer, WandererDirector, Finds,
  HallMapShop.ServerRenew): Ragn's gamble by kind, Sigrid's visits, the Keeper's six unique
  gifts, the finds of Haldor, Hildir and the Bog Witch, and the Rune of Renewed Trade.

Numbers written inline in the code (the mod's tunables and constants) are in the registry's
"values" of formulas treasure-maps, burial-ships and merchants; a section that depends on them
is hidden while its code is being re-checked (povwiki.formulas).
"""

from .markup import rel
from .pages import Ctx, _footer, _img, _table

TREASURE_PAGE = "world/treasure-maps.md"
SHIPS_PAGE = "world/burial-ships.md"
MERCHANTS_PAGE = "world/merchants.md"
# TreasureMaps.MapName: the lands a treasure can lie in (TreasureMaps.Lands), Valheim's Biome names.
_LANDS = ("Meadows", "BlackForest", "Swamp", "Mountain", "Plains", "Mistlands", "AshLands")
# BurialShip.Cargo, in enum order (BurialShip.Place: Cargo random 0..5).
_CARGOS = ("warrior", "guard", "smith", "runecarver", "seafarer", "jarl")
# BurialShip.Hazard 1..4 and their name keys (BurialShip.HazardName).
_HAZARDS = ("embers", "barrow", "cold", "chains")
# Merchants.Cat, in enum order, and their price group (Merchants.GroupOf).
_CATS = ("sword", "axe", "club", "spear", "atgeir", "knife", "bow", "crossbow", "staff", "shield",
         "helmet", "chest", "legs", "cape", "belt", "ring", "trinket")
_GROUPS = {"shield": "shield", **{c: "armour" for c in ("helmet", "chest", "legs", "cape")},
           **{c: "jewel" for c in ("belt", "ring", "trinket")}}
# Wanderer.KindName keys.
_GIFT_KINDS = ("weapon", "armour", "ring", "belt", "trinket", "jewel", "other")


def available(data) -> bool:
    """The world section exists from 6.0: the catalog has treasure map kinds."""
    return any(t.get("treasureKind") for t in data.loot.get("tables") or [])


# ---- Helpers ------------------------------------------------------------------------------------


def _values(fid: str) -> dict:
    from .formula_pages import _values as values

    return values().get(fid, {})


def _gate(ctx: Ctx, fid: str) -> list[str] | None:
    """None when a formula's code is as checked; else the note that it is being re-checked."""
    from .formula_pages import shown

    if shown(ctx, fid):
        return None
    ui = ctx.loc.ui
    return [f'!!! warning "{ui("formula.rechecking_title")}"', f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]


def _g(ctx: Ctx, key: str) -> str:
    """Game text by the mod's localisation key (without the "@")."""
    return ctx.loc.text(f"@{key}")


def _n(v: float) -> str:
    return f"{round(v, 2):g}"


def _pct(v: float) -> str:
    return f"{round(v * 100, 2):g}%"


def _round_half_even(v: float) -> int:
    """Mathf.RoundToInt: halves go to the even number (as Python's round)."""
    return int(round(v))


def _biomes(ctx: Ctx) -> list[dict]:
    """Progression biomes with their level (Ocean shares Mistlands' level: left out)."""
    return [b for b in ctx.loc.loot["biomes"] if b["id"] != "Ocean"]


def _biome(ctx: Ctx, biome_id: str) -> str:
    return ctx.loc.vkey(f"biome_{biome_id.lower()}", biome_id)


def _level_of(ctx: Ctx, biome_id: str) -> int:
    return next((b["level"] for b in ctx.loc.loot["biomes"] if b["id"] == biome_id), 1)


def _icon(ctx: Ctx, image: str, page: str, px: int) -> str:
    return _img(ctx.icons.path(image), page, px) if ctx.icons else ""


def _item(ctx: Ctx, prefab: str, page: str, px: int = 24) -> str:
    """An item's icon and name, linked to its page (currency, base) when it has one."""
    from .base_pages import _icon as item_icon, _item_name, base_path, bases
    from .gear_pages import currency_path

    name = _item_name(ctx, prefab)
    if name == prefab:  # the mod's items it names in its own strings (alloys, glyphs, gems)
        name = ctx.loc.text(f"@item.{prefab}.name", prefab)
    if prefab in (ctx.loc.loot.get("items") or {}):
        name = f"[{name}]({rel(currency_path(prefab), page)})"
    elif prefab in bases(ctx):
        name = f"[{name}]({rel(base_path(prefab), page)})"
    return f'<span class="pov-inline">{item_icon(ctx, prefab, page, px)}{name}</span>'


def _craft(ctx: Ctx) -> Ctx | None:
    from .pages import CRAFTING

    return next((t for t in ctx.trees or [] if t.spec is CRAFTING), None)


def _term(ctx: Ctx, key: str, page: str, start: bool = False) -> str:
    from .formula_pages import _term as term

    return term(ctx, key, page, start=start)


def _creature(ctx: Ctx, prefab: str, page: str) -> str:
    from .monster_pages import _named

    return _named(ctx, prefab, page, 24)


# ---- Treasure maps ------------------------------------------------------------------------------


def _kinds(ctx: Ctx) -> list[dict]:
    """The catalog's treasure map tables (LootCatalog: "treasureKind", "kindWeight"), in the order
    of LootDrops.TreasureKinds."""
    tables = {t["treasureKind"]: t for t in ctx.data.loot.get("tables") or [] if t.get("treasureKind")}
    return [tables[k] for k in ("weapons", "armour", "currency", "alloys", "runes", "jewellery", "jewels", "gems", "unique") if k in tables]


def kind_anchor(kind: str) -> str:
    return f"map-{kind}"


def _treasure_sources(ctx: Ctx) -> list[str]:
    row = next((c for c in ctx.data.loot.get("currency") or [] if c["id"] == "PoV_TreasureMap"), None)
    return list((row or {}).get("kinds") or [])


def _extra_nodes(ctx: Ctx) -> list[dict]:
    """Craft tree nodes with an extra chance of a treasure map (Stat.ExtraChance on TreasureMaps)."""
    craft = _craft(ctx)
    if craft is None:
        return []
    return [n for n in craft.tree_nodes
            if any(m.get("stat") == "ExtraChance" and "TreasureMaps" in (m.get("subjects") or [m.get("subject")]) for m in n.get("mods") or [])]


def _treasure_page(ctx: Ctx) -> str:
    from .pages import PAGE_SIZES, _effect, _name, _node_art

    ui, page = ctx.loc.ui, TREASURE_PAGE
    kinds = _kinds(ctx)
    md = [f"# {ui('world.tmap.title')}", "", ui("world.tmap.intro", chest=_g(ctx, "enc.tmap.chest")), "",
          f"> *{_g(ctx, 'enc.tmap.desc')}*", ""]

    # Where they drop: the catalog's currency row, the craft tree's extra chances, Sigrid.
    md += [f"## {ui('world.tmap.drops')} {{ #drops }}", ""]
    row = next((c for c in ctx.data.loot.get("currency") or [] if c["id"] == "PoV_TreasureMap"), None)
    sources = ", ".join(ui(f"world.source.{s}") for s in _treasure_sources(ctx))
    if row:
        from .formula_pages import LOOT_PAGE

        md += [ui("world.tmap.drops_text", sources=sources, weight=_n(row["weight"]), loot=f"{rel(LOOT_PAGE, page)}#loot"), ""]
    md += [ui("world.tmap.drops_more", merchants=f"{rel(MERCHANTS_PAGE, page)}#sigrid", ships=rel(SHIPS_PAGE, page)), ""]
    nodes = _extra_nodes(ctx)
    craft = _craft(ctx)
    if nodes and craft:
        # Their sectors (crafttree.json "branch"): kills on the timber side, chests on the forge side.
        sector = {kind: next((craft.sector_names.get(n.get("branch"), n.get("branch")) for n in nodes
                              if any(kind in (m.get("subjects") or []) for m in n.get("mods") or [])), "")
                  for kind in ("FromKills", "FromChests")}
        md += [f"### {ui('world.tmap.extra')} {{ #extra }}", "",
               ui("world.tmap.extra_text", timber=sector["FromKills"], forge=sector["FromChests"]), ""]
        rows = [[_node_art(craft, n, page, 40), _name(craft, n, page), _effect(craft, page, n["r"])]
                for n in sorted(nodes, key=lambda n: (n["size"] not in PAGE_SIZES, n["r"]["title"]))]
        md += _table(["", ui("col.name"), ui("col.effect")], rows)

    # The nine kinds.
    example = f"{_g(ctx, 'enc.tmap.kind.weapons')} · {_g(ctx, 'enc.tmap.biome.swamp')}"
    md += [f"## {ui('world.tmap.kinds')} {{ #kinds }}", "", ui("world.tmap.kinds_text", example=example), ""]
    gate = _gate(ctx, "treasure-maps")
    total = sum(t.get("kindWeight", 0) for t in kinds) or 1
    rows = []
    for t in kinds:
        k = t["treasureKind"]
        rows.append([f'<span id="{kind_anchor(k)}"></span>' + _icon(ctx, f"PassiveTree.item.PoV_TreasureMap_{k}.png", page, 40),
                     f"**{_g(ctx, f'enc.tmap.kind.{k}')}**", _g(ctx, f"enc.tmap.holds.{k}"),
                     "—" if gate else _pct(t.get("kindWeight", 0) / total)])
    md += _table(["", ui("col.name"), ui("world.tmap.holds"), ui("world.tmap.chance")], rows)

    md += [f"## {ui('world.tmap.chest_title')} {{ #chest }}", ""]
    if gate:
        md += gate
    else:
        v = _values("treasure-maps")
        md += [ui("world.tmap.chest_level"), "",
               ui("world.tmap.chest_text", rarity=_pct(v["rarity"]), quantity=_term(ctx, "chest-item-quantity", page),
                  chest_rarity=_term(ctx, "chest-item-rarity", page), n=v["spill"]), ""]
        md += [ui("world.tmap.rule_kept"), ""]
        md += [f"- {ui(f'world.tmap.kept.{k}')}" for k in ("weapons", "armour", "jewellery", "jewels", "gems", "currency", "runes", "alloys")]
        md += [f"- {ui('world.tmap.rule_unique', unique=_g(ctx, 'enc.tmap.kind.unique'))}", ""]
        for t in kinds:
            entries = t.get("entries") or []
            if not entries or not t.get("attempts"):
                continue
            k = t["treasureKind"]
            weights = sum(e["weight"] for e in entries) or 1
            md += [f"### {_g(ctx, f'enc.tmap.kind.{k}')}", "",
                   ui("world.tmap.entries", n=_n(t["attempts"]), chance=_pct(t.get("chance", 1))), ""]
            md += _table([ui("world.item"), ui("world.amount"), ui("world.share")],
                         [[_item(ctx, e["id"], page), _amount(e), _pct(e["weight"] / weights)]
                          for e in sorted(entries, key=lambda e: -e["weight"])])

    # Where the treasure lies.
    md += [f"## {ui('world.tmap.place')} {{ #place }}", ""]
    if gate:
        md += gate
    else:
        v = _values("treasure-maps")
        md += [ui("world.tmap.place_biome"), ""]
        lands = [b for b in _biomes(ctx) if b["id"] in _LANDS]
        rows = []
        for i, b in enumerate(lands):
            hi = lands[i + 1]["level"] - 1 if i + 1 < len(lands) else None
            rows.append([f"{b['level']}–{hi}" if hi else f"{b['level']}+", _biome(ctx, b["id"]),
                         _g(ctx, f"enc.tmap.name.{b['id'].lower()}"), str(b["level"])])
        md += _table([ui("world.tmap.map_level"), ui("bosses.biome"), ui("world.tmap.map_name"), ui("world.tmap.reward_level")], rows)
        md += [ui("world.tmap.place_text", near=_n(v["near"]), far=_n(v["far"]), location=_n(v["location_margin"]),
                  build=_n(v["build_clear"]), gap=_n(v["treasure_gap"]), edge=_n(v["edge"])), "",
               ui("world.tmap.place_wide", step=_n(v["wide_step"]), max=_n(v["wide_max"])), "",
               ui("world.tmap.moved", text=_g(ctx, "enc.tmap.moved")), ""]

    md += [f"## {ui('world.tmap.open')} {{ #open }}", "",
           ui("world.tmap.open_text", dig=_g(ctx, "enc.tmap.dig"), bearer=_g(ctx, "enc.tmap.bearer-only"),
              read=_g(ctx, "enc.tmap.read-name"), lost=_g(ctx, "enc.tmap.lost"), other=_g(ctx, "enc.tmap.other-world")), ""]
    return "\n".join(md + _footer(ctx))


def _amount(e: dict) -> str:
    lo, hi = e.get("stackMin", 1), e.get("stackMax", 1)
    return f"{lo}–{hi}" if hi > lo else str(lo)


# ---- Burial ships -------------------------------------------------------------------------------


def _roster(level: int, wave: int, waves: int, ash: int, swamp: int) -> tuple[list[str], str]:
    """BurialShip.Roster: the dead a wave draws from (repeats weigh more), and the guardian."""
    late, mid = level >= ash, level >= swamp
    guardian = "Charred_Melee" if late else "Draugr_Elite" if mid else "Skeleton"
    if wave == 1:
        return (["Charred_Melee", "Charred_Archer"] if late else ["Skeleton", "Skeleton", "Skeleton_Poison"]), guardian
    if wave < waves:
        if late:
            return ["Charred_Melee", "Charred_Archer", "Charred_Mage", "Charred_Twitcher"], guardian
        return (["Skeleton", "Ghost", "Draugr", "Draugr_Ranged", "Wraith"] if mid else ["Skeleton", "Skeleton", "Ghost"]), guardian
    if late:
        return ["Charred_Melee", "Charred_Archer"], guardian
    return (["Draugr", "Draugr_Ranged", "Skeleton"] if mid else ["Skeleton", "Skeleton_Poison"]), guardian


def _ship_page(ctx: Ctx) -> str:
    ui, page = ctx.loc.ui, SHIPS_PAGE
    md = [f"# {ui('world.ship.title')}", "", ui("world.ship.intro", name=_g(ctx, "enc.ship.name")), ""]
    gate = _gate(ctx, "burial-ships")
    if gate:
        return "\n".join(md + gate + _footer(ctx))
    v = _values("burial-ships")
    md += [ui("world.ship.where", chance=_pct(v["per_zone"]), discover=_n(v["discover"])), "",
           ui("world.ship.level", undead=_term(ctx, "undead", page)), ""]

    md += [f"## {ui('world.ship.cargo')} {{ #cargo }}", "", ui("world.ship.cargo_text"), ""]
    rows = []
    for c in _CARGOS:
        lo, hi = v["rolls"][c]
        rows.append([f"**{_g(ctx, f'enc.ship.cargo.{c}')}**", ui(f"world.ship.gives.{c}"), f"{lo}–{hi}",
                     ui(f"world.ship.bonus.{c}", rarity=_pct(v["jarl_rarity"])) if ui(f"world.ship.bonus.{c}") != f"world.ship.bonus.{c}" else "—"])
    md += _table([ui("world.ship.cargo_col"), ui("world.ship.gifts"), ui("world.ship.rolls"), ui("world.ship.bonus_col")], rows)
    md += [ui("world.ship.rolls_text", quantity=_term(ctx, "chest-item-quantity", page), rarity=_term(ctx, "chest-item-rarity", page)), ""]
    mats = v.get("materials") or []
    if mats:
        md += [f"### {_g(ctx, 'enc.ship.cargo.smith')}", "", ui("world.ship.smith_text"), ""]
        md += _table([ui("world.item"), ui("world.amount"), ui("world.from_level")],
                     [[_item(ctx, m["id"], page), f"{m['min']}–{m['max']}", f"{m['level']} ({_biome_at(ctx, m['level'])})"] for m in mats])
    md += [ui("world.ship.coins", base=f"{v['coins'][0]}–{v['coins'][1]}", per=_n(v["coins_per"])), ""]
    gate_rune = "PT_RuneOpenGate"
    rune = _item(ctx, gate_rune, page) if gate_rune in (ctx.loc.loot.get("items") or {}) else ""
    if rune:
        md += [ui("world.ship.open_gate", chance=_pct(v["open_gate"]), rune=rune), ""]

    md += [f"## {ui('world.ship.hazards')} {{ #hazards }}", "",
           ui("world.ship.hazards_text", chance=_pct(v["hazard_chance"]), rarity=_pct(v["hazard_rarity"]),
              quantity=_pct(v["hazard_quantity"]), barrow=_pct(v["barrow_quantity"]),
              barrow_name=_g(ctx, "enc.ship.hazard.barrow").split(":")[0]), ""]
    md += [f"- {_g(ctx, f'enc.ship.hazard.{h}')}" for h in _HAZARDS] + [""]

    md += [f"## {ui('world.ship.waves')} {{ #waves }}", "",
           ui("world.ship.waves_text", four=_pct(v["four_waves"]), wake=_g(ctx, "enc.ship.wake"), pause=_n(v["wave_pause"])), "",
           ui("world.ship.wave_size", base=v["wave_size"], more=_pct(v["party_count"]), cap=v["party_cap"]), ""]
    sizes = [[ui("world.ship.wave_n", n=w), *(str(_wave(v, w, p)) for p in (1, 2, 3, 4))] for w in (1, 2, 3, 4)]
    md += _table([ui("world.ship.wave"), *(ui("world.ship.players", n=p) for p in (1, 2, 3, 4))], sizes)
    md += [ui("world.ship.guardian", per=_n(v["elite_per"]), barrow=_g(ctx, "enc.ship.hazard.barrow").split(":")[0]), ""]
    ash, swamp = _level_of(ctx, "AshLands"), _level_of(ctx, "Swamp")
    rows = []
    for b in _biomes(ctx):
        lvl = b["level"]
        first, guardian = _roster(lvl, 1, 3, ash, swamp)
        middle, _ = _roster(lvl, 2, 3, ash, swamp)
        last, _ = _roster(lvl, 3, 3, ash, swamp)
        rows.append([f"{_biome(ctx, b['id'])} ({lvl})", *(_mix(ctx, r, page) for r in (first, middle, last)), _creature(ctx, guardian, page)])
    md += _table([ui("bosses.biome"), ui("world.ship.first"), ui("world.ship.middle"), ui("world.ship.last"), ui("world.ship.guardian_col")], rows)
    md += [ui("world.ship.rules", leash=_n(v["leash"]), leave=_n(v["leave"])), ""]
    md += [f"## {ui('world.ship.gifts_title')} {{ #gifts }}", "", ui("world.ship.gifts_text", take=_g(ctx, "enc.ship.take")), ""]
    return "\n".join(md + _footer(ctx))


def _wave(v: dict, wave: int, players: int) -> int:
    """HallsParty.ShipWave: the first wave's size plus one per wave after it, grown per extra
    player (HallsParty.Count), between 2 and the cap."""
    grow = 1 + max(0.0, v["party_count"]) * (max(1, players) - 1)
    return min(max(2, max(1, _round_half_even((v["wave_size"] + wave - 1) * grow))), max(2, v["party_cap"]))


def _mix(ctx: Ctx, roster: list[str], page: str) -> str:
    """A roster's creatures with their share (BurialShip.Spawn draws one at random per spawn).
    Creatures Valheim names alike (Draugr and its archer) share a line."""
    shares: dict[str, tuple[str, int]] = {}
    for prefab in roster:
        name = ctx.loc.creature(prefab)
        first, n = shares.get(name, (prefab, 0))
        shares[name] = (first, n + 1)
    return "<br>".join(f"{_creature(ctx, first, page)} {_pct(n / len(roster))}" for first, n in shares.values())


def _biome_at(ctx: Ctx, level: int) -> str:
    from .item_pages import biome

    return biome(ctx, level)


# ---- Merchants ----------------------------------------------------------------------------------


def _price(base: float, level: int, per: float) -> int:
    """Merchants.Price, Sigrid's Price: the base grown per level of the place, to 5 coins."""
    return max(5, _round_half_even(base * (1 + max(0, level) * per) / 5) * 5)


# Sigrid.EarlyGoods: what she sells when no material her roll finds is known in the world.
_EARLY_GOODS = (("Flint", 10, 20), ("LeatherScraps", 10, 20), ("DeerHide", 5, 10), ("Resin", 10, 20))


def _merchants_page(ctx: Ctx) -> str:
    ui, page, vk = ctx.loc.ui, MERCHANTS_PAGE, ctx.loc.vkey
    md = [f"# {ui('world.merch.title')}", "", ui("world.merch.intro"), ""]
    gate = _gate(ctx, "merchants")
    v = _values("merchants")
    biomes = _biomes(ctx)

    # Ragn Bone-Lot.
    md += [f"## {_g(ctx, 'enc.ragn.name')} {{ #ragn }}", "", f"*{_g(ctx, 'enc.ragn.what')}*", ""]
    if gate:
        md += gate
    else:
        md += [ui("world.merch.ragn_where", cell=_n(v["ragn_cell"]), chance=_pct(v["ragn_chance"]), discover=_n(v["ragn_discover"])), "",
               ui("world.merch.ragn_how", rule=_g(ctx, "enc.ragn.rule")), ""]
        odds = v["ragn_odds"]
        md += _table([ui("world.merch.rarity"), ui("world.share")],
                     [[ui(f"world.rarity.{r}"), _pct(odds[i] / sum(odds))] for i, r in enumerate(("common", "magic", "rare", "unique"))])
        rune = _item(ctx, "PT_RuneOpenGate", page) if "PT_RuneOpenGate" in (ctx.loc.loot.get("items") or {}) else ""
        md += [ui("world.merch.ragn_odds", trinket=_g(ctx, "enc.ragn.trinket-cap"), gate=_pct(v["ragn_open_gate"]), rune=rune), ""]
        groups = ("weapon", "shield", "armour", "jewel")
        md += [f"### {ui('world.merch.prices')}", "", ui("world.merch.prices_text", per=_pct(v["price_level"])), ""]
        md += _table([ui("world.merch.kind"), *(f"{_biome(ctx, b['id'])} ({b['level']})" for b in biomes)],
                     [[ui(f"world.merch.group.{g}") + f"<br><small>{', '.join(_g(ctx, f'enc.merch.cat.{c}') for c in _CATS if _GROUPS.get(c, 'weapon') == g)}</small>",
                       *(str(_price(v["price"][g], b["level"], v["price_level"])) for b in biomes)] for g in groups])

    # Sigrid Far-Road.
    md += [f"## {_g(ctx, 'enc.sig.name')} {{ #sigrid }}", "", f"*{_g(ctx, 'enc.sig.hint')}*", ""]
    if gate:
        md += gate
    else:
        md += [ui("world.merch.sigrid_when", pause=_n(v["sigrid_pause"]), chance=_pct(v["sigrid_chance"]), stay=_n(v["sigrid_stay"]),
                  near=_n(v["sigrid_min"]), far=_n(v["sigrid_max"]), merge=_n(v["sigrid_bed_merge"]), active=_n(v["sigrid_active"]),
                  buyer=_n(v["sigrid_buyer"])), "",
               ui("world.merch.sigrid_level"), "",
               ui("world.merch.sigrid_stock", maps=rel(TREASURE_PAGE, page)), ""]
        rows = [[ui("world.merch.sigrid_gear"), "3", ui("world.merch.sigrid_gear_price", base=_n(v["sigrid_gear"]), rare=_n(v["sigrid_rare"]), legendary=_n(v["sigrid_legendary"]))],
                [ui("world.merch.sigrid_currency"), "3", ui("world.merch.sigrid_currency_price", base=_n(v["sigrid_rune"]))],
                [ui("world.merch.sigrid_materials"), "2", ui("world.merch.sigrid_material_price", base=_n(v["sigrid_res"]))],
                [f"[{ui('world.tmap.title_one')}]({rel(TREASURE_PAGE, page)})", "1", ui("world.merch.sigrid_map_price", base=_n(v["sigrid_map"]))]]
        md += _table([ui("world.merch.goods"), ui("world.merch.count"), ui("world.merch.price")], rows)
        early = ", ".join(f"{_item(ctx, i, page)} ×{lo}–{hi}" for i, lo, hi in _EARLY_GOODS)
        md += [ui("world.merch.sigrid_materials_note", tries=_n(v["sigrid_material_tries"]), early=early), ""]
        md += [ui("world.merch.sigrid_prices", per=_pct(v["sigrid_price_level"])), ""]
        md += _table([ui("world.merch.level"), ui("world.tmap.title_one"), ui("world.merch.sigrid_gear_magic")],
                     [[f"{_biome(ctx, b['id'])} ({b['level']})", str(_price(v["sigrid_map"], b["level"], v["sigrid_price_level"])),
                       str(_price(v["sigrid_gear"], b["level"], v["sigrid_price_level"]))] for b in biomes])

    # The Keeper of Forgotten Sagas.
    md += [f"## {_g(ctx, 'enc.wand.name')} {{ #keeper }}", "", f"*{_g(ctx, 'enc.wand.hint')}*", ""]
    if gate:
        md += gate
    else:
        md += [ui("world.merch.keeper_text", sub=_g(ctx, "enc.wand.sub"), uniques=rel("items/uniques.md", page),
                  per=_n(v["keeper_per_offer"]), least=_n(v["keeper_offers_min"]), most=_n(v["keeper_offers_max"]),
                  kinds=", ".join(_g(ctx, f"enc.wand.kind.{k}").lower() for k in _GIFT_KINDS[:-1])), "",
               ui("world.merch.keeper_where", near=_n(v["keeper_move_min"] / 2), min=_n(v["keeper_move_min"]), max=_n(v["keeper_move_max"]),
                  clear=_n(v["keeper_base_clear"]), linger=_n(v["keeper_linger"]), leave=_n(v["keeper_leave"]), discover=_n(v["keeper_discover"])), ""]

    # Haldor, Hildir and the Bog Witch.
    names = ", ".join(vk(k) for k in ("npc_haldor", "npc_hildir")) + " " + ui("world.and") + " " + vk("npc_bogwitch")
    md += [f"## {ui('world.merch.finds_title', names=names)} {{ #finds }}", ""]
    if gate:
        md += gate
    else:
        md += [ui("world.merch.finds_text", lo=_n(v["finds_min"]), hi=_n(v["finds_max"]), days=_n(v["finds_days"]),
                  unique=_pct(v["finds_unique"]), rare=_pct(v["finds_rare"]), one=_g(ctx, "enc.finds.one"),
                  locked=_g(ctx, "enc.finds.locked"), tab=_g(ctx, "enc.finds.tab")), "",
               ui("world.merch.finds_price", magic=_n(v["finds_magic"]), rare=_n(v["finds_rare_x"]), unique=_n(v["finds_unique_x"]),
                  ragn="#ragn"), ""]

    # The Rune of Renewed Trade.
    rune = "PT_RuneOfRenewedTrade"
    if rune in (ctx.loc.loot.get("items") or {}):
        info = ctx.loc.loot["items"][rune]
        md += [f"## {info['name']} {{ #renewal }}", "", _item(ctx, rune, page, 32), "", f"*{info.get('action') or ''}*", "",
               ui("world.merch.renew_text", ragn=_g(ctx, "enc.hmap.renew.ragn")), ""]
    return "\n".join(md + _footer(ctx))


# ---- Pages --------------------------------------------------------------------------------------


def page_world(ctx: Ctx) -> dict[str, str]:
    if not available(ctx.data):
        return {}
    return {TREASURE_PAGE: _treasure_page(ctx), SHIPS_PAGE: _ship_page(ctx), MERCHANTS_PAGE: _merchants_page(ctx)}


def renewal_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """For the Rune of Renewed Trade's own page: the merchants it renews."""
    if item != "PT_RuneOfRenewedTrade" or not available(ctx.data):
        return []
    return [f"## {ctx.loc.ui('world.merch.title')}", "", ctx.loc.ui("world.merch.renew_link", link=f"{rel(MERCHANTS_PAGE, page)}#renewal"), ""]
