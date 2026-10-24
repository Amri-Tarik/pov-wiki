"""Item base pages: the Valheim items mods roll on, with their stats, recipe and item level.

Stats are Valheim's own (extracted with `povwiki valheim`); tags, defences and the crafted item
level are what the mod computes for the item (harness/items.py). Only the RPG side is listed:
weapons, armour, shields, trinkets and utility items with a name in Valheim's strings. Build tools
and fishing gear are left out, and so are monster attacks (which have no name).
"""

from collections import defaultdict

from .item_pages import biome
from .markup import rel
from .pages import Ctx, _footer, _img, _table

BASES_PAGE = "items/bases.md"
_RPG = {"weapon", "armour", "shield", "trinket", "utility", "belt", "ring"}
_NOT_RPG = {"tool", "fishing"}
_SLOTS = ("slot.helmet", "slot.chest", "slot.legs", "slot.cape")
_SHIELDS = ("shield.round", "shield.buckler", "shield.tower")
_CLASSES = ("weapons", "armour", "shields", "jewellery", "trinkets", "utility")
# Valheim damage types in its tooltip order, with their string keys.
_DAMAGES = [
    ("m_blunt", "inventory_blunt"), ("m_slash", "inventory_slash"), ("m_pierce", "inventory_pierce"),
    ("m_fire", "inventory_fire"), ("m_frost", "inventory_frost"), ("m_lightning", "inventory_lightning"),
    ("m_poison", "inventory_poison"), ("m_spirit", "inventory_spirit"), ("m_chop", "inventory_chop"),
    ("m_pickaxe", "inventory_pickaxe"),
]
_DEFENCES = [("armour", "defence.armour"), ("evasion", "defence.evasion"), ("runeShield", "defence.rune_shield")]


def base_path(prefab: str) -> str:
    return f"items/base/{prefab}.md"


def bases(ctx: Ctx) -> dict[str, dict]:
    """prefab -> {"shared": Valheim item data, "info": the mod's view, "name"}."""
    vh = ctx.loc.valheim
    if vh is None:
        return {}
    out = {}
    for prefab, info in ctx.loc.items.items():
        tags = set(info["tags"])
        if not tags & _RPG or tags & _NOT_RPG:
            continue
        if info.get("mod"):  # the mod's own gear (rings, belts): named by the mod
            shared = info["mod"]["shared"]
            out[prefab] = {"shared": shared, "info": info, "name": shared["m_name"]}
            continue
        # Player items have a translated name and an inventory icon; monster attacks have
        # neither (their names are plain text like "Swing attack").
        shared = vh["items"].get(prefab) or {}
        token = shared.get("m_name") or ""
        name = ctx.loc.vtext(token)
        if not token.startswith("$") or "$" in name or not shared.get("icon"):
            continue
        out[prefab] = {"shared": shared, "info": info, "name": name}
    return _one_per_name(ctx, out)


def _one_per_name(ctx: Ctx, found: dict[str, dict]) -> dict[str, dict]:
    """Valheim has copies of many items under the same name (FW_* and SP_* variants, the Dvergr's
    own arbalests): keep the one players craft, else the shortest prefab name (the plain one)."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for prefab, b in found.items():
        by_name[b["shared"]["m_name"]].append(prefab)
    keep = {min(prefabs, key=lambda p: (_recipe(ctx, p) is None, len(p), p)) for prefabs in by_name.values()}
    return {p: b for p, b in found.items() if p in keep}


def _class(b: dict) -> tuple[str, str]:
    """(class, subclass tag): weapons by kind, armour by slot, shields by type."""
    tags = b["info"]["tags"]
    if (b["info"].get("mod") or {}).get("kind") == "utility":  # the Rune of Resurrection: a tankard copy
        return "utility", "utility"
    if "shield" in tags:
        return "shields", next((t for t in _SHIELDS if t in tags), "shield")
    if "weapon" in tags:
        return "weapons", next((t for t in tags if t.startswith("kind.")), "weapon")
    if "armour" in tags:
        return "armour", next((t for t in _SLOTS if t in tags), "armour")
    if "trinket" in tags:
        return "trinkets", "trinket"
    for jewel in ("ring", "belt"):
        if jewel in tags:
            return "jewellery", jewel
    return "utility", "utility"


def _num(v: float) -> str:
    return str(int(round(v))) if abs(v - round(v)) < 0.001 else f"{v:.2f}".rstrip("0").rstrip(".")


def _at(shared: dict, key: str, per_level: str, quality: int) -> float:
    return (shared.get(key) or 0) + (shared.get(per_level) or 0) * (quality - 1)


def _damages(shared: dict, quality: int) -> dict[str, float]:
    base, per = shared.get("m_damages") or {}, shared.get("m_damagesPerLevel") or {}
    out = {k: base.get(k, 0) + per.get(k, 0) * (quality - 1) for k, _ in _DAMAGES}
    return {k: v for k, v in out.items() if v}


def _qualities(b: dict) -> range:
    return range(1, max(1, int(b["shared"].get("m_maxQuality") or 1)) + 1)


def _kind_line(ctx: Ctx, b: dict, page: str) -> str:
    """"axe · one-handed · evasion" from the item's tags."""
    from .weapon_pages import weapon_path, weapon_title, weapon_type_of

    ui, tags = ctx.loc.ui, b["info"]["tags"]
    parts = [ui(f"tag.{_class(b)[1]}")]
    if _class(b)[0] == "weapons" and (slug := weapon_type_of(tags)):
        parts[0] = f"[{parts[0]}]({rel(weapon_path(slug), page)} \"{weapon_title(ctx, slug)}\")"
    parts += [ui(f"tag.{t}") for t in ("one_handed", "two_handed", "paired") if t in tags]
    if b["info"].get("defence"):
        parts.append(ui(f"defence.{b['info']['defence']}"))
    return " · ".join(parts)


def _summary(ctx: Ctx, b: dict) -> str:
    """Key stats at quality 1, for the index."""
    s, vk = b["shared"], ctx.loc.vkey
    parts = [f"{vk(label)} {_num(v)}" for key, label in _DAMAGES if (v := _damages(s, 1).get(key))]
    d = (b["info"].get("defences") or [{}])[0]
    parts += [f"{ctx.loc.ui(label)} {_num(d[key])}" for key, label in _DEFENCES if d.get(key)]
    if "shield" in b["info"]["tags"]:
        parts.append(f"{vk('item_blockpower')} {_num(s.get('m_blockPower') or 0)}")
    parts += [i["text"] for i in b["info"].get("implicits") or [] if "text" in i]
    return ", ".join(parts)


def _stats(ctx: Ctx, b: dict) -> list[list[str]]:
    """Stat rows, one column per quality level. Rows that are zero everywhere are left out."""
    s, info, vk, ui = b["shared"], b["info"], ctx.loc.vkey, ctx.loc.ui
    qs = _qualities(b)
    rows: list[list[str]] = []

    def row(label: str, values: list, fmt=_num) -> None:
        if any(values):
            rows.append([label, *(fmt(v) for v in values)])

    if (info.get("mod") or {}).get("resurrection"):  # a tankard copy: its charges are listed instead
        row(vk("item_weight"), [s.get("m_weight") or 0] * len(qs))
        return rows
    for key, label in _DAMAGES:
        row(vk(label), [_damages(s, q).get(key, 0) for q in qs])
    defences = info.get("defences") or []
    for key, label in _DEFENCES:
        row(ui(label), [d.get(key, 0) for d in defences])
    tags = info["tags"]
    if "shield" in tags or "can_block" in tags:
        row(vk("item_blockpower"), [_at(s, "m_blockPower", "m_blockPowerPerLevel", q) for q in qs])
    if "can_parry" in tags or "shield" in tags:
        if (s.get("m_timedBlockBonus") or 0) > 1:
            row(vk("item_parrybonus"), [s["m_timedBlockBonus"]] * len(qs), lambda v: f"{_num(v)}x")
    if "weapon" in tags:
        row(vk("item_knockback"), [s.get("m_attackForce") or 0] * len(qs))
        row(vk("item_backstab"), [s.get("m_backstabBonus") or 0] * len(qs), lambda v: f"{_num(v)}x")
        attack = s.get("m_attack") or {}
        for key, label in (("m_attackStamina", "item_staminause"), ("m_attackEitr", "item_eitruse"),
                           ("m_attackHealth", "item_healthuse")):
            row(vk(label), [attack.get(key) or 0] * len(qs))
    if s.get("m_useDurability"):
        row(vk("item_durability"), [_at(s, "m_maxDurability", "m_durabilityPerLevel", q) for q in qs])
    row(vk("item_weight"), [s.get("m_weight") or 0] * len(qs))
    row(vk("item_movement_modifier"), [s.get("m_movementModifier") or 0] * len(qs), lambda v: f"{_num(v * 100)}%")
    return rows


# Valheim's Attack.AttackType and Skills.SkillType values.
_VERTICAL, _AREA = 1, 4
_MELEE_SKILLS = {1, 2, 3, 4, 5, 7, 11, 12}  # swords, knives, clubs, polearms, spears, axes, unarmed, pickaxes
_HEAVY_SKILLS = {1, 3, 4, 7}  # GroundStrike.Heavy: two-handed swords, clubs, polearms and axes


def attack_kinds(b: dict) -> dict[str, str]:
    """Which of a weapon's attacks are slams or strikes: {"primary"|"secondary": "slam"|"strike"}.
    The mod's ItemTooltip.AttackTags: area attacks are slams (Slams.IsSlam); a melee weapon's
    vertical swings are strikes (Strikes.IsStrikeSwing). Sceptres are left out (every smite
    counts as a strike, but never gets additional strikes: see Strikes.Eligible)."""
    s, tags = b["shared"], b["info"]["tags"]
    if "weapon" not in tags or "kind.Scepters" in tags:
        return {}
    out = {}
    for slot, key in (("primary", "m_attack"), ("secondary", "m_secondaryAttack")):
        a = s.get(key) or {}
        if not a.get("m_attackAnimation"):  # ItemData.HaveSecondaryAttack
            continue
        if a.get("m_attackType") == _AREA:
            out[slot] = "slam"
        elif a.get("m_attackType") == _VERTICAL and s.get("m_skillType") in _MELEE_SKILLS:
            out[slot] = "strike"
    return out


def ground_strike(b: dict) -> bool:
    """A two-handed weapon whose alternative attack the slam mastery turns into a slam (GroundStrike)."""
    s = b["shared"]
    return "weapon" in b["info"]["tags"] and s.get("m_itemType") == 14 and s.get("m_skillType") in _HEAVY_SKILLS


def attacks_line(ctx: Ctx, b: dict, page: str) -> list[str]:
    """Which attacks of a weapon are strikes or slams, linked to how they work."""
    from .formula_pages import _mastery_link, _term

    ui = ctx.loc.ui
    kinds = attack_kinds(b)
    parts = [ui(f"items.attack_{slot}", kind=_term(ctx, kinds[slot], page)) for slot in ("primary", "secondary") if slot in kinds]
    if ground_strike(b) and kinds.get("secondary") != "slam":
        parts.append(ui("items.attack_ground", mastery=_mastery_link(ctx, "MasterySlam1", page), slam=_term(ctx, "slam", page)))
    return [" ".join(parts), ""] if parts else []


def attacks_cell(ctx: Ctx, b: dict, page: str) -> str:
    """Short form for tables: "strike (alternative)"."""
    from .formula_pages import _term

    kinds = attack_kinds(b)
    return ", ".join(ctx.loc.ui(f"items.attack_{slot}_short", kind=_term(ctx, kinds[slot], page))
                     for slot in ("primary", "secondary") if slot in kinds) or "—"


def _recipe(ctx: Ctx, prefab: str) -> dict | None:
    mod = ctx.loc.items.get(prefab, {}).get("mod")
    if mod:  # the mod's own gear: its recipe at the rune carver table, if it has one
        return mod["recipe"]
    return next((r for r in ctx.loc.valheim["recipes"] if r["item"] == prefab and r["enabled"]), None)


def _level(ctx: Ctx, prefab: str) -> int | None:
    """The item level crafted copies get (CraftLevel.Of); None when the item can't be crafted
    (its level then comes from where it drops)."""
    return ctx.loc.items[prefab]["craftLevel"] if _recipe(ctx, prefab) else None


def _material_level(ctx: Ctx, recipe: dict) -> int:
    """The highest item level among a recipe's materials, upgrade items (Upgrader*/Mold*) left out:
    where the item sits in progression, for ordering lists. Upgrade items have levels of their own
    (CraftLevel.ByPrefix: moulds the Deep North, idols their tier's biome) that say nothing about it."""
    return max([ctx.loc.items.get(r["item"], {}).get("craftLevel", 1)
                for r in recipe["resources"] if not _is_upgrader(r["item"])] or [1])


def _station(ctx: Ctx, recipe: dict | None) -> str:
    """A crafting station's name. Recipes name the station prefab ("forge", "piece_workbench");
    its name is the "piece_" string of the same name."""
    station = recipe and recipe.get("station")
    if not station:
        return "—"
    if isinstance(station, dict):  # the mod's stations come with their name
        return station["name"]
    key = station if station.startswith("piece_") else f"piece_{station}"
    return ctx.loc.vkey(key, ctx.loc.vkey(key.lower(), station))


def _icon(ctx: Ctx, prefab: str, page: str, px: int) -> str:
    """Valheim's icon, or the mod's own for its items (PT_*: PassiveTree.item.<id>.png)."""
    if not ctx.icons:
        return ""
    mod = ctx.loc.items.get(prefab, {}).get("mod")
    if mod:  # the mod's own gear: its icon, or the one it keeps from the item it copies
        image = mod["icon"]
    else:
        image = f"PassiveTree.item.{prefab}.png" if prefab.startswith("PT_") else f"vh:{prefab}"
    return _img(ctx.icons.path(image), page, px)


def _item_name(ctx: Ctx, prefab: str) -> str:
    """Any item's name: Valheim's, or the mod's for its own items (runes, essences, rings...)."""
    loc = ctx.loc
    if mod := loc.items.get(prefab, {}).get("mod"):
        return mod["shared"]["m_name"]
    if prefab in loc.loot["items"]:
        return loc.loot["items"][prefab]["name"]
    return loc.vtext((loc.valheim["items"].get(prefab) or {}).get("m_name")) or prefab


def _is_upgrader(prefab: str) -> bool:
    return prefab.startswith(("Upgrader", "Mold"))


def _implicits_section(ctx: Ctx, b: dict, qs: range) -> list[str]:
    """Implicit lines (always on the item): rolled ones with their range, and the ones that grow
    with quality as a line per quality level ("—" while the game leaves the line out)."""
    implicits = b["info"].get("implicits") or []
    if not implicits:
        return []
    ui = ctx.loc.ui
    md = [f"## {ui('items.implicits')}", "", ui("items.implicits_note"), ""]
    ranged = [i for i in implicits if "text" in i]
    md += [f"- {i['text']}" for i in ranged] + ([""] if ranged else [])
    grows = [i for i in implicits if "byQuality" in i]
    if grows and len(qs) > 1:
        md += _table([ui("items.implicit"), *(ui("items.quality_n", n=q) for q in qs)],
                     [[next(t for t in reversed(i["byQuality"]) if t), *(t or "—" for t in i["byQuality"])] for i in grows])
    elif grows:
        md += [f"- {next(t for t in i['byQuality'] if t)}" for i in grows] + [""]
    return md


def _drops(ctx: Ctx, mod: dict | None) -> str:
    """How the mod's own gear drops: rings by biome (Rings.LootBases), unique belts anywhere from
    an item level (Belts: GlobalMinLevel)."""
    if not mod:
        return ""
    ui = ctx.loc.ui
    if mod.get("everywhere"):
        return ui("items.drops_everywhere")
    if mod.get("biome"):
        return ui("items.drops_in", biome=ctx.loc.vkey(f"biome_{mod['biome'].lower()}", mod["biome"]))
    if mod.get("globalMinLevel"):
        return ui("items.drops_from_level", level=mod["globalMinLevel"], biome=biome(ctx, mod["globalMinLevel"]))
    return ""


def page_bases(ctx: Ctx) -> dict[str, str]:
    """An index of item bases by class, and a page per base."""
    found = bases(ctx)
    if not found:
        return {}
    ui, page = ctx.loc.ui, BASES_PAGE
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for prefab, b in found.items():
        cls, sub = _class(b)
        groups[cls][sub].append(prefab)

    header = ["", ui("col.name"), ui("items.stats"), ui("items.station"), ui("items.item_level")]
    md = [f"# {ui('items.bases')}", "", ui("items.bases_intro"), ""]
    for cls in _CLASSES:
        if cls not in groups:
            continue
        md += [f"## {ui('class.' + cls)}", ""]
        subs = groups[cls]
        if cls == "weapons":  # weapons have a page per type; the ones of no type are listed here
            from .weapon_pages import weapons_index

            md += weapons_index(ctx, found, page)
            subs = {t: v for t, v in subs.items() if t == "weapon"}
            if subs:
                md += [ui("weapons.others"), ""]
        for sub in sorted(subs, key=lambda t: ui(f"tag.{t}")):
            # Crafted items in progression order, then the ones only found as loot.
            def order(p: str) -> tuple:
                recipe = _recipe(ctx, p)
                return (_material_level(ctx, recipe) if recipe else 10**6), found[p]["name"]

            prefabs = sorted(groups[cls][sub], key=order)
            md += [f"### {ui(f'tag.{sub}').capitalize()} ({len(prefabs)})", ""]
            md += _table(header, [[
                _icon(ctx, p, page, 40),
                f"[**{found[p]['name']}**]({rel(base_path(p), page)})",
                _summary(ctx, found[p]),
                _station(ctx, _recipe(ctx, p)),
                biome(ctx, _level(ctx, p)) if _level(ctx, p) else "—",
            ] for p in prefabs])
    pages = {page: "\n".join(md + _footer(ctx))}
    for prefab, b in found.items():
        pages[base_path(prefab)] = _base_page(ctx, prefab, b, found)
    return pages


def _base_page(ctx: Ctx, prefab: str, b: dict, found: dict) -> str:
    loc, ui, page = ctx.loc, ctx.loc.ui, base_path(prefab)
    s, info = b["shared"], b["info"]
    art = _icon(ctx, prefab, page, 96)
    md = [f"# {b['name']}", ""]
    if art:
        md += [art, ""]
    md += [f"<b>{_kind_line(ctx, b, page)}</b>", ""]
    if s.get("m_description"):
        md += [f"*{loc.vtext(s['m_description'])}*".replace("\n", " "), ""]
    summons = loc.difficulty.get("summons") or {}
    if any(c["id"] == prefab for c in summons.get("calls", []) + summons.get("vanilla", [])):
        from .formula_pages import SUMMONS_PAGE

        md += [ui("items.summons_see", link=rel(SUMMONS_PAGE, page)), ""]

    qs = _qualities(b)
    md += _implicits_section(ctx, b, qs)
    stats = _stats(ctx, b)
    if stats:
        md += [f"## {ui('items.stats')}", ""]
        md += _table([ui("items.stat"), *(ui("items.quality_n", n=q) for q in qs)], stats)
    md += attacks_line(ctx, b, page)

    md += _bomb_section(ctx, info.get("mod"), page) + _resurrection_section(ctx, info.get("mod"), page)
    md += _ascension_section(ctx, prefab, b, page)

    recipe = _recipe(ctx, prefab)
    if recipe:
        station = _station(ctx, recipe)
        if isinstance(recipe.get("station"), dict):  # the mod's own station has its own page
            from .building_pages import building_path

            station = f"[{station}]({rel(building_path(recipe['station']['id']), page)})"
        station = f"{station} · {ui('items.station_level', n=recipe['stationLevel'])}"
        md += [f"## {ui('items.recipe')}", "", station, ""]
        if (makes := recipe.get("makes") or recipe.get("amount") or 1) > 1:
            md += [ui("items.makes", n=makes), ""]
        rows = []
        for res in recipe["resources"]:
            mat = res["item"]
            name = _item_name(ctx, mat)
            link = f"[{name}]({rel(base_path(mat), page)})" if mat in found else name
            # Valheim's Requirement.GetAmount: crafting takes the amount, upgrading to quality q
            # takes (q - 1) x the per-level amount. Some of the mod's staves cost the per-level
            # amount once per step ("flat": StarterStaves.UpgradeCost).
            upgrades = [str(res["perLevel"] * (1 if res.get("flat") else q - 1)) for q in qs[1:]]
            rows.append([_icon(ctx, mat, page, 32), link, str(res["amount"]), *upgrades])
        header = ["", ui("items.material"), ui("items.craft"), *(ui("items.upgrade_n", n=q) for q in qs[1:])]
        md += _table(header, rows)

    level = _level(ctx, prefab)
    md += [f"## {ui('items.item_level')}", ""]
    if level is None:
        md += [ui("items.not_craftable"), ""]
    else:
        md += [ui("items.item_level_line", biome=biome(ctx, level), level=level), ""]
    if drops := _drops(ctx, info.get("mod")):
        md += [drops, ""]
    from .gear_pages import chisel_section

    md += chisel_section(ctx, prefab, page)
    if _class(b)[0] != "utility" or not info.get("mod"):  # the rune rolls nothing
        md += _mods_section(ctx, b, page)

    md += [f"## {ui('items.tags')}", "", ui("items.tags_note"), ""]
    md += [", ".join(ui(f"tag.{t}") if ui(f"tag.{t}") != f"tag.{t}" else f"`{t}`" for t in info["tags"]), ""]
    from .patch_pages import history

    md += history(ctx, "bases", [prefab], page)
    return "\n".join(md + _footer(ctx))


def _ascension_section(ctx: Ctx, prefab: str, b: dict, page: str) -> list[str]:
    """What each boss essence that can ascend this item makes of it (povwiki.ascension)."""
    from .ascension import ascended
    from .formula_pages import _anchor, shown
    from .gear_pages import currency_path

    rows = ascended(ctx, prefab, b["shared"]) if shown(ctx, "ascension") else []
    if not rows:
        return []
    loc, ui, vk = ctx.loc, ctx.loc.ui, ctx.loc.vkey
    s = b["shared"]

    def pair(base: float, per: float) -> str:  # quality 1, and what each quality adds
        return f"{_num(base)} (+{_num(per)})" if per else _num(base)

    cols = []  # (label, cell) for the stats this item has
    if any(_damages({"m_damages": r["damages"]}, 1) for r in rows) and "shield" not in b["info"]["tags"]:
        cols.append((ui("formula.ascension.damage"), lambda r: ", ".join(
            f"{vk(label)} {pair(r['damages'].get(key, 0), r['damagesPerLevel'].get(key, 0))}"
            for key, label in _DAMAGES if r["damages"].get(key) or r["damagesPerLevel"].get(key))))
    if "shield" in b["info"]["tags"]:
        cols.append((vk("item_blockpower"), lambda r: pair(r["block"], r["blockL"])))
        cols.append((vk("item_deflection"), lambda r: pair(r["defl"], r["deflL"])))
    if s.get("m_useDurability"):
        cols.append((vk("item_durability"), lambda r: pair(r["dur"], r["durL"])))
    header = [ui("formula.ascension.essence"), ui("bosses.biome"), *(label for label, _ in cols)]
    table = [[f"[{loc.loot['items'].get(r['essence'], {}).get('name', r['essence'])}]({rel(currency_path(r['essence']), page)})",
              f"{vk(f'biome_{r['biome'].lower()}', r['biome'])} ({r['level']})", *(cell(r) for _, cell in cols)] for r in rows]
    from .tools_pages import ASCENSION_PAGE

    calc = f"{rel(ASCENSION_PAGE, page)}#{prefab}"  # the calculator, with this item filled in
    return ([f"## {ui('formula.ascension.title')}", "",
             ui("formula.ascension.item_intro", link=_anchor("ascension", page), title=ui("formula.ascension.title")), ""] + _table(header, table)
            + [ui("tools.ascension.item_link", link=calc, title=ui("tools.ascension.title")), ""])


def _bomb_section(ctx: Ctx, mod: dict | None, page: str) -> list[str]:
    """The burst of the mod's bombs (BombLadder.Rung, StarterBomb): its radius and what it does
    besides damage."""
    bomb = (mod or {}).get("bomb")
    if not bomb:
        return []
    from .markup import glossary_path

    ui, term = ctx.loc.ui, lambda key: rel(glossary_path(key), page)
    md = [f"## {ui('items.bomb')}", "", f"- {ui('items.bomb_radius', radius=_num(bomb['radius']))}"]
    if "thornsShare" in bomb:
        md.append(f"- {ui('items.bomb_thorns', base=_num(bomb['thornsBase']), share=_num(bomb['thornsShare'] * 100), thorns=term('thorns'))}")
    if "pullRange" in bomb:
        md.append(f"- {ui('items.bomb_pull', range=_num(bomb['pullRange']), seconds=_num(bomb['pullSeconds']))}")
    if "breakShare" in bomb:
        md.append(f"- {ui('items.bomb_break', share=_num(bomb['breakShare'] * 100), seconds=_num(bomb['breakSeconds']), corrosion=term('corrosion'))}")
    if "tarSeconds" in bomb:
        md.append(f"- {ui('items.bomb_tar', seconds=_num(bomb['tarSeconds']))}")
    return md + [""]


def _resurrection_section(ctx: Ctx, mod: dict | None, page: str) -> list[str]:
    """The Rune of Resurrection (Resurrection): charges and channel time by quality, how it is
    used and recharged."""
    res = (mod or {}).get("resurrection")
    if not res:
        return []
    from .markup import glossary_path

    ui = ctx.loc.ui
    md = [f"## {ui('items.resurrection')}", "", ui("items.resurrection_use", companion=rel(glossary_path("companion"), page),
                                                    range=_num(res["range"])), ""]
    md += _table([ui("items.stat"), *(ui("items.quality_n", n=q) for q in range(1, len(res["charges"]) + 1))], [
        [ui("items.resurrection_charges"), *(str(c) for c in res["charges"])],
        [ui("items.resurrection_seconds"), *(f"{_num(s)} s" for s in res["seconds"])],
    ])
    from .building_pages import building_path

    return md + [ui("items.resurrection_recharge", station=rel(building_path("PT_RuneCarverTable"), page),
                    azurite=rel("items/currency/PT_DivineAzurite.md", page)), ""]


# ---- Mods that roll on a base -------------------------------------------------------------------


def _fits(affix: dict, tags: set[str]) -> bool:
    """The tag part of AffixDef.Fits: all of AllowAll, one of AllowAny (if any), none of DenyAny."""
    return (all(t in tags for t in affix["allowAll"])
            and (not affix["allowAny"] or any(t in tags for t in affix["allowAny"]))
            and not any(t in tags for t in affix["denyAny"]))


def _slot(tags: set[str]) -> str:
    """Which slot multiplier the item gets (LootRoller.SlotMult): its key in the rendered tiers."""
    for tag, slot in (("slot.chest", "chest"), ("slot.legs", "legs"), ("shield.tower", "tower"), ("shield.buckler", "buckler")):
        if tag in tags:
            return slot
    if "weapon" in tags and "paired" not in tags:
        if "two_handed" in tags:
            return "two_handed"
        if "one_handed" in tags:
            return "one_handed"
    return "base"


def _rollable_tiers(affix: dict) -> list[dict]:
    """Tiers that can roll (TierDef.Allows: special tiers never do; weight 0 never wins)."""
    return [t for t in affix["tiers"] if not t["special"] and t["weight"] > 0]


def _mods_section(ctx: Ctx, b: dict, page: str) -> list[str]:
    """Every mod that can roll on this base, prefixes and suffixes apart, with weights. Values are
    for this item's slot. Mods only a boss essence adds are listed after."""
    from .item_pages import _title, _values, mod_path

    ui, loot = ctx.loc.ui, ctx.loc.loot
    tags = set(b["info"]["tags"])
    slot = _slot(tags)
    fitting = [a for a in loot["affixes"] if _fits(a, tags) and _rollable_tiers(a)]
    rolls = [a for a in fitting if a["generation"]]
    essence = [a for a in fitting if a["source"] == "essence"]
    if not rolls and not essence:
        return []

    def values(a: dict) -> str:
        tiers = _rollable_tiers(a)
        low, high = (_values(t["text"].get(slot) or t["text"]["base"]) for t in (tiers[0], tiers[-1]))
        return low if low == high else f"{low} → {high}"

    def link(a: dict) -> str:
        return f"[{_title(a)}]({rel(mod_path(a), page)})"

    def level(a: dict) -> str:
        # AffixDef.Fits wants the item level at the mod's own minimum, and a tier must allow it.
        lvl = max(1, a["minLevel"], min(t["minLevel"] for t in _rollable_tiers(a)))
        return f"{biome(ctx, lvl)} <small>({lvl})</small>"

    md = [f"## {ui('items.mods')}", "", ui("items.base_mods_intro"), ""]
    header = [ui("items.mod"), ui("items.value"), ui("items.min_level"), ui("items.tiers"), ui("items.weight"), ui("items.share")]
    for place in ("prefix", "suffix"):
        chosen = sorted((a for a in rolls if a["place"] == place), key=lambda a: (-a["weight"], _title(a)))
        if not chosen:
            continue
        total = sum(a["weight"] for a in chosen)
        md += [f"### {ui('items.' + place)} ({len(chosen)})", ""]
        md += _table(header, [[
            link(a), values(a), level(a), str(len(_rollable_tiers(a))), f"{a['weight']:g}", f"{100 * a['weight'] / total:.1f}%",
        ] for a in chosen])
    if essence:
        from .item_pages import _essences_for

        md += [f"### {ui('items.essence_only')} ({len(essence)})", "", ui("items.base_essence_note"), ""]
        md += _table([ui("items.mod"), ui("items.place"), ui("items.value"), ui("items.source")], [
            [link(a), ui(f"items.{a['place']}"), values(a), ", ".join(_essences_for(ctx, a))]
            for a in sorted(essence, key=_title)
        ])
    return md
