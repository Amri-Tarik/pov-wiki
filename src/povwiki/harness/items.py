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
            }
        except Exception as ex:  # one bad item must not lose the rest
            errors.append({"item": prefab, "error": str(ex).split("\n")[0]})
    return out


class _CraftLevel:
    """CraftLevel.Of / Level, over the extracted recipes instead of the live ObjectDB. The mod's
    tables (CraftLevel.materials: material -> biome; BiomeLevels: biome -> item level) are read
    once into plain Python."""

    def __init__(self, recipes: list, craft_level, biome_levels):
        t = clr.GetClrType(craft_level)
        materials = t.GetField("materials", _ALL).GetValue(None)
        self.materials = {str(kv.Key): int(kv.Value) for kv in materials}
        self.by_prefix = t.GetMethod("ByPrefix", _ALL)
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
                level = max(level, self.level(res["item"], depth + 1))
        return level

    def of(self, prefab: str) -> int:
        return max(1, self.level(prefab))
