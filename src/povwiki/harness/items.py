"""Valheim items as the mod sees them: tags, defence type and values, crafted item level.

Each extracted Valheim item (`povwiki valheim`) is rebuilt as a real ItemDrop.ItemData with its
SharedData filled from the extracted fields; Unity objects it references become stand-ins
(harness/unity.py): its prefab (by name) and the status effects it applies (with their fields).
Then the mod's own code runs on it: ItemTags.Of (what mods can roll on it),
EquipmentDefences.Kind / Of (armour, evasion or rune shield, and how much per quality).

The crafted item level (CraftLevel.Of) walks recipe materials, looking recipes up in the game's
live ObjectDB, which doesn't exist here: that walk is mirrored over the extracted recipes, using
the mod's own material table (CraftLevel.materials, ByPrefix) and BiomeLevels.
"""

import json
from pathlib import Path

import clr
from System import Activator, AppDomain, Boolean, Enum, String
from System.Reflection import BindingFlags
from System.Runtime.CompilerServices import RuntimeHelpers

from . import unity

_ALL = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
_INSTANCE = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic


def _asm(name: str):
    return next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == name)


class _Builder:
    def __init__(self, effects: dict):
        clr.AddReference("UnityEngine.CoreModule")
        import UnityEngine

        self.unity_object = clr.GetClrType(UnityEngine.Object)
        self.game_object = clr.GetClrType(UnityEngine.GameObject)
        self.valheim = _asm("assembly_valheim")
        self.item_data = self.valheim.GetType("ItemDrop+ItemData")
        self.shared_data = self.valheim.GetType("ItemDrop+ItemData+SharedData")
        self.status_effect = self.valheim.GetType("StatusEffect")
        self.effects = effects
        self._effect_cache: dict = {}

    def _is_unity(self, t) -> bool:
        """Unity objects, and Unity classes wrapping native data (AnimationCurve, Gradient...):
        never created here; their finalizers call native code and would kill the process."""
        if t.IsArray:
            return self._is_unity(t.GetElementType())
        if t.IsGenericType:
            return any(self._is_unity(a) for a in t.GetGenericArguments())
        if not t.IsValueType and (t.Namespace or "").startswith("UnityEngine"):
            return True
        return self.unity_object.IsAssignableFrom(t)

    def _effect(self, name: str):
        """A status effect stand-in of its real class, with its fields filled."""
        if name not in self._effect_cache:
            data = self.effects.get(name)
            se = None
            if data:
                cls = self.valheim.GetType(data["class"] or "") or self.status_effect
                se = unity.stand_in(cls, name)
                self.fill(se, data["fields"])
            self._effect_cache[name] = se
        return self._effect_cache[name]

    def fill(self, obj, data: dict) -> None:
        """Copy extracted type-tree values onto a .NET object, field by field (recursively)."""
        t = obj.GetType()
        for key, value in data.items():
            f = t.GetField(key, _INSTANCE)
            if f is None or value is None:
                continue
            ft = f.FieldType
            if self._is_unity(ft):
                if isinstance(value, str) and self.status_effect.IsAssignableFrom(ft):
                    se = self._effect(value)
                    if se is not None:
                        f.SetValue(obj, se)
                continue
            if ft.IsEnum:
                f.SetValue(obj, Enum.ToObject(ft, int(value)))
            elif ft == clr.GetClrType(String):
                f.SetValue(obj, str(value))
            elif ft.IsPrimitive:
                if ft == clr.GetClrType(Boolean):
                    value = bool(value)  # type trees store booleans as 0/1
                setattr(obj, key, value)  # pythonnet converts to the field's exact type
            elif isinstance(value, dict) and not ft.IsArray and not ft.IsGenericType and not ft.IsAbstract:
                # Classes are created without running their constructor: some (Attack) build
                # native-backed Unity objects there, whose finalizers then crash the process.
                # The extracted data fills every serialized field anyway.
                child = f.GetValue(obj) or (Activator.CreateInstance(ft) if ft.IsValueType else RuntimeHelpers.GetUninitializedObject(ft))
                self.fill(child, value)
                f.SetValue(obj, child)  # structs: write the filled copy back

    def item(self, prefab: str, shared: dict):
        data = Activator.CreateInstance(self.item_data)
        s = Activator.CreateInstance(self.shared_data)
        self.fill(s, shared)
        data.m_shared = s
        data.m_quality = 1
        data.m_dropPrefab = unity.stand_in(self.game_object, prefab)
        return data


_hooks: list = []


def _no_world_level(item_data) -> None:
    """ItemData.GetArmor adds world level x Game.instance.m_worldLevelGearBaseAC, and there is no
    running Game here: use the same formula at world level 0 (a world without modifiers)."""
    if _hooks:
        return
    from MonoMod.RuntimeDetour import Hook
    from System import Func, Int32, Object, Single

    def armor(self, quality, world_level):
        s = self.m_shared
        return s.m_armor + max(0, quality - 1) * s.m_armorPerLevel

    method = item_data.GetMethod("GetArmor", _INSTANCE, None, [clr.GetClrType(Int32), clr.GetClrType(Single)], None)
    _hooks.append(Hook(method, Func[Object, Int32, Single, Single](armor)))


def render_items(valheim: Path, errors: list) -> dict:
    """{prefab: {tags, defence, defences: [per quality], craftLevel}} for every Valheim item."""
    from PassiveTree import BiomeLevels, EquipmentDefences
    from PassiveTree.Loot import CraftLevel, ItemTags

    unity.install()
    _no_world_level(_asm("assembly_valheim").GetType("ItemDrop+ItemData"))
    items = json.loads((valheim / "items.json").read_text(encoding="utf-8"))
    effects = json.loads((valheim / "effects.json").read_text(encoding="utf-8"))
    recipes = json.loads((valheim / "recipes.json").read_text(encoding="utf-8"))
    build = _Builder(effects)
    tag_set = clr.GetClrType(ItemTags).GetField("set", _INSTANCE)
    craft_level = _CraftLevel(recipes, CraftLevel, BiomeLevels)

    out = {}
    for prefab, shared in items.items():
        try:
            item = build.item(prefab, shared)
            tags = sorted(str(t) for t in tag_set.GetValue(ItemTags.Of(item)))
            wears = EquipmentDefences.Wear(item) or "shield" in tags
            defences = []
            if wears:
                for q in range(1, max(1, int(shared.get("m_maxQuality") or 1)) + 1):
                    d = EquipmentDefences.Of(item, q, -1.0)
                    defences.append({"armour": d.Armour, "evasion": d.Evasion, "runeShield": d.RuneShield})
            out[prefab] = {
                "tags": tags,
                "defence": str(EquipmentDefences.Kind(item)) if wears else None,
                "defences": defences,
                "craftLevel": craft_level.of(prefab),
                "implicits": _implicits(item, prefab),
            }
        except Exception as ex:  # one bad item must not lose the rest
            errors.append({"item": prefab, "error": str(ex).split("\n")[0]})
    out.update(_mod_items(items, build, tag_set, craft_level, errors))
    return out


def _implicits(item, prefab: str) -> list[dict]:
    """Implicit lines (Implicits.Rows): a range for rolled ones, a value per quality for the ones
    the item shows from its quality (belt upgrades, Megingjord's carry weight)."""
    import PassiveTree

    Implicits = getattr(PassiveTree, "Implicits", None)
    if Implicits is None:  # older versions
        return []
    for owner in ("Belts", "Rings"):  # they register their implicits on first use (Implicits.Rows)
        if (cls := getattr(PassiveTree, owner, None)) is not None:
            cls.Touch()
    bases = clr.GetClrType(Implicits).GetField("bases", _ALL).GetValue(None)
    if not bases.ContainsKey(prefab):
        return []
    rows = []
    for row in bases[prefab]:
        d, lo, hi = row.Item1, row.Item2, row.Item3
        if d.Shown is not None:
            values = []
            for q in range(1, max(1, item.m_shared.m_maxQuality) + 1):
                item.m_quality = q
                values.append(int(d.Shown(item)))
            item.m_quality = 1
            if any(values):  # the tooltip leaves a line out while its value is 0
                rows.append({"id": d.Id, "byQuality": [Implicits.Line(d, v) if v else None for v in values]})
        else:
            shown = Implicits.Range(lo, hi) or str(lo)
            rows.append({"id": d.Id, "text": Implicits.Line(d, shown), "min": lo, "max": hi})
    return rows


def _mod_items(items: dict, build: "_Builder", tag_set, craft_level: "_CraftLevel", errors: list) -> dict:
    """The mod's own gear. The game builds it at run time by copying a Valheim item and changing
    its shared data, so it is rebuilt the same way here: the source item's extracted data plus
    the mod's changes, then the mod's own code computes tags and implicits.

    - Rings.All, Belts.All: copies of Megingjord (Rings/Belts.Template), recipes at the rune
      carver table (RingRecipes, Belts.Recipes), how they drop.
    - Staves (StarterStaves, LinkStaves), Sceptres, rune chisels (RuneVein.Chisels): weapons and
      tools with their own damage, attack costs, durability and recipes. Tables the mod keeps as
      data (StarterStaves.rungs, RuneVein.Chisels) are read from it; values the mod writes inline
      in code (Spark/Blood Seal staves, staves of bonds, the sceptre) are mirrored below.
    Quivers (Quivers.cs) are left out: 5.1 never creates them (Quivers.Ensure is empty)."""
    from PassiveTree import L
    from PassiveTree.Loot import ItemTags, LootCatalog

    LootCatalog.Ensure()
    out = {}
    for spec in _rings_and_belts(items) + _weapons(items) + _bombs(items) + _rune(items):
        prefab = spec["id"]
        try:
            source = items.get(spec["source"]) or {}
            shared = {k: v for k, v in source.items() if k not in spec.get("drop", ())}
            shared.update(spec["overrides"])
            if spec.get("weaponKind"):
                _register_kind(prefab, spec["weaponKind"])
            item = build.item(prefab, shared)
            recipe = spec.get("recipe")
            if recipe:
                craft_level.recipe_of[prefab] = {"item": prefab, "enabled": True, "resources": recipe["resources"]}
            out[prefab] = {
                "tags": sorted(str(t) for t in tag_set.GetValue(ItemTags.Of(item))),
                "defence": None,
                "defences": [],
                "craftLevel": craft_level.of(prefab),
                "implicits": _implicits(item, prefab),
                "mod": {
                    "kind": spec["kind"],
                    "source": spec["source"],
                    "shared": {k: v for k, v in shared.items() if k not in ("m_icons",)},
                    "icon": spec["icon"],
                    "recipe": recipe,
                    **spec.get("drops", {}),
                    **(spec["extra"](item) if spec.get("extra") else {}),
                },
            }
        except Exception as ex:  # one bad item must not lose the rest
            errors.append({"item": prefab, "error": str(ex).split("\n")[0]})
    return out


def _register_kind(prefab: str, kind: str) -> None:
    """WeaponAffixes.Register: the mod tells its weapon code what kind each of its weapons is."""
    from PassiveTree import WeaponAffixes, WeaponKind
    from System import Enum

    WeaponAffixes.Register(prefab, Enum.Parse(clr.GetClrType(WeaponKind), kind))


def _rings_and_belts(items: dict) -> list[dict]:
    import PassiveTree
    from PassiveTree import L, Runes

    # Older versions have no rings (5.1) or no belts of their own.
    Rings, RingRecipes, Belts = (getattr(PassiveTree, n, None) for n in ("Rings", "RingRecipes", "Belts"))
    station = {"id": "PT_RuneCarverTable", "name": L.Id("piece.PT_RuneCarverTable.name", "Rune Carver Table")}
    common = {"m_itemType": 18, "m_maxStackSize": 1, "m_setName": "", "m_setSize": 0, "m_subtitle": "",
              "m_teleportable": True}
    drop = ("m_equipStatusEffect", "m_setStatusEffect")
    parts = clr.GetClrType(RingRecipes).GetField("parts", _ALL).GetValue(None) if RingRecipes else {}
    known = set(items) | {str(k.Id) for k in Runes.All}

    def spec(k, kind: str, overrides: dict, resources: list | None, drops: dict) -> dict:
        return {"id": str(k.Id), "source": "BeltStrength", "drop": drop, "kind": kind,
                "overrides": {**common, **overrides}, "icon": f"PassiveTree.item.{k.Id}.png", "drops": drops,
                "recipe": {"station": station, "stationLevel": 1, "resources": resources} if resources else None}

    specs = []
    for k in Rings.All if Rings else []:
        resources = None
        if parts.ContainsKey(k.Id):
            metal, essence = parts[k.Id].Item1, parts[k.Id].Item2
            resources = [{"item": metal, "amount": 10 if essence is None else 5, "perLevel": 0}]
            if essence is not None:
                resources.append({"item": essence, "amount": 1, "perLevel": 0})
            resources.append({"item": "PT_AzuriteDust", "amount": 40, "perLevel": 0})
        specs.append(spec(k, "ring", {
            "m_name": L.Id(f"item.{k.Id}.name", k.Name), "m_description": L.Id(f"item.{k.Id}.flavor", k.Flavor),
            "m_maxQuality": 1, "m_weight": 0.1,
        }, resources, {"biome": None if k.Everywhere else str(k.Biome), "everywhere": bool(k.Everywhere)}))
    for k in Belts.All if Belts else []:
        flavor = L.Id(f"item.{k.Id}.flavor", k.Flavor)
        if k.Quote is not None:
            flavor += "\n\n<i>" + L.Id(f"item.{k.Id}.quote", k.Quote) + "</i>"
        resources = None
        if not k.Unique and k.Recipe is not None:
            resources = []
            for part in k.Recipe:
                found = next((i for i in part.Item1 if i in known), None)
                if found is None:  # Belts.Recipe: no recipe when a material is missing
                    resources = None
                    break
                resources.append({"item": found, "amount": part.Item2, "perLevel": max(1, part.Item2 // 2)})
        specs.append(spec(k, "belt", {
            "m_name": L.Id(f"item.{k.Id}.name", k.Name), "m_description": flavor,
            "m_maxQuality": 1 if k.Unique else 3, "m_weight": 1.0,
        }, resources, {"unique": bool(k.Unique), "globalMinLevel": int(k.GlobalMinLevel) or None}))
    return specs


def _resources(ids, amounts, upgrades, flat: bool = False) -> list[dict]:
    """Recipe materials. flat: StarterStaves.UpgradeCost, every quality step costs the per-level
    amount once (vanilla multiplies it by the steps)."""
    return [{"item": i, "amount": int(a), "perLevel": int(u), **({"flat": True} if flat else {})}
            for i, a, u in zip(ids, amounts, upgrades)]


def _attack(source: dict, **costs) -> dict:
    """StarterAttack: the source attack with the mod's costs and no extra spawns."""
    attack = dict(source.get("m_attack") or {})
    attack.update({"m_attackHealthPercentage": 0.0, "m_attackHealthLowBlockUse": True, "m_consumeItem": False,
                   "m_destroyPreviousProjectile": False, "m_spawnOnHitChance": 0.0, "m_drawEitrDrain": 0.0,
                   "m_drawStaminaDrain": 0.0, "m_requiresReload": False, **costs})
    return attack


def _weapons(items: dict) -> list[dict]:
    """Staves, the sceptre and rune chisels (see _mod_items)."""
    import PassiveTree
    from PassiveTree import L

    if getattr(PassiveTree, "StarterStaves", None) is None:  # older versions
        return []
    workbench = "piece_workbench"
    starter = clr.GetClrType(PassiveTree.StarterStaves)
    calls = starter.GetField("Calls", _ALL)  # the summoning staves (5.2.0), which also made staves sturdier
    durability = (200.0, 50.0) if calls is not None else (80.0, 20.0)
    gone = ("m_consumeStatusEffect", "m_attackStatusEffect", "m_spawnOnHit", "m_spawnOnHitTerrain")

    def staff(source: str, prefab: str, name: str, skill: int, stamina: float, health: float, eitr: float) -> dict:
        """StarterStaves.Clone."""
        return {"m_name": L.Id(f"item.{prefab}.name", name), "m_skillType": skill, "m_weight": 1.5,
                "m_maxQuality": 3, "m_maxDurability": durability[0], "m_durabilityPerLevel": durability[1], "m_useDurability": True,
                "m_attack": _attack(items.get(source, {}), m_attackStamina=stamina, m_attackHealth=health,
                                    m_attackEitr=eitr),
                "m_secondaryAttack": {}, "m_ammoType": "", "m_attackForce": 5.0, "m_backstabBonus": 1.0}

    specs = []
    # Spark and Blood Seal staves (StarterStaves, built inline).
    specs.append({"id": "PT_StaffSpark", "source": "StaffFireball", "drop": gone, "kind": "weapon",
                  "weaponKind": "ElementalMagic", "icon": "vh:StaffFireball",
                  "overrides": {**staff("StaffFireball", "PT_StaffSpark", "Посох искры", 9, 14, 0, 4),
                                "m_description": L.Id("ui.staff.fires-a-fireball-that-explodes", "Fires a fireball that explodes on impact."),
                                "m_damages": {"m_fire": 6.0, "m_blunt": 5.0}, "m_damagesPerLevel": {"m_fire": 3.0, "m_blunt": 1.0}},
                  "recipe": {"station": workbench, "stationLevel": 1, "resources": _resources(
                      ["Wood", "Resin", "Coal", "SurtlingCore"], [10, 4, 2, 1], [5, 2, 1, 0], flat=True)}})
    blood = staff("StaffShield", "PT_StaffBloodSeal", "Посох кровавой печати", 10, 18, 6, 6)
    blood["m_attack"].update({"m_attackType": 3, "m_attackProjectile": None})
    specs.append({"id": "PT_StaffBloodSeal", "source": "StaffShield", "drop": gone, "kind": "weapon",
                  "weaponKind": "BloodMagic", "icon": "vh:StaffShield",
                  "overrides": {**blood, "m_description": L.Id("ui.staff.blood-seal-shields-you-and", "Blood Seal shields you and allies."),
                                "m_damages": {}, "m_damagesPerLevel": {}},
                  "recipe": {"station": workbench, "stationLevel": 1, "resources": _resources(
                      ["Wood", "LeatherScraps", "Raspberry"], [10, 4, 4], [5, 2, 2], flat=True)}})

    # The rung staves: StarterStaves.rungs (Source, CutBeam, Blow).
    rungs = starter.GetField("rungs", _ALL).GetValue(None)
    for r in rungs:
        source = next((f for f in r.From if _projectile_source(items.get(f), r)), "StaffFireball")
        attack = (items.get(source) or {}).get("m_attack") or {}
        shots, bursts = max(1, int(attack.get("m_projectiles") or 1)), max(1, int(attack.get("m_projectileBursts") or 1))
        if r.Volley > 0 and shots * bursts > 24:  # CutBeam
            shots, bursts = min(shots, r.Volley), max(1, r.Volley // shots)
        n = shots * bursts
        element = {"Fire": "m_fire", "Poison": "m_poison", "Frost": "m_frost"}.get(str(r.Kind), "m_lightning")
        overrides = staff(source, str(r.Id), r.Name, 9, float(r.Stamina), 0.0, float(r.Eitr))
        overrides["m_attack"].update({"m_projectiles": shots, "m_projectileBursts": bursts})
        overrides.update({
            "m_description": L.Id(f"ui.staff.{r.Id}.about", r.About),
            "m_damages": {"m_blunt": r.Blunt / n, element: r.Element / n},
            "m_damagesPerLevel": {element: r.PerLevel / n},
        })
        specs.append({"id": str(r.Id), "source": source, "drop": gone, "kind": "weapon", "weaponKind": "ElementalMagic",
                      "icon": f"vh:{source}", "overrides": overrides,
                      "recipe": {"station": workbench, "stationLevel": int(r.Bench),
                                 "resources": _resources(r.Mats, r.Amounts, r.Upgrades, flat=True)}})

    # The summoning staves: StarterStaves.Calls (SummonStaff), Dead Raiser copies that cost only stamina.
    resources = set(starter.Assembly.GetManifestResourceNames())
    for c in (calls.GetValue(None) if calls is not None else []):
        prefab = str(c.Id)
        overrides = staff("StaffSkeleton", prefab, c.Name, 10, float(c.Stamina), 0.0, 0.0)
        overrides["m_attack"].update({"m_attackType": 3, "m_attackProjectile": None, "m_attackHealthPercentage": 0.0})
        overrides.update({"m_description": L.Id(f"item.{prefab}.about", c.About), "m_damages": {}, "m_damagesPerLevel": {}})
        icon = next(i for i in (f"PassiveTree.item.{prefab}.png", "PassiveTree.item.PT_StaffBoneCall.png") if i in resources)
        specs.append({"id": prefab, "source": "StaffSkeleton", "drop": gone, "kind": "weapon", "weaponKind": "BloodMagic",
                      "icon": icon, "overrides": overrides,
                      "recipe": {"station": workbench, "stationLevel": int(c.Bench),
                                 "resources": _resources(c.Mats, c.Amounts, c.Upgrades, flat=True)}})

    # Staves of bonds (LinkStaves.Make), BloodMagic, no damage.
    for prefab, source, name, desc, station, level, mats, amounts, ups in (
        ("pov_staff_link_wood", "StaffGreenRoots", "Staff of Bonds",
         "Hold the attack to channel a beam. Touching an ally links you: what your links carry passes between you while the beam holds. Costs eitr while channelling; never harms anyone.",
         workbench, 2, ["Wood", "GreydwarfEye", "Resin"], [12, 4, 6], [4, 2, 2]),
        ("pov_staff_link_runic", "StaffShield", "Runic Staff of Bonds",
         "A reinforced staff of bonds: a longer beam and a cheaper channel. Hold the attack to link an ally you touch with the beam.",
         "piece_magetable", 1, ["YggdrasilWood", "Eitr", "BlackCore"], [10, 6, 1], [5, 3, 0]),
    ):
        specs.append({"id": prefab, "source": source, "drop": gone + ("m_equipStatusEffect",), "kind": "weapon",
                      "weaponKind": "BloodMagic", "icon": "PassiveTree.v2.icon.link.png",
                      "overrides": {"m_name": L.Id(f"item.{prefab}.name", name),
                                    "m_description": L.Id(f"item.{prefab}.description", desc), "m_skillType": 10,
                                    "m_damages": {}, "m_damagesPerLevel": {}, "m_maxQuality": 4,
                                    "m_maxDurability": 100.0, "m_durabilityPerLevel": 50.0, "m_useDurability": True,
                                    "m_weight": 2.0, "m_ammoType": "", "m_secondaryAttack": {}},
                      "recipe": {"station": station, "stationLevel": level, "resources": _resources(mats, amounts, ups)}})

    # Sceptre of the Pious (Sceptres): a club whose blows also call down Smite.
    if getattr(PassiveTree, "Sceptres", None) is not None:
        club = items.get("Club") or {}
        specs.append({"id": "PT_SceptrePious", "source": "Club", "drop": ("m_spawnOnHit", "m_spawnOnHitTerrain"),
                      "kind": "weapon", "weaponKind": "Scepters", "icon": "PassiveTree.item.PT_SceptrePious.png",
                      "overrides": {"m_name": L.Id("item.PT_SceptrePious.name", "Sceptre of the Pious"),
                                    "m_description": L.Id("item.PT_SceptrePious.description", "A priest's sceptre."),
                                    "m_damages": {"m_blunt": 10.0, "m_lightning": 20.0, "m_fire": 20.0},
                                    "m_damagesPerLevel": {"m_blunt": 5.0, "m_lightning": 10.0, "m_fire": 10.0},
                                    "m_attackForce": 10.0, "m_maxQuality": 4,
                                    "m_attack": {**(club.get("m_attack") or {}), "m_attackEitr": 5.0}},
                      "recipe": {"station": workbench, "stationLevel": 1, "resources": _resources(
                          ["Wood", "Resin", "Flint"], [10, 4, 4], [5, 2, 2])}})

    # Rune chisels (RuneVein.Chisels): azurite mining tools made from the flint knife.
    for k in getattr(getattr(PassiveTree, "RuneVein", None), "Chisels", None) or []:
        prefab = str(k.Id)
        specs.append({"id": prefab, "source": "KnifeFlint", "kind": "tool", "icon": f"PassiveTree.item.{prefab}.png",
                      "overrides": {"m_name": L.Id(f"item.{prefab}.name", k.Name),
                                    "m_description": L.Id(f"item.{prefab}.description", k.Desc), "m_skillType": 0,
                                    "m_damages": {"m_pickaxe": float(k.Power), "m_pierce": float(min(k.Power, 60))},
                                    "m_damagesPerLevel": {}, "m_toolTier": 0, "m_maxQuality": 4, "m_useDurability": True,
                                    "m_maxDurability": float(k.Durability), "m_durabilityPerLevel": 50.0,
                                    "m_attack": {**((items.get("SpearFlint") or items.get("KnifeFlint") or {}).get("m_attack") or {}),
                                                 "m_speedFactor": 0.0},
                                    "m_secondaryAttack": {}},
                      "recipe": {"station": "forge", "stationLevel": int(k.Station), "resources": _resources(
                          ["Wood", k.Hide, k.Metal], [2, 2, k.MetalAmount], [1, 1, k.MetalAmount // 2])}})
    return specs


def _blast(d) -> dict:
    """A DamageTypes struct as extracted item data: its non-zero damages."""
    return {k: float(getattr(d, k)) for k in _DAMAGE_FIELDS if float(getattr(d, k))}


_DAMAGE_FIELDS = ("m_blunt", "m_slash", "m_pierce", "m_fire", "m_frost", "m_lightning", "m_poison", "m_spirit")


def _bombs(items: dict) -> list[dict]:
    """The mod's bombs, copies of Valheim's with their own blast and recipe at the workbench:
    the Ember Bomb (StarterBomb) and the bomb ladder (BombLadder.rungs)."""
    import PassiveTree

    ladder, starter = getattr(PassiveTree, "BombLadder", None), getattr(PassiveTree, "StarterBomb", None)
    if ladder is None and starter is None:  # older versions
        return []
    from PassiveTree import L

    resources = set(clr.GetClrType(ladder or starter).Assembly.GetManifestResourceNames())

    def spec(prefab: str, source: str, name: str, about: str, blast: dict, weight: float, bench: int,
             cost: list, makes: int, bomb: dict) -> dict:
        icon = f"PassiveTree.item.{prefab}.png"
        stack = max(10, int((items.get(source) or {}).get("m_maxStackSize") or 1))
        return {"id": prefab, "source": source, "kind": "weapon", "weaponKind": "Bombs",
                "icon": icon if icon in resources else f"vh:{source}",
                "overrides": {"m_name": name, "m_description": about, "m_damages": blast, "m_damagesPerLevel": {},
                              "m_maxQuality": 1, "m_weight": weight, "m_maxStackSize": stack},
                "recipe": {"station": "piece_workbench", "stationLevel": bench, "makes": makes,
                           "resources": _resources([c[0] for c in cost], [c[1] for c in cost], [0] * len(cost))},
                "extra": lambda item, bomb=bomb: {"bomb": bomb}}

    specs = []
    if starter is not None:
        t = clr.GetClrType(starter)
        source = str(t.GetField("Source", _ALL).GetValue(None))
        specs.append(spec(
            "PT_BombEmber", source, L.Id("ui.starter-bomb.ember-bomb", "Ember Bomb"),
            L.Id("ui.starter-bomb.a-clay-pot-of-resin", "A clay pot of resin and embers. Bursts into fire where it lands; the blast is small enough to throw from behind a shield. Scales with bomb, fire and area bonuses."),
            _blast(starter.Damage()), 0.5, 1, [("Wood", 5), ("Resin", 3), ("Flint", 2)], 3,
            {"radius": float(t.GetField("Radius", _ALL).GetValue(None))}))
    for r in clr.GetClrType(ladder).GetField("rungs", _ALL).GetValue(None) if ladder is not None else []:
        prefab = str(r.Id)
        bomb = {"radius": round(float(r.Radius), 4)}
        if r.ThornsShare > 0:
            bomb.update({"thornsBase": round(float(r.ThornsBase), 4), "thornsShare": round(float(r.ThornsShare), 4)})
        if r.PullRange > 0:
            bomb.update({"pullRange": round(float(r.PullRange), 4), "pullSeconds": round(float(r.PullSeconds), 4)})
        if r.BreakShare > 0:
            bomb.update({"breakShare": round(float(r.BreakShare), 4), "breakSeconds": round(float(r.BreakSeconds), 4)})
        if r.TarSeconds > 0:
            bomb["tarSeconds"] = round(float(r.TarSeconds), 4)
        specs.append(spec(prefab, str(r.Source), L.Id(f"ui.bomb.{prefab}.name", r.Name), L.Id(f"ui.bomb.{prefab}.about", r.About),
                          _blast(r.Blast), 0.8, int(r.Bench), [(str(c.Item1), int(c.Item2)) for c in r.Cost], int(r.Amount), bomb))
    return specs


def _rune(items: dict) -> list[dict]:
    """The Rune of Resurrection (Resurrection.MakeRune): a Tankard copy whose durability is its
    charges, made at the rune carver table, that brings a dead companion back from its grave."""
    import PassiveTree

    res = getattr(PassiveTree, "Resurrection", None)
    if res is None:
        return []
    from PassiveTree import L

    t = clr.GetClrType(res)

    def per_quality(item) -> dict:
        charges, seconds = [], []
        for q in range(1, 5):
            item.m_quality = q
            charges.append(int(res.MaxCharges(item)))
            seconds.append(float(res.Seconds(item)))
        item.m_quality = 1
        return {"resurrection": {"charges": charges, "seconds": seconds, "range": float(t.GetField("Range", _ALL).GetValue(None))}}

    station = {"id": "PT_RuneCarverTable", "name": L.Id("piece.PT_RuneCarverTable.name", "Rune Carver Table")}
    return [{"id": "PT_RuneOfResurrection", "source": "Tankard", "kind": "utility", "icon": "PassiveTree.item.PT_RuneOfResurrection.png",
             "drop": ("m_consumeStatusEffect", "m_equipStatusEffect", "m_attackStatusEffect"),
             "overrides": {"m_name": L.Id("item.PT_RuneOfResurrection.name", "Rune of Resurrection"),
                           "m_description": L.Id("item.PT_RuneOfResurrection.flavor", "The green tree of life wakes in the stone when it is held over the fallen."),
                           "m_itemType": 3, "m_skillType": 0, "m_damages": {}, "m_damagesPerLevel": {}, "m_maxQuality": 4,
                           "m_weight": 0.5, "m_maxStackSize": 1, "m_value": 0, "m_teleportable": True, "m_useDurability": True,
                           "m_maxDurability": 3.0, "m_durabilityPerLevel": 1.0, "m_canBeReparied": True},
             "recipe": {"station": station, "stationLevel": 1, "resources": _resources(
                 ["PT_BlankRunestone", "PT_DivineAzurite", "PT_DivineAzuriteDust"], [1, 3, 60], [0, 2, 40])},
             "extra": per_quality}]


def _projectile_source(source: dict | None, rung) -> bool:
    """StarterStaves.Source: a source staff must shoot projectiles, and not a beam of more than
    24 unless the rung cuts it to a volley. (Its check on projectiles that spawn something needs
    the projectile prefab, which isn't extracted: the first projectile staff is taken.)"""
    attack = (source or {}).get("m_attack") or {}
    if int(attack.get("m_attackType") or 0) != 2 or not attack.get("m_attackProjectile"):
        return False
    shots = max(1, int(attack.get("m_projectiles") or 1)) * max(1, int(attack.get("m_projectileBursts") or 1))
    return shots <= 24 or rung.Volley > 0


def _reads_field(methods: list, name: str) -> bool:
    """Whether any of these methods loads a field of this name (an ldfld in its IL)."""
    for m in methods:
        il = bytes(bytearray(m.GetMethodBody().GetILAsByteArray()))
        for i in range(len(il) - 4):
            if il[i] != 0x7B:  # ldfld <token>
                continue
            try:
                if m.Module.ResolveField(int.from_bytes(il[i + 1:i + 5], "little")).Name == name:
                    return True
            except Exception:  # noqa: BLE001 - a 0x7B byte that isn't an opcode
                continue
    return False


class _CraftLevel:
    """CraftLevel.Of / Level, over the extracted recipes instead of the live ObjectDB. The mod's
    tables (CraftLevel.materials: material -> biome; BiomeLevels: biome -> item level) are read
    once into plain Python."""

    def __init__(self, recipes: list, craft_level, biome_levels):
        t = clr.GetClrType(craft_level)
        materials = t.GetField("materials", _ALL).GetValue(None)
        self.materials = {str(kv.Key): int(kv.Value) for kv in materials}
        self.by_prefix = t.GetMethod("ByPrefix", _ALL)
        # 5.1.2: materials with amount 0 (Valheim lists upgrade-only materials that way) don't count.
        # Read from the version's own code: does Level read Requirement.m_amount?
        self.skip_empty = _reads_field([m for m in t.GetMethods(_ALL) if m.Name == "Level"], "m_amount")
        biome = _asm("assembly_valheim").GetType("Heightmap+Biome")
        self.biome_level = {int(v): int(biome_levels.Of(Enum.ToObject(biome, int(v)))) for v in Enum.GetValues(biome)}
        self.recipe_of = {}
        for r in recipes:
            if r["enabled"]:
                self.recipe_of.setdefault(r["item"], r)

    def level(self, prefab: str, depth: int = 0) -> int:
        if not prefab:
            return 0
        if prefab in self.materials:
            return self.biome_level.get(self.materials[prefab], 0)
        found = self.by_prefix.Invoke(None, [prefab])  # Mold*/Upgrader* items
        if found is not None:
            return self.biome_level.get(int(found), 0)
        level = self.biome_level.get(1, 1)  # Meadows
        recipe = self.recipe_of.get(prefab)
        if recipe and depth < 5:
            for res in recipe["resources"]:
                if self.skip_empty and res.get("amount", 1) <= 0:
                    continue
                level = max(level, self.level(res["item"], depth + 1))
        return level

    def of(self, prefab: str) -> int:
        return max(1, self.level(prefab))
