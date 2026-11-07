"""Jewels, unique items and currency details, as the game defines and shows them.

- Jewels (Jewels.All): base jewels (Base: str, dex-int...) and unique ones, with their name,
  flavor, icon, radius and socket limit. Kinds with neither a base nor unique lines are unused
  placeholders (Jewels.Blank) and are marked so.
- Unique lines (UniqueItems, from the loot catalog): each line rendered like the tooltip
  (LootAffixes.Def.Line) at its minimum and maximum, merged into "(min-max)" ranges. Lines that
  pick a tree node, theme or path when the item drops keep the game's wording with the pick left
  open ({0}); lines that pick a stat from a pool list every stat they can pick.
- Currency (Runes.All): category, consumable, rarity flags (names, actions and recipes are in
  the loot section); for sigils, their effect in each kind of item (BossSigils.Describe).
"""

import clr

from .loot import _merge
from System.Reflection import BindingFlags

_ALL = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic


def _numeric(d, lo: float, hi: float) -> str:
    if d.Shown is not None and lo != hi:  # values shown as words (radius: Small...Very Large)
        from PassiveTree import L
        from System import String

        return String.Format(L.Id("affix." + d.Id, d.Text), f"({d.Shown(float(lo))} – {d.Shown(float(hi))})")
    return _merge(d.Line(float(lo)), d.Line(float(hi)))


def _rolled(d, value: float, ref):
    from PassiveTree import LootAffixes

    r = LootAffixes.Rolled()
    r.Id, r.Value, r.Ref = d.Id, value, ref
    return r


def _line(line) -> dict:
    """One unique line: {"text"} for fixed wording, {"template", "pick"} for a line that picks a
    tree node/theme/path, {"pool": [...]} for a line that picks a stat; "count" rows of it."""
    from PassiveTree import L, LootAffixes

    if line.OneOf.Count:
        return {"oneOf": [{**_line(sub), "weight": float(sub.Weight)} for sub in line.OneOf]}
    d = LootAffixes.Find(line.Affix)
    out = {"affix": line.Affix, "count": int(line.Count), "distinct": bool(line.Distinct)}
    if d is None:
        return {**out, "text": line.Affix, "unknown": True}
    if line.Pool.Count:
        out["pool"] = [{
            "text": _merge(d.Line(_rolled(d, p.Min, p.Ref)), d.Line(_rolled(d, p.Max, p.Ref))),
            "weight": float(p.Weight),
        } for p in line.Pool]
    elif d.NodeRef or d.ThemeRef or d.PathRef:
        out["template"] = L.Id("affix." + d.Id, d.Text)
        out["pick"] = line.Ref  # keystone, notable, theme, path-other
    elif line.HasRange:
        out["text"] = _numeric(d, line.Min, line.Max)
    elif d.Tiers is not None and len(d.Tiers):
        out["text"] = _numeric(d, min(t.Min for t in d.Tiers), max(t.Max for t in d.Tiers))
    else:
        out["text"] = d.Line(0.0)
    return out


def _affixes(lines: list[dict]):
    for line in lines:
        yield line.get("affix")
        yield from _affixes(line.get("oneOf") or [])


def _radius(j: dict, unique: dict | None) -> None:
    """The tooltip's radius header (ItemTooltip.Head): only for jewels with a zone; the fixed
    radius, "Variable" when a line rolls it, else Large; "Ring:" for ring jewels."""
    from PassiveTree import L, LootAffixes
    from System import String

    j["radius"] = j["radiusLine"] = None
    if j["zone"] <= 0:
        return
    rolled = set(_affixes((unique or {}).get("lines") or []))
    ring = LootAffixes.RingRadius.Id in rolled
    if j["fixedRadius"] >= 0:
        text = LootAffixes.RadiusShown(float(j["fixedRadius"]))
    elif ring or LootAffixes.JewelRadius.Id in rolled:
        text = L.Id("ui.item.radius-variable", "Variable")
    else:
        text = LootAffixes.RadiusShown(2.0)
    j["radius"] = text
    j["radiusLine"] = String.Format(L.Id("ui.item.ring", "Ring: {0}") if ring else L.Id("ui.item.radius", "Radius: {0}"), text)


def _jewel(k, blank) -> dict:
    from PassiveTree import L

    return {
        "name": L.Id(f"item.{k.Id}.name", k.Name),
        "flavor": L.Id(f"item.{k.Id}.flavor", k.Flavor) if k.Flavor else "",
        "icon": f"PassiveTree.jewel.{k.Icon}.png",
        "base": k.Base,
        "unique": str(k.Rarity) == "Unique" if k.Rarity is not None else False,
        "fixedRadius": int(k.FixedRadius),
        "zone": float(k.Zone),
        "limit": int(k.LimitOf),
        "family": k.Family,
        "influence": k.Influence,
        "globalWeight": float(k.GlobalWeight),
        "globalMinLevel": int(k.GlobalMinLevel),
        "placeholder": bool(blank.Invoke(None, [k])),
        "implicits": _jewel_implicits(str(k.Id)),
    }


def _jewel_implicits(jewel: str) -> list[dict]:
    """A base jewel's attribute implicits (JewelImplicits registers them by base on first use)."""
    import PassiveTree

    Implicits, owner = getattr(PassiveTree, "Implicits", None), getattr(PassiveTree, "JewelImplicits", None)
    if Implicits is None or owner is None:  # older versions
        return []
    owner.Touch()
    bases = clr.GetClrType(Implicits).GetField("bases", _ALL).GetValue(None)
    if not bases.ContainsKey(jewel):
        return []
    return [{"id": r.Item1.Id, "text": Implicits.Line(r.Item1, Implicits.Range(r.Item2, r.Item3) or str(r.Item2)),
             "min": r.Item2, "max": r.Item3} for r in bases[jewel]]


def _complete_kvasir(unique: dict | None) -> None:
    """LootAffixes.CompleteKvasir: every Kvasir's Blood also gets mead duration and potency lines
    (25 each) when it is loaded, on top of its catalog lines."""
    from PassiveTree import LootAffixes

    if unique is None:
        return
    t = clr.GetClrType(LootAffixes)
    for name in ("KvasirMeadDuration", "KvasirMeadPotency"):
        member = t.GetField(name, _ALL) or t.GetProperty(name, _ALL)
        d = member.GetValue(None) if member is not None else None
        if d is not None:
            unique["lines"].append({"affix": d.Id, "count": 1, "distinct": True, "text": d.Line(25.0)})


def _code_only_uniques(uniques: dict) -> None:
    """Uniques whose line is rolled in code at drop time (no catalog lines). Eye Between Worlds
    (LootAffixes "PT_Jewel_EyeBetweenWorlds"): one JewelRiftTo line pointing at a random knowledge
    portal of the tree (Rifts.Targets). Keep in sync with LootAffixes.uniques."""
    import PassiveTree
    from PassiveTree import L, LootAffixes

    if "PT_Jewel_EyeBetweenWorlds" in uniques or not hasattr(PassiveTree, "Rifts"):
        return
    d = LootAffixes.Find("jewel.rift-to")
    if d is not None:
        uniques["PT_Jewel_EyeBetweenWorlds"] = {"lines": [
            {"affix": "jewel.rift-to", "count": 1, "distinct": False, "template": L.Id("affix." + d.Id, d.Text), "pick": "portal"}],
            # The ascendancy class each SubclassReveal subject stands for (Subclasses.ByChip), by its shown name:
            # the portals the Eye can point at are hidden without their class.
            "classes": _class_names()}
    # Womb of Corruption (WombOfCorruption.Roll, 5.3.2): a random keystone, and one of the
    # LootAffixes.WombPenalties at 10-20% less.
    if "PT_Jewel_WombOfCorruption" not in uniques and hasattr(PassiveTree, "WombOfCorruption"):
        node = LootAffixes.AllocatesNode
        uniques["PT_Jewel_WombOfCorruption"] = {"lines": [
            {"affix": str(node.Id), "count": 1, "distinct": False, "template": L.Id("affix." + node.Id, node.Text), "pick": "keystone"},
            {"oneOf": [{"affix": str(d.Id), "count": 1, "distinct": False, "text": _numeric(d, 10, 20), "weight": 1.0}
                       for d in LootAffixes.WombPenalties]}]}


def _class_names() -> dict[str, str]:
    from PassiveTree import Subclasses

    names = {d.Key: str(d.Shown) for d in Subclasses.All}
    return {str(kv.Key): names.get(kv.Value, str(kv.Value)) for kv in Subclasses.ByChip}


_DAMAGE_KEYS = ("blunt", "slash", "pierce", "fire", "frost", "lightning", "poison", "spirit")


def _base_value(base, key: str):
    return float(base[key]) if base.ContainsKey(key) else None


def _apply_base(shared: dict, base) -> dict:
    """UniqueGear.ApplyBase over the donor's data: when the base names any damage, the damage (and
    per quality) is replaced by it, chop and pickaxe kept; draw and reload time, armour, block,
    durability and movement override the donor's; noEquipEffect drops its equip effect."""
    s = dict(shared)
    if any(base.ContainsKey(k) for k in _DAMAGE_KEYS):
        old = s.get("m_damages") or {}
        s["m_damages"] = {**{f"m_{k}": _base_value(base, k) or 0.0 for k in _DAMAGE_KEYS},
                          "m_chop": old.get("m_chop", 0.0), "m_pickaxe": old.get("m_pickaxe", 0.0)}
        s["m_damagesPerLevel"] = {f"m_{k}": _base_value(base, k + "PerQuality") or 0.0 for k in _DAMAGE_KEYS}
    attack = dict(s.get("m_attack") or {})
    for key, field in (("drawSeconds", "m_drawDurationMin"), ("reloadSeconds", "m_reloadTime")):
        if base.ContainsKey(key) and s.get("m_attack") is not None:
            attack[field] = _base_value(base, key)
            s["m_attack"] = attack
    for key, field, per in (("armour", "m_armor", "m_armorPerLevel"), ("blockPower", "m_blockPower", "m_blockPowerPerLevel"),
                            ("durability", "m_maxDurability", "m_durabilityPerLevel"), ("movement", "m_movementModifier", None)):
        if base.ContainsKey(key):
            s[field] = _base_value(base, key)
            if per is not None and base.ContainsKey(key + "PerQuality"):
                s[per] = _base_value(base, key + "PerQuality")
    if (_base_value(base, "noEquipEffect") or 0) > 0.5:
        s.pop("m_equipStatusEffect", None)
    return s


def _gear_line(d, tier) -> str:
    """A unique's row as the tooltip writes it (harness/loot.py _line), at its special tier's
    minimum and maximum: UniqueGear.EnsureRolled rolls min + step × k, without slot multipliers."""
    from .loot import _line as affix_line

    return _merge(affix_line(d, tier, float(tier.Min)), affix_line(d, tier, float(tier.Max)))


def _unique_gear(errors: list, valheim, items: dict) -> dict:
    """Unique equipment (UniqueGear, 6.0): copies of a donor item (UniqueGear.Make) with their own
    name, flavor (and quote), base changes (ApplyBase), defence base (pov.defence.base), implicit
    (RegisterImplicits: the donor's, or their own range) and rows of unique.* affixes at their
    special tier U-<key>, rolled at the unique's item level (EnsureRolled)."""
    import json

    from PassiveTree import EquipmentDefences, L
    from PassiveTree.Loot import ItemTags, LootCatalog

    try:
        from PassiveTree.Loot import UniqueGear
    except ImportError:  # before 6.0
        return {}
    from .items import _Builder, _implicits

    LootCatalog.Ensure()
    clr.GetClrType(UniqueGear).GetMethod("RegisterImplicits", _ALL).Invoke(None, [])
    vh_items, build = {}, None
    if valheim is not None:
        vh_items = json.loads((valheim / "items.json").read_text(encoding="utf-8"))
        build = _Builder(json.loads((valheim / "effects.json").read_text(encoding="utf-8")))
    tag_set = clr.GetClrType(ItemTags).GetField("set", _ALL)
    out = {}
    for d in UniqueGear.All:
        try:
            flavor = L.Id(f"item.{d.Id}.flavor", d.Flavor) if d.Flavor else ""
            quote = L.Id(f"item.{d.Id}.quote", d.Quote) if d.Quote else ""
            rows = []
            for row in d.Rows:
                a = LootCatalog.Find(row.Affix)
                tier = a.Tier(d.TierId) if a is not None else None
                if tier is not None:  # ReadOne keeps only rows whose affix has the unique's tier
                    rows.append({"affix": str(row.Affix), "count": 1, "distinct": False, "text": _gear_line(a, tier)})
            g = {
                "name": L.Id(f"item.{d.Id}.name", d.Name), "flavor": flavor, "quote": quote,
                "kind": str(d.Kind), "donor": str(d.Donor), "level": int(d.Level), "defence": str(d.Defence) or None,
                "loot": bool(d.Loot), "pending": str(d.Pending) or None,
                "base": {str(kv.Key): float(kv.Value) for kv in d.Base if isinstance(kv.Value, (int, float))},
                "lines": rows,
            }
            # The item as UniqueGear.Ensure registers it: weapon kind, ring or belt of its donor.
            from PassiveTree import Belts, Rings, WeaponAffixes

            kind = WeaponAffixes.RegisteredKind(d.Donor)
            if str(kind) != "None":
                WeaponAffixes.Register(d.Id, kind)
            if d.Kind == "ring":
                Rings.AddUnique(d.Id, d.Donor)
            if d.Kind == "belt":
                Belts.AddUnique(d.Id, d.Donor)
            donor = vh_items.get(str(d.Donor)) or ((items.get(str(d.Donor)) or {}).get("mod") or {}).get("shared")
            if build is not None and donor:
                shared = _apply_base(donor, d.Base)
                shared.update({"m_name": g["name"], "m_description": flavor, "m_maxStackSize": 1, "m_maxQuality": 1,
                               "m_setName": "", "m_setSize": 0})
                shared.pop("m_setStatusEffect", None)
                item = build.item(str(d.Id), shared)
                if d.Defence:
                    item.m_customData["pov.defence.base"] = d.Defence
                wears = EquipmentDefences.Wear(item)
                tags = sorted(str(t) for t in tag_set.GetValue(ItemTags.Of(item)))
                dv = EquipmentDefences.Of(item, 1, -1.0) if wears else None
                g.update({
                    "shared": {k: v for k, v in shared.items() if k not in ("m_icons",)},
                    "tags": tags,
                    "defenceKind": str(EquipmentDefences.Kind(item)) if wears else None,
                    "defences": [{"armour": dv.Armour, "evasion": dv.Evasion, "runeShield": dv.RuneShield}] if dv else [],
                    "implicits": _implicits(item, str(d.Id)),
                })
            out[str(d.Id)] = g
        except Exception as ex:  # one bad unique must not lose the rest
            errors.append({"uniqueGear": str(d.Id), "error": str(ex).split("\n")[0]})
    return out


def _halls_bosses() -> dict[str, str]:
    """The halls' own bosses (HallsBosses.Defs), named as the game names them (HallsBosses.Make)."""
    try:
        from PassiveTree import L
        from PassiveTree.Encounters.Halls import HallsBosses
    except ImportError:  # before 6.0
        return {}
    defs = clr.GetClrType(HallsBosses).GetField("Defs", _ALL).GetValue(None)
    return {str(d.Id): L.Id(f"enc.halls.{d.Key}", d.Name) for d in defs}


def render_gear(errors: list, valheim=None, items: dict | None = None) -> dict:
    import PassiveTree
    from PassiveTree import L, Runes
    from PassiveTree.Loot import BossSigils, LootCatalog, UniqueItems

    LootCatalog.Ensure()
    out: dict = {"jewels": {}, "uniques": {}, "currency": {}}
    Jewels = getattr(PassiveTree, "Jewels", None)
    if Jewels is not None:
        blank = clr.GetClrType(Jewels).GetMethod("Blank", _ALL)
        for k in Jewels.All:
            try:
                out["jewels"][str(k.Id)] = _jewel(k, blank)
            except Exception as ex:  # one bad jewel must not lose the rest
                errors.append({"jewel": k.Id, "error": str(ex).split("\n")[0]})

    defs = clr.GetClrType(UniqueItems).GetField("defs", _ALL).GetValue(None)
    for kv in defs:
        try:
            out["uniques"][str(kv.Key)] = {"lines": [_line(line) for line in kv.Value.Lines]}
        except Exception as ex:
            errors.append({"unique": kv.Key, "error": str(ex).split("\n")[0]})
    _complete_kvasir(out["uniques"].get("PT_BeltKvasirsBlood"))
    _code_only_uniques(out["uniques"])
    out["uniqueGear"] = _unique_gear(errors, valheim, items or {})
    for item, g in out["uniqueGear"].items():  # their rows are unique lines like the others'
        out["uniques"].setdefault(item, {"lines": g["lines"]})
    for item, j in out["jewels"].items():
        _radius(j, out["uniques"].get(item))

    # The mod's own bosses, named as the game names them (loot tables list them by prefab).
    out["creatures"] = {}
    if (mother := getattr(PassiveTree, "MistMother", None)) is not None:
        out["creatures"]["PT_MistMother"] = mother.Title
    if (monolith := getattr(PassiveTree, "MonolithBoss", None)) is not None:
        for boss in monolith.All:
            out["creatures"][str(boss.Name)] = boss.Title
    out["creatures"].update(_halls_bosses())

    for k in Runes.All:
        out["currency"][str(k.Id)] = {
            "cat": str(k.Cat), "consumable": bool(k.Consumable), "trophy": bool(k.Trophy),
            "rare": bool(k.Rare), "rareResource": bool(k.RareResource),
        }
        try:  # a sigil's effect in each kind of item, as its tooltip lists it (BossSigils.Describe)
            # Plain text (no tooltip scaling links); a line that allocates a tree node names it by id.
            described = BossSigils.Describe(str(k.Id), False)
            lines = [{"slots": kv.Key, "text": kv.Value, "node": str(line.Node) if line.Node else None}
                     for kv, line in zip(described, BossSigils.LinesOf(str(k.Id)))]
            if lines or BossSigils.Known(str(k.Id)):
                out["currency"][str(k.Id)]["sigil"] = lines
        except Exception as ex:
            errors.append({"sigil": str(k.Id), "error": str(ex).split("\n")[0]})
    out["sigilNoEffect"] = L.Id("sigil.no-effect", "")  # what the tooltip says in an item it does nothing for
    from PassiveTree import Tunables

    if any(k.Id == "monolith.unique-chance" for k in Tunables.All):  # 5.1.1: a won rune monolith event's unique
        out["monolithUniqueChance"] = float(Tunables.Of("monolith.unique-chance"))
    return out
