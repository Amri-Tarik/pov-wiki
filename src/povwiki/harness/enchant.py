"""Enchantments at the Runecarver Table (6.0: Enchants, EnchantLoot), as the Enchant tab shows them.

- Rows: Enchants.Rows, built by the mod's own code from the loot catalog (one row per affix it
  accepts, its tiers T5..T1 picked from the affix's tiers, T0 from its special tier or the
  catalog's "t0" map), with the theme or boss whose scroll opens it.
- Tier lines: as EnchantWindow.Range writes them: Enchants.Line with the tier's min–max ("0.#").
- Tabs: Enchants.Tabs; a row is on a tab when it fits the tab's sample item (Enchants.OnTab). The
  game reads the sample's tags from the live ObjectDB; here they are the rendered items' tags
  (harness/items.py) put into an ItemTags. The jewellery tab has no sample: a row is on it when it
  fits one of the mod's belts or rings (JewelleryBases; the game stops at the first six it finds).
- Scrolls: their names and effect lines (EnchantLoot.Name / Effect), the scroll stage of each
  biome (EnchantLoot.LevelOf(GlyphLoot.Stage): Defs.Stage of the biome, the ocean as the swamp),
  the level from which bosses drop exalted scrolls (EnchantLoot.PerfectFrom), costs
  (Enchants.CostOf, RemoveCost).
"""

import clr
from System import Activator, AppDomain, Enum, Single
from System.Reflection import BindingFlags

_INSTANCE = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic


def _num(v: float) -> str:
    """EnchantWindow.Range's Num: v.ToString(v % 1 == 0 ? "0" : "0.#")."""
    f = Single(v)
    return f.ToString("0" if float(v) % 1 == 0 else "0.#")


def _range(row, i: int) -> tuple[str, str]:
    """EnchantWindow.Range: the tier's line with its min–max; and that min–max alone."""
    from PassiveTree.RunicCraft import Enchants

    tier, owner = row.Tiers[i], row.Owners[i]
    if tier is None or owner is None:
        return "", ""
    if owner.AutoText:
        lo, hi = abs(float(tier.Min)), abs(float(tier.Max))
        lo, hi = min(lo, hi), max(lo, hi)
        number = _num(lo) if abs(lo - hi) < 1e-6 else f"{_num(lo)}–{_num(hi)}"
        return str(Enchants.Line(owner, number, float(tier.Max) < 0)), number
    number = _num(tier.Min) if abs(float(tier.Min) - float(tier.Max)) < 1e-6 else f"{_num(tier.Min)}–{_num(tier.Max)}"
    return str(Enchants.Line(owner, number, False)), number


def _tags(tag_list: list[str]):
    """An ItemTags holding these tags (its set is private; the game builds it from an item)."""
    from PassiveTree.Loot import ItemTags

    t = clr.GetClrType(ItemTags)
    tags = Activator.CreateInstance(t, True)
    s = t.GetField("set", _INSTANCE).GetValue(tags)
    for tag in tag_list:
        s.Add(tag)
    return tags


def _biome_type():
    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "assembly_valheim")
    return asm.GetType("Heightmap+Biome")


def render_enchant(items: dict, errors: list) -> dict:
    try:
        from PassiveTree.RunicCraft import EnchantLoot, Enchants
    except ImportError:  # before 6.0
        return {}
    from PassiveTree import BiomeLevels, L, LootAffixes
    from PassiveTree.Loot import LootCatalog
    from PassiveTree.RunicCraft import Defs

    LootCatalog.Ensure()
    tabs = []
    for t in Enchants.Tabs:
        if t.Sample is not None:
            info = items.get(t.Sample)
            samples = [info["tags"]] if info else []
        else:  # Enchants.JewelleryBases: belts and rings without a unique of their own
            samples = [v["tags"] for p, v in items.items()
                       if ("belt" in v["tags"] or "ring" in v["tags"]) and not LootAffixes.HasUnique(p)]
        tabs.append({"id": t.Id, "name": str(Enchants.TabName(t)), "sample": t.Sample,
                     "fits": [_tags(s) for s in samples], "rows": []})

    rows = []
    for r in Enchants.Rows:
        try:
            tiers = []
            for i in range(6):
                tier = r.Tiers[i]
                if tier is None:
                    tiers.append(None)
                    continue
                dust, divine = Enchants.CostOf(i, 0, 0)[-2:]
                text, number = _range(r, i)
                tiers.append({"label": str(Enchants.Labels[i]), "owner": r.Owners[i].Id, "tier": tier.Id,
                              "min": float(tier.Min), "max": float(tier.Max), "text": text, "number": number,
                              "dust": int(dust), "divine": int(divine)})
            row = {"id": r.Id, "name": str(EnchantLoot.RowName(r)), "place": str(r.Place).lower(),
                   "theme": r.Theme.Id if r.Theme is not None else None, "boss": r.Boss,
                   "tiers": tiers}
            for t in tabs:
                if any(r.Def.FitsTags(tags) for tags in t["fits"]):
                    t["rows"].append(r.Id)
            if r.Tiers[5] is not None:
                row["zeroScroll"] = str(EnchantLoot.Name(f"t0:{r.Id}"))
            rows.append(row)
        except Exception as ex:  # one bad row must not lose the rest
            errors.append({"enchant": r.Id, "error": str(ex).split("\n")[0]})
    for t in tabs:
        del t["fits"]

    themes = [{"id": t.Id, "name": str(Enchants.ThemeName(t)),
               "color": "#%02x%02x%02x" % tuple(round(c * 255) for c in (t.Color.r, t.Color.g, t.Color.b)),
               "scrolls": [str(EnchantLoot.Name(f"theme:{t.Id}:{n}")) for n in range(1, 6)]}
              for t in Enchants.Themes]
    bosses = [{"family": b.Item1, "prefab": b.Item2, "name": str(EnchantLoot.BossName(b.Item2)),
               "scroll": str(EnchantLoot.Name(f"boss:{b.Item2}")), "rows": bool(Enchants.HasBossRows(b.Item2))}
              for b in Enchants.Bosses]

    # The theme scroll stage of each biome's loot (GlyphLoot.Stage: the ocean counts as the swamp).
    biome = _biome_type()
    stages = {}
    for name in Enum.GetNames(biome):
        value = Enum.Parse(biome, name)
        if int(BiomeLevels.Of(value)) <= 0:
            continue
        b = Enum.Parse(biome, "Swamp") if name == "Ocean" else value
        stages[str(name)] = int(EnchantLoot.LevelOf(Defs.Stage(b)))

    costs = []
    for i in range(6):
        dust, divine = Enchants.CostOf(i, 0, 0)[-2:]
        costs.append({"label": str(Enchants.Labels[i]), "dust": int(dust), "divine": int(divine)})

    def say(key: str) -> str:
        return str(L.Id(key, ""))

    return {
        "rows": rows, "tabs": tabs, "themes": themes, "bosses": bosses, "stages": stages, "costs": costs,
        "removeCost": int(Enchants.RemoveCost), "bossRange": float(EnchantLoot.BossRange),
        "exaltedAbove": int(BiomeLevels.Of(Enum.Parse(biome, "Mistlands"))),
        "effects": {"theme": [str(EnchantLoot.Effect(f"theme:fire:{n}")) for n in range(1, 6)],
                    "boss": str(EnchantLoot.Effect("boss:Eikthyr")), "zero": str(EnchantLoot.Effect("t0:x"))},
        "items": {p: {"name": say(f"item.{p}.name"), "text": say(f"item.{p}.text")} for p in EnchantLoot.Prefabs},
        "text": {k: say(k) for k in ("enchant.ui.prefixes", "enchant.ui.suffixes", "enchant.ui.tab", "enchant.scroll.foreign",
                                     "enchant.scroll.use", "enchant.why.one", "enchant.why.group", "enchant.why.unique",
                                     "enchant.why.no-prefix", "enchant.why.no-suffix")},
    }
