"""What a boss essence makes of a weapon, shield or summoning staff (the mod's ItemAscension).

Ascending raises an item to a later biome: its stats become the median of Valheim's own craftable
weapons or shields of the same class in that biome (ItemAscension.Build/Compute), never lower than
its own. The game measures those references from ObjectDB at run time, which the harness has no
copy of, so this reads the same numbers from Valheim's item data and recipes:

- an item's class: its hands (1h, 2h, bow, shield), its weapon kind and, for shields, tower,
  buckler or round (ClassOf, ShieldKind); summoning staves are "summon";
- its biome: the highest item level among its recipe's materials (BaseBiome, BiomeLevels.BiomeAt);
- references: Valheim's craftable items with qualities to upgrade (Build); per biome and class
  the median of eight numbers (damage, durability, block, deflection and their per-quality
  growth), with "*/<hands>" and "*" for classes no item measures, and a curve between biomes
  (the median ratio of each class from one biome to the next) where a class has no cell.
"""

from statistics import median

from .pages import Ctx

_COMBAT = ("m_damage", "m_blunt", "m_slash", "m_pierce", "m_fire", "m_frost", "m_lightning", "m_poison", "m_spirit")
_NO_CLASS_SKILLS = {0, 12, 104, 106}  # none, pickaxes, farming, fishing
_NO_CLASS_KINDS = {"Pickaxes", "Bombs", "Traps", "Torch"}
_CURVE_ONLY = ("ElementalMagic/", "Scepters/")
_SUMMON = "summon"
# The eight numbers of a reference (Build: MDmg..MDeflL).
_DMG, _DMG_L, _DUR, _DUR_L, _BLOCK, _BLOCK_L, _DEFL, _DEFL_L = range(8)


def _combat(d: dict | None) -> float:
    return sum((d or {}).get(k, 0) for k in _COMBAT)


def _scale(d: dict, k: float) -> dict:
    return {key: v * k if key in _COMBAT else v for key, v in d.items()}


def _hands(s: dict) -> str | None:
    return {3: "1h", 4: "bow", 5: "shield", 14: "2h", 22: "2h"}.get(s.get("m_itemType"))


def _shield_kind(s: dict, prefab: str) -> str:
    bonus = s.get("m_timedBlockBonus") or 0
    if bonus <= 1.01:
        return "tower"
    return "buckler" if "buckler" in prefab.lower() or bonus >= 2.5 else "round"


def _summons(ctx: Ctx) -> set[str]:
    """Summoning staves (StarterStaves.CallOf; the vanilla ones too, with the default world setting)."""
    s = ctx.loc.difficulty.get("summons") or {}
    return {c["id"] for c in s.get("calls", []) + s.get("vanilla", [])}


def _class(ctx: Ctx, s: dict, prefab: str) -> str | None:
    hands = _hands(s)
    if hands is None:
        return None
    if hands == "shield":
        return f"shield:{_shield_kind(s, prefab)}"
    if prefab in _summons(ctx):
        return _SUMMON
    if s.get("m_skillType") in _NO_CLASS_SKILLS or _combat(s.get("m_damages")) < 5:
        return None
    tags = (ctx.loc.items.get(prefab) or {}).get("tags") or []
    kind = next((t.removeprefix("kind.") for t in tags if t.startswith("kind.")), None) or f"skill{s.get('m_skillType')}"
    return None if kind in _NO_CLASS_KINDS else f"{kind}/{hands}"


def _recipe(ctx: Ctx, prefab: str) -> dict | None:
    """ItemAscension.RecipeOf: the first enabled recipe of the item, else its first one."""
    mod = (ctx.loc.items.get(prefab) or {}).get("mod")
    if mod:
        return mod.get("recipe")
    recipes = [r for r in (ctx.loc.valheim or {}).get("recipes", []) if r["item"] == prefab]
    return next((r for r in recipes if r["enabled"]), recipes[0] if recipes else None)


def _biome_at(ctx: Ctx, level: int) -> str:
    """BiomeLevels.BiomeAt: the biome with the highest level not above it (Ocean left out)."""
    best = ("Meadows", -10**9)
    for b in ctx.loc.loot["biomes"]:
        if b["id"] != "Ocean" and best[1] < b["level"] <= level:
            best = (b["id"], b["level"])
    return best[0]


def base_biome(ctx: Ctx, prefab: str) -> int:
    """ItemAscension.BaseBiome, as an index into the stages."""
    stages = ctx.loc.difficulty["stages"]
    summons = ctx.loc.difficulty.get("summons") or {}
    for c in summons.get("calls", []) + summons.get("vanilla", []):
        if c["id"] == prefab:
            return min(max(c["stage"], 0), len(stages) - 1)
    levels = [(ctx.loc.items.get(r["item"]) or {}).get("craftLevel", 1)
              for r in (_recipe(ctx, prefab) or {}).get("resources", [])
              if r["amount"] > 0 and not r["item"].startswith("Upgrader")]
    level = max(levels) if levels else (ctx.loc.items.get(prefab) or {}).get("craftLevel", 1)
    biome = _biome_at(ctx, level)
    return stages.index(biome) if biome in stages else 0


_REFS: dict[str, dict] = {}


def _refs(ctx: Ctx) -> dict:
    """ItemAscension.Build: Valheim's craftable weapons and shields, their medians and curve
    (the same in every language: kept per game data version)."""
    if ctx.data.version not in _REFS:
        _REFS[ctx.data.version] = _build(ctx)
    return _REFS[ctx.data.version]


def _build(ctx: Ctx) -> dict:
    stages = ctx.loc.difficulty["stages"]
    rows = []
    for prefab, s in (ctx.loc.valheim or {}).get("items", {}).items():
        cls = _class(ctx, s, prefab)
        if cls is None or (s.get("m_maxQuality") or 1) <= 1:
            continue
        recipe = _recipe(ctx, prefab)
        if not recipe or not recipe.get("enabled") or not recipe.get("station"):
            continue
        shield = cls.startswith("shield:")
        dmg = _combat(s.get("m_damages"))
        if (s.get("m_blockPower") or 0) <= 0 if shield else dmg > 600:
            continue
        m = [0 if shield else dmg, 0 if shield else _combat(s.get("m_damagesPerLevel")),
             s.get("m_maxDurability") or 0, s.get("m_durabilityPerLevel") or 0,
             s.get("m_blockPower") or 0, s.get("m_blockPowerPerLevel") or 0,
             s.get("m_deflectionForce") or 0, s.get("m_deflectionForcePerLevel") or 0]
        rows.append({"prefab": prefab, "cls": cls, "hands": _hands(s), "bi": base_biome(ctx, prefab), "m": m})

    groups: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        keys = [r["cls"]]
        if r["cls"] != _SUMMON and not r["cls"].startswith(_CURVE_ONLY):
            keys += ["shield:*"] if r["hands"] == "shield" else [f"*/{r['hands']}", "*"]
        for key in keys:
            groups.setdefault((key, r["bi"]), []).append(r)
    cells: list[dict[str, list[float]]] = [{} for _ in stages]
    for (key, bi), rs in groups.items():
        cells[bi][key] = [median(r["m"][k] for r in rs) for k in range(8)]
    curve = [[1.0] * len(stages) for _ in range(8)]
    for k in range(8):
        for i in range(1, len(stages)):
            ratios = [v[k] / cells[i - 1][key][k] for key, v in cells[i].items()
                      if "*" not in key and key != _SUMMON and not key.startswith(_CURVE_ONLY)
                      and key in cells[i - 1] and cells[i - 1][key][k] > 0 and v[k] > 0]
            curve[k][i] = median(ratios) if ratios else 1.0
    return {"cells": cells, "curve": curve}


def _measured(refs: dict, cls: str) -> bool:
    return any(cls in c for c in refs["cells"])


def _effective(refs: dict, cls: str, hands: str) -> str:
    if _measured(refs, cls):
        return cls
    if hands == "shield":
        return "shield:*"
    return f"*/{hands}" if _measured(refs, f"*/{hands}") else "*"


def _value(refs: dict, cls: str, bi: int, k: int) -> float:
    cells, curve = refs["cells"], refs["curve"]
    if cls in cells[bi]:
        return cells[bi][cls][k]
    for i in range(bi - 1, -1, -1):
        if cls in cells[i]:
            v = cells[i][cls][k]
            for j in range(i + 1, bi + 1):
                v *= curve[k][j]
            return v
    for i in range(bi + 1, len(cells)):
        if cls in cells[i]:
            v = cells[i][cls][k]
            for j in range(i, bi, -1):
                v /= max(0.01, curve[k][j])
            return v
    return 0.0


def _curve_ratio(refs: dict, k: int, src: int, dst: int) -> float:
    r = 1.0
    for i in range(src + 1, dst + 1):
        r *= refs["curve"][k][i]
    return r


def ascended(ctx: Ctx, prefab: str, s: dict) -> list[dict]:
    """Each essence that can ascend this item (ItemAscension.CanApply) and what it becomes
    (Compute): {essence, biome, damages, damagesPerLevel, dur, durL, block, blockL, defl, deflL}."""
    targets = (ctx.loc.loot.get("ascension") or {})
    cls = _class(ctx, s, prefab)
    if not targets or cls is None or not ctx.loc.valheim:
        return []
    stages, refs, hands = ctx.loc.difficulty["stages"], _refs(ctx), _hands(s)
    eff, shield, src = _effective(refs, cls, hands), hands == "shield", base_biome(ctx, prefab)
    out = []
    for essence, t in targets.items():
        dst = stages.index(t["biome"]) if t["biome"] in stages else 0
        if src >= dst:
            continue
        d = dict(s.get("m_damages") or {})
        dl = dict(s.get("m_damagesPerLevel") or {})
        o = {"essence": essence, "biome": t["biome"], "level": t["level"],
             "dur": s.get("m_maxDurability") or 0, "durL": s.get("m_durabilityPerLevel") or 0,
             "block": s.get("m_blockPower") or 0, "blockL": s.get("m_blockPowerPerLevel") or 0,
             "defl": s.get("m_deflectionForce") or 0, "deflL": s.get("m_deflectionForcePerLevel") or 0}
        unmeasured = not _measured(refs, eff)
        if cls != _SUMMON:
            if not shield and (cls.startswith(_CURVE_ONLY) or unmeasured):
                if (r := _curve_ratio(refs, _DMG, src, dst)) > 1:
                    d, dl = _scale(d, r), _scale(dl, r)
            elif not shield:
                own, want = _combat(s.get("m_damages")), _value(refs, eff, dst, _DMG)
                if own > 0 and want > own:
                    d = _scale(s.get("m_damages") or {}, want / own)
                own_l, want_l = _combat(s.get("m_damagesPerLevel")), _value(refs, eff, dst, _DMG_L)
                if want_l > own_l:
                    if own_l > 0:
                        dl = _scale(s.get("m_damagesPerLevel") or {}, want_l / own_l)
                    elif _combat(d) > 0:
                        keep = s.get("m_damagesPerLevel") or {}
                        dl = _scale(d, want_l / _combat(d)) | {"m_chop": keep.get("m_chop", 0), "m_pickaxe": keep.get("m_pickaxe", 0)}
            elif unmeasured:
                if (r := _curve_ratio(refs, _BLOCK, src, dst)) > 1:
                    o["block"], o["blockL"] = o["block"] * r, o["blockL"] * r
                if (r := _curve_ratio(refs, _DEFL, src, dst)) > 1:
                    o["defl"], o["deflL"] = o["defl"] * r, o["deflL"] * r
            else:
                for key, k in (("block", _BLOCK), ("blockL", _BLOCK_L), ("defl", _DEFL), ("deflL", _DEFL_L)):
                    o[key] = max(o[key], _value(refs, eff, dst, k))
        if s.get("m_useDurability"):
            o["dur"] = max(o["dur"], _value(refs, eff, dst, _DUR))
            o["durL"] = max(o["durL"], _value(refs, eff, dst, _DUR_L))
        out.append(o | {"damages": d, "damagesPerLevel": dl})
    return sorted(out, key=lambda o: (stages.index(o["biome"]) if o["biome"] in stages else 0, o["essence"]))


def calculator_data(ctx: Ctx) -> dict:
    """Everything the ascension calculator needs (javascripts/ascension.js): the references and
    curve, the essences, and every item base that can ascend, with names in this language."""
    from .base_pages import bases

    targets = ctx.loc.loot.get("ascension") or {}
    if not targets or not ctx.loc.valheim:
        return {}
    loc, stages, refs = ctx.loc, ctx.loc.difficulty["stages"], _refs(ctx)
    dmg_keys = [k for k in _COMBAT if k != "m_damage"] + ["m_chop", "m_pickaxe"]
    items = []
    for prefab, b in sorted(bases(ctx).items(), key=lambda kv: kv[1]["name"]):
        s = b["shared"]
        cls = _class(ctx, s, prefab)
        if cls is None:
            continue
        items.append({"id": prefab, "name": b["name"], "cls": cls, "src": base_biome(ctx, prefab),
                      "maxQ": s.get("m_maxQuality") or 1, "useDur": bool(s.get("m_useDurability")),
                      "d": {k: v for k in dmg_keys if (v := (s.get("m_damages") or {}).get(k))},
                      "dl": {k: v for k in dmg_keys if (v := (s.get("m_damagesPerLevel") or {}).get(k))},
                      **{key: s.get(f) or 0 for key, f in (("dur", "m_maxDurability"), ("durL", "m_durabilityPerLevel"),
                                                          ("block", "m_blockPower"), ("blockL", "m_blockPowerPerLevel"),
                                                          ("defl", "m_deflectionForce"), ("deflL", "m_deflectionForcePerLevel"))}})
    kinds = sorted({i["cls"].split("/")[0] for i in items if "/" in i["cls"]} | {k.split("/")[0] for c in refs["cells"] for k in c
                                                                               if "/" in k and not k.startswith("*")})

    def kind_name(k: str) -> str:
        name = loc.ui(f"tag.kind.{k}")
        return name.capitalize() if name != f"tag.kind.{k}" else k

    ui = loc.ui
    return {
        "stages": [loc.vkey(f"biome_{st.lower()}", st) for st in stages],
        "targets": [{"id": e, "name": loc.loot["items"].get(e, {}).get("name", e), "stage": stages.index(t["biome"]), "level": t["level"]}
                    for e, t in sorted(targets.items(), key=lambda kv: (kv[1]["level"], kv[0])) if t["biome"] in stages],
        "cells": refs["cells"], "curve": refs["curve"],
        "kinds": [[k, kind_name(k)] for k in kinds],
        "damage": [[k, loc.vkey(f"inventory_{k.removeprefix('m_')}", k)] for k in dmg_keys],
        "items": items,
        "ui": {k: ui(f"tools.ascension.{k}") for k in (
            "base", "custom", "kind", "hands", "h1", "h2", "bow", "shield", "summon", "round", "tower", "buckler", "biome", "biome_col",
            "quality", "at_q1", "shield_kind", "damage_col", "per_quality", "durability", "block", "parry", "essence", "result", "none", "not_eligible",
            "already", "uses_durability", "curve_note", "biome_note", "step_note")},
    }
