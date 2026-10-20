"""Item mods (affixes), essences and the mod's own items, as the game defines and shows them.

- Affixes: LootCatalog (parsed from the embedded loot.catalog.json). Lines are rendered like the
  item tooltip (ItemTooltip, "details" view): template affixes as string.Format(Shown, value),
  auto-text affixes as StatText.DescribeMod of each rolled mod (GearEnvelope.Affix.ModAt). Values
  are rolled like LootRoller.Materialize: LootRoller.Final(tier min/max, slot multiplier, step).
  Each tier is rendered at its minimum and maximum and merged into "(min-max)" ranges.
- Slot multipliers (LootRoller.SlotMult): affix values scale with the item slot; local and unscaled
  affixes don't (MultFor).
- Sources: an affix rolls on loot when Generation is on. Essences (RuneActions.Essences) add an
  affix of their element family (tiers up to their cap); a boss essence also adds affixes of its
  boss family, which never roll otherwise (LootRoller.AddEssence). Anything else is not generated.
- Mod items (Runes.All): names, actions and flavor as the game registers them.
"""

import re

# LootRoller.SlotMult values, by what the item is.
SLOT_MULTS = {"base": 1.0, "one_handed": 0.7, "two_handed": 1.5, "chest": 1.5, "legs": 0.7, "tower": 1.5, "buckler": 0.8}
_NUMBER = re.compile(r"[-−]?\d+(?:[.,]\d+)?")
_INT_MAX = 2**31 - 1


def _num(v: float) -> str:
    """ItemTooltip's num2: whole numbers without decimals, else up to two."""
    if abs(v - round(v)) < 0.001:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _merge(low: str, high: str) -> str:
    """Two renderings of the same line at the tier's min and max -> one line with ranges."""
    if _NUMBER.sub("#", low) != _NUMBER.sub("#", high):
        return low if low == high else f"{low} … {high}"
    parts = _NUMBER.split(low)
    out = [part + (a if a == b else f"({a}–{b})") for part, a, b in zip(parts, _NUMBER.findall(low), _NUMBER.findall(high))]
    return "".join(out) + parts[-1]


def _line(d, tier, rolled: float) -> str:
    """One affix line at a rolled value, as the item tooltip writes it."""
    from PassiveTree import StatText
    from PassiveTree.Loot import GearEnvelope

    if not d.AutoText:
        return d.Shown.replace("{0}", _num(rolled))
    affix = GearEnvelope.Affix()
    affix.Def, affix.Tier, affix.Place, affix.Target = d.Id, tier.Id, d.Place, d.Target
    for m in d.Mods:
        raw = GearEnvelope.RawMod()
        raw.Stat, raw.Form, raw.Rolled, raw.Value = int(m.Stat), int(m.Form), rolled, rolled * m.Scale
        if m.Overs is not None:
            raw.Overs = [int(o) for o in m.Overs]
        affix.Mods.Add(raw)
    return ", ".join(StatText.DescribeMod(affix.ModAt(i)) for i in range(affix.Mods.Count) if affix.Mods[i].Known)


def _affix(d, boss_families: set) -> dict:
    from PassiveTree.Loot import LootRoller

    scaled = d.Scaled and str(d.Target) != "Local"
    mults = SLOT_MULTS if scaled else {"base": 1.0}
    tiers = []
    for t in d.Tiers:
        text = {
            name: _merge(_line(d, t, LootRoller.Final(t.Min, mult, t.Step)), _line(d, t, LootRoller.Final(t.Max, mult, t.Step)))
            for name, mult in mults.items()
        }
        tiers.append({
            "id": t.Id, "min": t.Min, "max": t.Max, "step": t.Step,
            "minLevel": t.MinLevel, "maxLevel": t.MaxLevel if t.MaxLevel < _INT_MAX else None,
            "weight": t.Weight, "special": bool(t.Special), "text": text,
        })
    families = [str(f) for f in d.Families]
    boss = [f for f in families if f in boss_families]
    return {
        "id": d.Id,
        "text": d.Shown,
        "place": str(d.Place).lower(),
        "target": str(d.Target).lower(),
        "group": d.Group or None,
        "families": families,
        "allowAll": [str(x) for x in d.AllowAll],
        "allowAny": [str(x) for x in d.AllowAny],
        "denyAny": [str(x) for x in d.DenyAny],
        "minLevel": d.MinLevel,
        "maxLevel": d.MaxLevel if d.MaxLevel < _INT_MAX else None,
        "weight": d.Weight,
        "generation": bool(d.Generation),
        "scaled": scaled,
        "auto": bool(d.AutoText),
        # Where it comes from: loot rolls, a boss essence only, or nowhere.
        "source": "loot" if d.Generation else ("essence" if boss else "none"),
        "bossFamilies": boss,
        "tiers": tiers,
    }


def render_loot(errors: list) -> dict:
    from PassiveTree import L, Runes
    from PassiveTree.Loot import LootCatalog, RuneActions

    LootCatalog.Ensure()
    essences = {kv.Key: {"family": kv.Value.Family, "boss": kv.Value.Boss or None, "cap": kv.Value.Cap} for kv in RuneActions.Essences}
    boss_families = {e["boss"] for e in essences.values() if e["boss"]}

    affixes = []
    for d in LootCatalog.Affixes:
        try:
            affixes.append(_affix(d, boss_families))
        except Exception as ex:  # one bad affix must not lose the rest
            errors.append({"affix": d.Id, "error": str(ex).split("\n")[0]})

    items = {
        k.Id: {
            "name": L.Id(f"item.{k.Id}.name", k.Name),
            "action": L.Id(f"item.{k.Id}.action", k.Action) if k.Action else "",
            "flavor": L.Id(f"item.{k.Id}.flavor", k.Flavor) if k.Flavor else "",
            "base": k.BaseItem or None,
            "recipe": k.Recipe or None,
        }
        for k in Runes.All
    }
    return {"affixes": affixes, "essences": essences, "items": items, "slotMults": SLOT_MULTS, "biomes": _biomes()}


def _biomes() -> list[dict]:
    """The mod's item level per biome (BiomeLevels.Of), lowest first: Meadows 1, Black Forest 19...;
    "band": levels until the next biome's (BiomeLevels.Band), where full experience there ends."""
    from System import AppDomain, Enum
    from PassiveTree import BiomeLevels

    biome = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "assembly_valheim").GetType("Heightmap+Biome")
    out = []
    for name in Enum.GetNames(biome):
        value = Enum.Parse(biome, name)
        level = int(BiomeLevels.Of(value))
        if level > 0:
            out.append({"id": str(name), "level": level, "band": int(BiomeLevels.Band(value))})
    return sorted(out, key=lambda b: (b["level"], b["id"]))
