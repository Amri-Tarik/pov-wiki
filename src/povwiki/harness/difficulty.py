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


def _governing() -> dict[str, list[str]]:
    """Each weapon skill's governing attributes (StatText.AttrsFor), by Valheim skill name; the mod
    asks its own code. Scepters (Strength and Intelligence) are set by weapon, not by skill."""
    from System import Array, Enum, Object

    # AttrsFor(SkillType, out Stat?, out Stat?): the overload without the item.
    method = next(m for m in _type("StatText").GetMethods(_ANY)
                  if m.Name == "AttrsFor" and len(m.GetParameters()) == 3 and m.GetParameters()[0].ParameterType.IsEnum)
    skill = method.GetParameters()[0].ParameterType
    out = {}
    for name in Enum.GetNames(skill):
        args = Array[Object]([Enum.Parse(skill, name), None, None])  # out values come back in a .NET array
        method.Invoke(None, args)
        attrs = [str(args[i]) for i in (1, 2) if args[i] is not None]
        if attrs:
            out[str(name)] = attrs
    return out


def _caps(*stats: str) -> dict[str, float]:
    """The highest (or lowest) value these stats can reach (StatText.C, used by StatText.Clamp)."""
    caps = _type("StatText").GetField("C", _ANY).GetValue(None)
    return {str(kv.Key): float(kv.Value) for kv in caps if str(kv.Key) in stats}


def _summons() -> dict:
    """The summoning staves (StarterStaves.Calls) and Valheim's own (VanillaCalls): thralls, lives,
    biome stages; the eitr each summon holds (Tunables summon.reserve.*)."""
    from PassiveTree import L, Tunables

    staves = _type("StarterStaves")
    if staves.GetField("Calls", _ANY) is None:  # before 5.2.0
        return {}
    calls = [{"id": str(c.Id), "thrall": str(c.Thrall), "name": L.Id(f"creature.{c.Thrall}.name", c.ThrallName),
              "health": float(c.Health), "blunt": float(c.Blunt), "slash": float(c.Slash), "life": float(c.Life),
              "stamina": float(c.Stamina), "bench": int(c.Bench), "stage": int(c.Stage)}
             for c in staves.GetField("Calls", _ANY).GetValue(None)]
    vanilla = [{"id": str(c.Id), "life": float(c.Life), "stage": int(c.Stage)}
               for c in staves.GetField("VanillaCalls", _ANY).GetValue(None)]
    return {"calls": calls, "vanilla": vanilla,
            "reserve": {c["id"]: float(Tunables.Of(f"summon.reserve.{c['id']}")) for c in calls + vanilla}}


def _boss_health() -> dict:
    """Bosses with their own health factor (EnemyDifficulty.bossHealth, 5.3.1)."""
    field = _type("EnemyDifficulty").GetField("bossHealth", _ANY)
    if field is None:
        return {}
    return {str(kv.Key): float(kv.Value) for kv in field.GetValue(None)}


def _loot_scale(presets: dict) -> dict:
    """What each difficulty preset does to loot (LootDifficulty, 5.3.1): the share of the per-star
    loot bonuses creatures keep (StarScale) and the factor on creatures' and elites' loot quantity
    (Factor), so that loot per area stays at the Normal preset's. Computed with the mod's own
    MeanStars and PerArea from each preset's star chance, maximum stars and density, the other
    settings at their defaults (each star past two 0.5, one modifier per star, always, worth 0.5)."""
    try:
        from PassiveTree.Loot import LootDifficulty
    except ImportError:
        return {}
    out = {}
    normal_mean = float(LootDifficulty.MeanStars(0.18, 0.5, 5))
    normal_area = float(LootDifficulty.PerArea(1.2, 0.18, 0.5, 5, 1.0, 1.0, 0.5, 1.0))
    for name, p in presets.items():
        step, top = p["Star"] / 100, int(p["MaxStars"])
        mean = float(LootDifficulty.MeanStars(step, 0.5, top))
        scale = normal_mean / mean if mean > normal_mean and mean > 0 else 1.0
        area = float(LootDifficulty.PerArea(p["Density"], step, 0.5, top, 1.0, 1.0, 0.5, scale))
        out[name] = {"star": scale, "quantity": normal_area / area if area > normal_area and area > 0 else 1.0}
    return out


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
            "bossHealthFactor": _boss_health(),
            "lootScale": _loot_scale(presets),
            # Creatures whose health the mod leaves alone (EnemyDifficulty.fixedHealth, 5.1.1: Kall's 2nd phase).
            "fixedHealth": sorted(str(x) for x in (enemy.GetField("fixedHealth", _ANY).GetValue(None) or [])
                                  ) if enemy.GetField("fixedHealth", _ANY) else [],
            "monsterPower": {k: float(Tunables.Of(f"monster-power.{k}")) for k in ("step", "biome-step", "max")},
            # Evasion and armour knobs (Evasion.AccuracyAt/Chance, ArmorEffect).
            "tunables": {k: float(Tunables.Of(k)) for k in (
                "evasion.accuracy.base", "evasion.accuracy.per-level", "evasion.accuracy.growth",
                "evasion.accuracy.per-star", "evasion.full-ratio", "evasion.cap", "evasion.decay",
                "evasion.decay-reset", "evasion.decay-reset-boss", "evasion.stamina-cost", "armor.effect",
                # The evasion cost by the damage a hit would deal (Evasion.CostShare, 5.3.4).
                "evasion.stamina-cost-min", "evasion.cost-low-hit", "evasion.cost-full-hit",
                # Ranged falloff, ground effects, infusion, unique jewel dust, permadeath (5.3.0).
                "ranged.falloff.start", "ranged.falloff.end", "ranged.falloff.floor",
                "groundfield.base-limit", "groundfield.radius", "groundfield.duration", "groundfield.damage-share",
                "groundfield.buildup-share", "groundfield.tick", "groundfield.sliding-friction", "groundfield.sliding-steering",
                "infusion.base-limit", "infusion.duration", "infusion.absorption-area", "infusion.area-per-unit",
                "infusion.damage-per-unit", "disenchant.unique-jewel-divine", "disenchant.unique-jewel-azurite",
                "disenchant.unique-jewel-level-step", "disenchant.unique-mult", "disenchant.unique-level-step",
                "permadeath.oneshot-share", "permadeath.oneshot-cooldown",
                "permadeath.mercy-hours",
                # Damaging ailments and shock (DamagingAilments, ShockAilment; 5.3.0).
                "ailment.burning.dps-share", "ailment.burning.duration", "ailment.poison.dps-share", "ailment.poison.duration",
                "ailment.poison.base-limit", "ailment.bleeding.dps-share", "ailment.bleeding.duration", "shock.duration",
                "shock.coefficient", "shock.exponent", "shock.minimum", "shock.maximum",
                # Additional and phantom strikes (Strikes, Phantoms).
                "strike.interval", "strike.focus-damage", "strike.reach", "strike.radius",
                "phantom.damage", "phantom.radius", "phantom.interval", "phantom.delay", "attrs.might-covers",
                "ailment.threshold", "shield.delay-cap",  # the ailment gauge (AilmentDamage.Grip)
                # Charged attacks, slams, thorns, impale, endurance.
                "charge.cooldown", "charge.source-cooldown", "charge.source-cooldown.crit", "splash.radius", "movement.charge-distance",
                "slam.ground-radius", "slam.cutting-to-blunt", "aftershock.delay", "throw.slam-damage", "crossbow.fire-interval-share", "thorns.contact-interval",
                "bow.falloff.start", "bow.falloff.end", "thorns.increased.base", "thorns.block.share",
                "thorns.riposte.share", "impale.stack", "impale.limit", "impale.window", "endurance.base", "endurance.cap",
                "rage.more-per-point", "stagger.rune-shield", "phantom.stagger", "xp.ally-kill",
                "minion.instability-share", "minion.instability-radius", "loot.white-jewel-weight",
                "spore.limit", "crystal.limit", "shard.limit", "chain.targets", "minion.guard-seconds", "minion.guard-share",
                *(f"summon.power-{k}.{staff}" for k in ("health", "damage")
                  for staff in ("StaffSkeleton", "StaffGreenRoots", "StaffRedTroll", "StaffSpiritCaller")))},
            # Every tunable with its title and default, for the patch pages' changed values.
            "knobs": {str(k.Id): {"title": str(k.Title or k.Id), "value": float(k.Base), "pct": bool(k.Pct),
                                  "unit": str(k.Unit or "")} for k in Tunables.All},
            "governing": _governing(),
            "summons": _summons(),
            "caps": _caps("StaggerResistPct", "GlancingChance"),
        }
    except Exception as ex:
        errors.append({"difficulty": str(ex).split("\n")[0]})
        return {}
