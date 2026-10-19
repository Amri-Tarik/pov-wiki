"""Jewels, unique items and currency details, as the game defines and shows them.

- Jewels (Jewels.All): base jewels (Base: str, dex-int...) and unique ones, with their name,
  flavor, icon, radius and socket limit. Kinds with neither a base nor unique lines are unused
  placeholders (Jewels.Blank) and are marked so.
- Unique lines (UniqueItems, from the loot catalog): each line rendered like the tooltip
  (LootAffixes.Def.Line) at its minimum and maximum, merged into "(min-max)" ranges. Lines that
  pick a tree node, theme or path when the item drops keep the game's wording with the pick left
  open ({0}); lines that pick a stat from a pool list every stat they can pick.
- Currency (Runes.All): category, consumable, rarity flags (names, actions and recipes are in
  the loot section).
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
    }


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


def render_gear(errors: list) -> dict:
    import PassiveTree
    from PassiveTree import Runes
    from PassiveTree.Loot import LootCatalog, UniqueItems

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
    for item, j in out["jewels"].items():
        _radius(j, out["uniques"].get(item))

    # The mod's own bosses, named as the game names them (loot tables list them by prefab).
    out["creatures"] = {}
    if (mother := getattr(PassiveTree, "MistMother", None)) is not None:
        out["creatures"]["PT_MistMother"] = mother.Title
    if (monolith := getattr(PassiveTree, "MonolithBoss", None)) is not None:
        for boss in monolith.All:
            out["creatures"][str(boss.Name)] = boss.Title

    for k in Runes.All:
        out["currency"][str(k.Id)] = {
            "cat": str(k.Cat), "consumable": bool(k.Consumable), "trophy": bool(k.Trophy),
            "rare": bool(k.Rare), "rareResource": bool(k.RareResource),
        }
    return out
