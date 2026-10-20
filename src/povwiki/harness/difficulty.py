"""Enemy difficulty tables, for the formulas page (the formulas themselves are written down in
formulas/registry.toml and checked against the code; these are their numbers, read live).

- Biome stage factors (EnemyDifficulty.Defaults): health, damage, boss health and damage, armour
  and resistance penetration, Meadows to Deep North.
- Species overrides (EnemyDifficulty.CreatureHealthFactor): health factors that replace the stage.
- After a biome's boss falls (EnemyDifficulty.ringNear/ringFar; Tunables difficulty.boss-step-*):
  how far toward the next stage its creatures move, by distance from the world centre.
- Presets (DifficultyPreset: vanilla, easy, normal, hard, merciless).
- Monster Power (Tunables monster-power.*); evasion and armour knobs (evasion.*, armor.effect).
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic
_STAGES = ["Meadows", "BlackForest", "Swamp", "Mountain", "Plains", "Mistlands", "AshLands", "DeepNorth"]


def _type(name: str):
    from System import AppDomain

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    return asm.GetType(f"PassiveTree.{name}")


def _floats(values) -> list[float]:
    return [round(float(v), 4) for v in values]


def render_difficulty(errors: list) -> dict:
    from PassiveTree import EnemyDifficulty, Tunables

    try:
        d = EnemyDifficulty.Defaults()
        enemy = _type("EnemyDifficulty")
        preset = _type("DifficultyPreset")
        presets = {}
        for name in ("vanilla", "easy", "normal", "hard", "merciless"):
            deal = preset.GetField(name, _ANY).GetValue(None)
            t = deal.GetType()
            presets[name] = {f: float(t.GetField(f).GetValue(deal))
                             for f in ("Ladder", "Health", "Damage", "Density", "Penetration", "Star", "MaxStars")}
        return {
            "stages": _STAGES,
            "health": _floats(d.Health), "damage": _floats(d.Damage),
            "bossHealth": _floats(d.BossHealth), "bossDamage": _floats(d.BossDamage),
            "armorPen": _floats(d.ArmorPen), "resistPen": _floats(d.ResistPen),
            "species": {s: float(EnemyDifficulty.CreatureHealthFactor(s, -1.0))
                        for s in ("Wolf", "Draugr", "Draugr_Ranged")
                        if float(EnemyDifficulty.CreatureHealthFactor(s, -1.0)) >= 0},
            "ringNear": _floats(enemy.GetField("ringNear", _ANY).GetValue(None)),
            "ringFar": _floats(enemy.GetField("ringFar", _ANY).GetValue(None)),
            "bossStep": [float(Tunables.Of("difficulty.boss-step-near")), float(Tunables.Of("difficulty.boss-step-far"))],
            "presets": presets,
            # Creatures whose health the mod leaves alone (EnemyDifficulty.fixedHealth, 5.1.1: Kall's 2nd phase).
            "fixedHealth": sorted(str(x) for x in (enemy.GetField("fixedHealth", _ANY).GetValue(None) or [])
                                  ) if enemy.GetField("fixedHealth", _ANY) else [],
            "monsterPower": {k: float(Tunables.Of(f"monster-power.{k}")) for k in ("step", "biome-step", "max")},
            # Evasion and armour knobs (Evasion.AccuracyAt/Chance, ArmorEffect).
            "tunables": {k: float(Tunables.Of(k)) for k in (
                "evasion.accuracy.base", "evasion.accuracy.per-level", "evasion.accuracy.growth",
                "evasion.accuracy.per-star", "evasion.hit-factor", "evasion.cap", "armor.effect")},
        }
    except Exception as ex:
        errors.append({"difficulty": str(ex).split("\n")[0]})
        return {}
