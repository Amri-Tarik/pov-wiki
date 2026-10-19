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
_RPG = {"weapon", "armour", "shield", "trinket", "utility", "belt"}
_NOT_RPG = {"tool", "fishing"}
_SLOTS = ("slot.helmet", "slot.chest", "slot.legs", "slot.cape")
_SHIELDS = ("shield.round", "shield.buckler", "shield.tower")
_CLASSES = ("weapons", "armour", "shields", "trinkets", "utility")
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
    if "shield" in tags:
        return "shields", next((t for t in _SHIELDS if t in tags), "shield")
    if "weapon" in tags:
        return "weapons", next((t for t in tags if t.startswith("kind.")), "weapon")
    if "armour" in tags:
        return "armour", next((t for t in _SLOTS if t in tags), "armour")
    if "trinket" in tags:
        return "trinkets", "trinket"
    return "utility", "belt" if "belt" in tags else "utility"


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


def _kind_line(ctx: Ctx, b: dict) -> str:
    """"axe · one-handed · evasion" from the item's tags."""
    ui, tags = ctx.loc.ui, b["info"]["tags"]
    parts = [ui(f"tag.{_class(b)[1]}")]
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
    return ", ".join(parts)


def _stats(ctx: Ctx, b: dict) -> list[list[str]]:
    """Stat rows, one column per quality level. Rows that are zero everywhere are left out."""
    s, info, vk, ui = b["shared"], b["info"], ctx.loc.vkey, ctx.loc.ui
    qs = _qualities(b)
    rows: list[list[str]] = []

    def row(label: str, values: list, fmt=_num) -> None:
        if any(values):
            rows.append([label, *(fmt(v) for v in values)])

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


def _recipe(ctx: Ctx, prefab: str) -> dict | None:
    return next((r for r in ctx.loc.valheim["recipes"] if r["item"] == prefab and r["enabled"]), None)


def _level(ctx: Ctx, prefab: str) -> int | None:
    """The item level crafted copies get (CraftLevel.Of); None when the item can't be crafted
    (its level then comes from where it drops)."""
    return ctx.loc.items[prefab]["craftLevel"] if _recipe(ctx, prefab) else None


def _material_level(ctx: Ctx, recipe: dict) -> int:
    """The highest item level among a recipe's materials, upgrade items (Upgrader*/Mold*) left out:
    where the item sits in progression, for ordering lists. Upgrade items are rated Deep North
    (CraftLevel.ByPrefix), so most recipes would otherwise tie."""
    return max([ctx.loc.items.get(r["item"], {}).get("craftLevel", 1)
                for r in recipe["resources"] if not _is_upgrader(r["item"])] or [1])


def _station(ctx: Ctx, recipe: dict | None) -> str:
    """A crafting station's name. Recipes name the station prefab ("forge", "piece_workbench");
    its name is the "piece_" string of the same name."""
    station = recipe and recipe.get("station")
    if not station:
        return "—"
    key = station if station.startswith("piece_") else f"piece_{station}"
    return ctx.loc.vkey(key, ctx.loc.vkey(key.lower(), station))


def _icon(ctx: Ctx, prefab: str, page: str, px: int) -> str:
    return _img(ctx.icons.path(f"vh:{prefab}"), page, px) if ctx.icons else ""


def _is_upgrader(prefab: str) -> bool:
    return prefab.startswith(("Upgrader", "Mold"))


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
        for sub in sorted(groups[cls], key=lambda t: ui(f"tag.{t}")):
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
    md += [f"<b>{_kind_line(ctx, b)}</b>", ""]
    if s.get("m_description"):
        md += [f"*{loc.vtext(s['m_description'])}*".replace("\n", " "), ""]

    qs = _qualities(b)
    stats = _stats(ctx, b)
    if stats:
        md += [f"## {ui('items.stats')}", ""]
        md += _table([ui("items.stat"), *(ui("items.quality_n", n=q) for q in qs)], stats)

    recipe = _recipe(ctx, prefab)
    if recipe:
        station = f"{_station(ctx, recipe)} · {ui('items.station_level', n=recipe['stationLevel'])}"
        md += [f"## {ui('items.recipe')}", "", station, ""]
        rows = []
        for res in recipe["resources"]:
            mat = res["item"]
            name = loc.vtext((loc.valheim["items"].get(mat) or {}).get("m_name")) or mat
            link = f"[{name}]({rel(base_path(mat), page)})" if mat in found else name
            # Valheim's Requirement.GetAmount: crafting takes the amount, upgrading to quality q
            # takes (q - 1) x the per-level amount.
            upgrades = [str(res["perLevel"] * (q - 1)) for q in qs[1:]]
            rows.append([_icon(ctx, mat, page, 32), link, str(res["amount"]), *upgrades])
        header = ["", ui("items.material"), ui("items.craft"), *(ui("items.upgrade_n", n=q) for q in qs[1:])]
        md += _table(header, rows)

    level = _level(ctx, prefab)
    md += [f"## {ui('items.item_level')}", ""]
    if level is None:
        md += [ui("items.not_craftable"), ""]
    else:
        md += [ui("items.item_level_line", biome=biome(ctx, level), level=level), ""]
    md += _mods_section(ctx, b, page)

    md += [f"## {ui('items.tags')}", "", ui("items.tags_note"), ""]
    md += [", ".join(ui(f"tag.{t}") if ui(f"tag.{t}") != f"tag.{t}" else f"`{t}`" for t in info["tags"]), ""]
    return "\n".join(md + _footer(ctx))


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
