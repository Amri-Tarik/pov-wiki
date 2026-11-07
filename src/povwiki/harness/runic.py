"""Runic crafting (PassiveTree.RunicCraft, 6.0.0): the Runic Anvil's stages, the special ores and
their veins, the alloys and the glyphs, as the mod's own tables define them.

- Anvil.Stages: each stage's name (piece.runicanvil.stage<N>), cost and biome; Defs.SlotsByStage.
- Defs: the action's base cost and dust, the base critical chance, every alloy (AlloyDef) and glyph
  (GlyphDef) with its potential, dust and divine dust cost (GlyphDef.Dust/Divine by value class).
  An alloy's theme is the enchantment theme it belongs to (Enchants.Themes), named like
  ItemLines.Of names it; the affixes it favours are those its Matches accepts (LootCatalog.Affixes).
- Item lines: as ItemLines.Of writes them (runic.line.*), in the game's language.
- Veins.All: each vein's ore, pickaxe tier, ore per vein and its chance per 128 m cell by biome.
- OreBonus.Table: the unusual ores that may come with a unit of ordinary ore, and their chances.
- Glyph drops: LootCatalog.GlyphChances (catalog "glyphSources") over GlyphLoot.Default, and the
  catalog's glyph weights and first biomes (LootCatalog.Glyphs) over GlyphDef's.
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


def _type(name: str):
    from System import AppDomain

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    return asm.GetType(f"PassiveTree.RunicCraft.{name}")


def _field(type_name: str, field: str):
    return _type(type_name).GetField(field, _ANY).GetValue(None)


def render_runic(errors: list) -> dict:
    if _type("Defs") is None:  # before 6.0.0
        return {}
    try:
        return _render()
    except Exception as ex:
        errors.append({"runic": str(ex).split("\n")[0]})
        return {}


def _render() -> dict:
    from PassiveTree import L
    from PassiveTree.Loot import LootCatalog
    from PassiveTree.RunicCraft import Anvil, Defs, Enchants, ItemMarks

    LootCatalog.Ensure()

    def stage_of(biome) -> int:
        return int(Defs.Stage(biome))

    stages = []
    for i, s in enumerate(Anvil.Stages):
        stages.append({
            "name": L.Id(f"piece.runicanvil.stage{i}", s.Name), "biome": str(s.Biome),
            "cost": [{"item": str(c.Item1), "amount": int(c.Item2)} for c in s.Cost],
            "slots": int(Defs.SlotsByStage[i]),
        })

    themes = {}
    for t in Enchants.Themes:
        if t.Alloy is not None:
            themes[t.Alloy.Id] = {"id": t.Id, "name": Enchants.ThemeName(t)}

    affixes = list(LootCatalog.Affixes)
    alloys = []
    for a in Defs.Alloys:
        theme = themes.get(a.Id)
        theme_word = theme["name"].lower() if theme else a.Name  # ItemLines.Of: ThemeName(...).ToLowerInvariant()
        alloys.append({
            "id": a.Id, "ore": a.Ore,
            "name": L.Id(f"item.{a.Id}.name", a.Name), "oreName": L.Id(f"item.{a.Ore}.name", a.OreName),
            "flavor": L.Id(f"item.{a.Id}.flavor", a.Lore), "oreFlavor": L.Id(f"item.{a.Ore}.flavor", a.OreLore),
            "cost": int(a.Cost), "dust": int(a.Dust), "weight": int(a.Weight),
            "theme": theme,
            "lines": [L.Id("runic.line.alloy", "Forging: {0} properties far more likely").replace("{0}", theme_word),
                      L.Id("runic.line.cost", "Action cost: +{0} potential, +{1} azurite dust")
                      .replace("{0}", str(a.Cost)).replace("{1}", str(a.Dust))],
            "oreLines": [L.Id("runic.line.ore", "Smelts into {0}").replace("{0}", L.Id(f"item.{a.Id}.name", a.Name))],
            # Every catalog affix the alloy favours, wherever it can roll (the forge pool is per item).
            "affixes": [d.Id for d in affixes if d.Generation and a.Matches.Invoke(d)],
        })

    weights = {str(kv.Key): (float(kv.Value.Item1), kv.Value.Item2) for kv in LootCatalog.Glyphs}
    glyphs = []
    for g in Defs.Glyphs:
        weight, first = weights.get(g.Id, (float(g.Weight), g.FirstBiome))
        cost_line = (L.Id("runic.line.cost-divine", "Action cost: +{0} potential, +{1} azurite dust, +{2} divine dust")
                     if g.Divine > 0 else L.Id("runic.line.cost", "Action cost: +{0} potential, +{1} azurite dust"))
        glyphs.append({
            "id": g.Id, "name": L.Id(f"item.{g.Id}.name", g.Name),
            "effect": L.Id(f"item.{g.Id}.effect", g.Effect), "flavor": L.Id(f"item.{g.Id}.flavor", g.Lore),
            "cost": int(g.Cost), "dust": int(g.Dust), "divine": int(g.Divine), "value": str(g.Value),
            "weight": weight, "firstBiome": str(first), "stage": stage_of(first),
            "main": bool(g.Main), "op": str(g.Op), "support": str(g.Support),
            "lines": [L.Id(f"item.{g.Id}.effect", g.Effect),
                      cost_line.replace("{0}", str(g.Cost)).replace("{1}", str(g.Dust)).replace("{2}", str(g.Divine))],
        })

    veins = []
    for v in _field("Veins", "All"):
        veins.append({
            "id": v.Id, "ore": v.Ore, "name": L.Id(f"piece.{v.Id}.name", v.Name),
            "tier": int(v.Tier), "min": int(v.Min), "max": int(v.Max), "health": float(v.Health),
            "rates": [{"biome": str(r.Item1), "rate": float(r.Item2)} for r in v.Rates],
        })
    ore_table = {str(kv.Key): [{"ore": str(t.Item1), "chance": float(t.Item2)} for t in kv.Value]
                 for kv in _field("OreBonus", "Table")}

    return {
        "potential": int(Defs.Potential), "baseCost": int(Defs.BaseCost), "baseDust": int(Defs.BaseDust),
        "baseCrit": float(Defs.BaseCritChance), "maxSlots": int(Defs.MaxSlots),
        "dust": Defs.Dust, "divineDust": Defs.DivineDust,
        "prefixes": int(LootCatalog.MaxPrefixes), "suffixes": int(LootCatalog.MaxSuffixes),
        "levelCap": int(ItemMarks.LevelCap), "durabilityStep": float(ItemMarks.DurabilityStep),
        "anvil": {"id": Anvil.Id, "stages": stages},
        "alloys": alloys, "glyphs": glyphs, "veins": veins, "oreChances": ore_table,
        "scarlet": str(_field("OreBonus", "Scarlet")),
        "glyphChances": {str(kv.Key): float(kv.Value) for kv in LootCatalog.GlyphChances},
        "stageNames": _stage_biomes(),
        # Veins (the seeding loop, Settle): one roll per cell, never this close to a building, moved at most the
        # last of Rings when its spot is taken.
        "veinPlacement": {"cell": float(_field("Veins", "Cell")), "buildGap": float(_field("Veins", "BuildGap")),
                          "maxSlope": float(_field("Veins", "MaxSlope")), "shift": float(max(_field("Veins", "Rings")))},
    }


def _stage_biomes() -> list[str]:
    """The biome of each glyph stage (Defs.Stage), lowest first."""
    from System import AppDomain, Enum
    from PassiveTree.RunicCraft import Defs

    biome = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "assembly_valheim").GetType("Heightmap+Biome")
    by_stage = {}
    for name in ("Meadows", "BlackForest", "Swamp", "Mountain", "Plains", "Mistlands", "AshLands", "DeepNorth"):
        by_stage.setdefault(int(Defs.Stage(Enum.Parse(biome, name))), name)
    return [by_stage[i] for i in sorted(by_stage)]
