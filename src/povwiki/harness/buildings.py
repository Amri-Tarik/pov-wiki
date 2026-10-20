"""The mod's buildable pieces, as its Make() methods build them.

Each one copies a Valheim piece (its cost, station and category come from there: pieces.json of
`povwiki valheim`) and overrides its name, description and icon, sometimes adds to its cost or
moves it to another station. The prefabs only exist in a running game, so this lists what each
Make() changes, reading the mod's own tables where it has them:
- Azurite Kiln (AzuriteKiln.Make): a smelter whose conversions are AzuriteKiln.Conversions.
- Rune Carver Table (RuneCarverTable.Make): its cost is written inline (no table); the station
  for the mod's runes, rings and belts.
- Inscription Gate (GoldlightGate.Make): portal_wood + GoldlightGate.Extra; built once a craft
  mastery grants Stat.GoldlightGate.
- Vacuum Chest (VacuumChest.Make): piece_chest + VacuumChest.Extra, built at the Rune Carver
  Table; needs Stat.VacuumChest. Radius and timing: its constants.
- Wild Sowing (WildSowing.Build): one Cultivator sapling per wild plant that regrows; the plants
  come from Valheim's Pickables, so the page works them out (herbs, excluded plants and seeds
  are listed here).
Keep in sync with those Make() methods.
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


def _asm():
    from System import AppDomain

    return next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")


def _static(type_name: str, field: str):
    return _asm().GetType(f"PassiveTree.{type_name}").GetField(field, _ANY).GetValue(None)


def _pairs(type_name: str, field: str) -> list[dict]:
    """A (string prefab, int amount)[] cost table."""
    return [{"item": str(t.Item1), "amount": int(t.Item2)} for t in _static(type_name, field)]


def render_buildings(errors: list) -> list[dict]:
    from PassiveTree import L

    def text(key: str) -> str:
        return L.Id(key, "") or ""

    out = []
    try:
        out.append({
            "id": "PT_AzuriteKiln", "source": str(_static("AzuriteKiln", "Source")),
            "name": text("piece.PT_AzuriteKiln.name"), "description": text("piece.PT_AzuriteKiln.desc"),
            "icon": "PassiveTree.model.azurite-kiln-icon.png",
            "conversion": [{"from": str(c.Item1), "to": str(c.Item2), "yield": int(c.Item3)}
                           for c in _static("AzuriteKiln", "Conversions")],
        })
        out.append({
            "id": "PT_RuneCarverTable", "source": str(_static("RuneCarverTable", "Source")),
            "name": text("piece.PT_RuneCarverTable.name"), "description": "",
            "icon": "PassiveTree.model.runecarver-table-icon.png",
            "resources": [{"item": "Stone", "amount": 10}, {"item": "Wood", "amount": 5}],  # inline in Make()
            "station": None, "craftingStation": True,
        })
        out.append({
            "id": "PT_GoldlightGate", "source": str(_static("GoldlightGate", "Source")),
            "name": text("piece.PT_GoldlightGate.name"), "description": text("piece.PT_GoldlightGate.desc"),
            "icon": "PassiveTree.goldgate.icon.png", "extra": _pairs("GoldlightGate", "Extra"),
            "unlock": "GoldlightGate", "maxGates": int(_static("GoldlightGate", "MaxGates")),
        })
        keys, names = _static("VacuumChest", "CatKeys"), _static("VacuumChest", "CatNames")
        out.append({
            "id": "PT_VacuumBox", "source": str(_static("VacuumChest", "Source")),
            "name": text("piece.PT_VacuumBox.name"), "description": text("piece.PT_VacuumBox.desc"),
            "icon": None, "extra": _pairs("VacuumChest", "Extra"), "station": "PT_RuneCarverTable",
            "unlock": "VacuumChest",
            "radius": [float(_static("VacuumChest", n)) for n in ("RadiusMin", "RadiusDefault", "RadiusMax")],
            "every": float(_static("VacuumChest", "Every")), "feedPerTick": int(_static("VacuumChest", "FeedPerTick")),
            "categories": [L.Id(f"ui.vacuum.cat.{k}", n) for k, n in zip(keys, names)],
        })
        seeds = _static("CraftItems", "Seeds")
        out.append({
            "id": "PT_wild_", "source": "sapling_carrot", "tool": "Cultivator",
            "description": text("ui.wild-sowing.wild-growth-planted-on-cultivated"),
            "excluded": sorted(str(x) for x in _static("WildSowing", "animal")),
            "herbs": sorted(str(x) for x in _static("WildSowing", "herbs")),
            "seeds": {str(kv.Key): str(kv.Value.Item1) for kv in seeds},
            "seedNames": {str(kv.Value.Item1): L.Id(f"item.{kv.Value.Item1}.name", str(kv.Value.Item2)) for kv in seeds},
        })
    except Exception as ex:
        errors.append({"buildings": str(ex).split("\n")[0]})
    return out
