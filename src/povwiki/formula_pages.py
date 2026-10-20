"""Mechanics: the game's formulas (formulas/registry.toml), on three pages.

Each formula's words are in i18n ([formula] strings), its numbers from the registry ("values":
setting defaults, numbers written inline in the code) or read live from the game data (biome
tables, catalog, tunables). A formula whose code changed since it was checked is not shown: its
section says it is being re-checked (povwiki.formulas).
"""

from functools import cache

from .markup import glossary_path, rel
from .pages import Ctx, _footer, _table

CREATURES_PAGE = "mechanics/creatures.md"
LOOT_PAGE = "mechanics/loot.md"
COMBAT_PAGE = "mechanics/combat.md"


@cache
def _status(version: str) -> dict:
    from .formulas import check

    return check(version)


@cache
def _values() -> dict[str, dict]:
    from .formulas import load

    return {f["id"]: f.get("values", {}) for f in load()["formula"]}


def shown(ctx: Ctx, fid: str) -> bool:
    s = _status(ctx.data.version).get(fid)
    return bool(s and s.ok)


def _n(v: float, digits: int = 2) -> str:
    return f"{round(v, digits):g}"


def _pct(v: float) -> str:
    return f"{round(v * 100, 2):g}%"


def _formula(text: str) -> list[str]:
    return [f'<div class="pov-formula">{text}</div>', ""]


def _term(ctx: Ctx, key: str, page: str) -> str:
    """A link to a glossary term of the mod's wiki, by its title there."""
    from .markup import plain

    term = ctx.loc.wiki.get(key)
    return f"[{plain(term['title'])}]({rel(glossary_path(key), page)})" if term else ""


def _section(ctx: Ctx, fid: str, page: str, body) -> list[str]:
    """A formula's section, or a note that it is being re-checked."""
    ui = ctx.loc.ui
    md = [f"## {ui(f'formula.{fid}.title')} {{ #{fid} }}", ""]
    if not shown(ctx, fid):
        return md + [f'!!! warning "{ui("formula.rechecking_title")}"',
                     f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
    return md + body(_values().get(fid, {})) + [""]


def _biomes(ctx: Ctx) -> list[tuple[str, int]]:
    """(name, level) of each progression biome (Ocean shares Mistlands' level; left out)."""
    return [(ctx.loc.vkey(f"biome_{b['id'].lower()}", b["id"]), b["level"])
            for b in ctx.loc.loot["biomes"] if b["id"] != "Ocean"]


def _intro(ctx: Ctx, key: str) -> list[str]:
    return [ctx.loc.ui(f"formula.{key}_intro"), "", ctx.loc.ui("formula.defaults_note"), ""]


# ---- Creature scaling ---------------------------------------------------------------------------


def page_creature_formulas(ctx: Ctx) -> str:
    ui, page, d = ctx.loc.ui, CREATURES_PAGE, ctx.loc.difficulty
    from .monster_pages import BOSSES_PAGE, MODS_PAGE

    md = [f"# {ui('formula.creatures')}", ""] + _intro(ctx, "creatures")
    biomes = _biomes(ctx)

    def level(v):
        rows = [[name, str(lvl)] for name, lvl in biomes]
        return [ui("formula.creature-level.text"), ""] + _table([ui("bosses.biome"), ui("formula.level")], rows)

    def strength(v):
        names = [ctx.loc.vkey(f"biome_{s.lower()}", s) for s in d["stages"]]
        rows = [[n, f"×{_n(h, 3)}", f"×{_n(dm, 3)}", f"×{_n(bh, 3)}", f"×{_n(bd, 3)}"]
                for n, h, dm, bh, bd in zip(names, d["health"], d["damage"], d["bossHealth"], d["bossDamage"])]
        species = ", ".join(f"{ctx.loc.creature(s)} ×{_n(f)}" for s, f in d["species"].items() if s != "Draugr_Ranged")
        p = d["presets"]
        preset_rows = [[ui(f"formula.preset.{k}"), _n(v_["Health"]), _n(v_["Damage"]), f"{_n(v_['Star'])}%", _n(v_["MaxStars"])]
                       for k, v_ in p.items()]
        return ([ui("formula.creature-strength.text"), ""]
                + _formula(ui("formula.creature-strength.health")) + _formula(ui("formula.creature-strength.damage"))
                + [ui("formula.creature-strength.terms", tamed=_pct(v["tamed"]),
                      power=f"#monster-power", stars="#stars"), ""]
                + [f"### {ui('formula.stage_table')}", "", ui("formula.stage_note"), ""]
                + _table([ui("bosses.biome"), ui("formula.health"), ui("formula.damage"), ui("formula.boss_health"),
                          ui("formula.boss_damage")], rows)
                + [ui("formula.creature-strength.species", species=species), ""]
                + [f"### {ui('formula.presets')}", "", ui("formula.presets_note"), ""]
                + _formula(ui("formula.creature-strength.soften"))
                + _table([ui("formula.preset_col"), ui("formula.health_scale"), ui("formula.damage_scale"),
                          ui("formula.star_chance"), ui("formula.max_stars")], preset_rows))

    def boss_step(v):
        names = [ctx.loc.vkey(f"biome_{s.lower()}", s) for s in d["stages"]]
        near, far = d["bossStep"]
        rows = [[n, f"{_n(a, 0)} m", f"{_n(b, 0)} m"] for n, a, b in list(zip(names, d["ringNear"], d["ringFar"]))[:-1]]
        return ([ui("formula.boss-step.text", near=_pct(near), far=_pct(far)), ""]
                + _formula(ui("formula.boss-step.formula", near=_n(near), far=_n(far)))
                + _table([ui("bosses.biome"), ui("formula.ring_near"), ui("formula.ring_far")], rows)
                + [ui("formula.boss-step.species"), ""])

    def stars(v):
        p = v["chance"]
        odds = [["0", _pct(1 - p)], ["1", _pct(p * (1 - p))], ["2+", _pct(p * p)]]
        return ([ui("formula.stars.text", rarity=rel(MODS_PAGE, page))]
                + [""] + _formula(ui("formula.stars.health", h=_n(v["health"]))) + _formula(ui("formula.stars.damage", d=_n(v["damage"])))
                + [ui("formula.stars.chance", chance=_pct(p), above=_pct(v["above_two"]), mods=v["mods_per_star"],
                      home=v["home_max_level"] - 1), ""]
                + _table([ui("monsters.stars"), ui("formula.odds")], odds))

    def boss_stars(v):
        return ([ui("formula.boss-stars.text", chance=_pct(v["chance"]), two=_pct(v["two"]), bosses=rel(BOSSES_PAGE, page)), ""]
                + _formula(ui("formula.boss-stars.health", h=_n(v["health"]))) + _formula(ui("formula.boss-stars.damage", d=_n(v["damage"])))
                + [ui("formula.boss-stars.notes", mods=v["mods_per_star"]), ""])

    def power(v):
        mp = d["monsterPower"]
        step, cap = mp["step"] + mp["biome-step"], mp["max"]
        return ([ui("formula.monster-power.text"), ""]
                + _formula(ui("formula.monster-power.formula", step=_n(step), max=_n(cap)))
                + [ui("formula.monster-power.notes", n=round((cap - 1) / step) if step else 0, loot=rel(LOOT_PAGE, page) + "#loot"), ""])

    for fid, body in (("creature-level", level), ("creature-strength", strength), ("boss-step", boss_step),
                      ("stars", stars), ("boss-stars", boss_stars), ("monster-power", power)):
        md += _section(ctx, fid, page, body)
    return "\n".join(md + _footer(ctx))


# ---- Loot and experience ------------------------------------------------------------------------


def page_loot_formulas(ctx: Ctx) -> str:
    ui, page, loot = ctx.loc.ui, LOOT_PAGE, ctx.data.loot
    md = [f"# {ui('formula.loot_page')}", ""] + _intro(ctx, "loot")
    links = {"quantity": _term(ctx, "item-quantity", page), "rarity": _term(ctx, "item-rarity", page)}

    def drops(v):
        stars = loot.get("stars", {})
        sources = [[ui(f"gear.source.{s['id']}") if ui(f"gear.source.{s['id']}") != f"gear.source.{s['id']}" else s["id"],
                    _n(s["lambda"]), _pct(s.get("jewel", 0) / (s.get("gear", 0) + s.get("currency", 0) + s.get("jewel", 0)))]
                   for s in loot.get("sources", [])]
        levels = [[str(r["level"]), _n(r["common"]), _n(r["magic"]), _n(r["rare"])] for r in loot.get("rarityByLevel", [])]
        return ([ui("formula.loot.text", **links), ""]
                + _formula(ui("formula.loot.quantity", star=_n(stars.get("quantityPerStar", 0)), mod=_n(v["per_modifier"])))
                + _formula(ui("formula.loot.rarity", star=_n(stars.get("rarityPerStar", 0))))
                + [ui("formula.loot.notes"), ""]
                + [f"### {ui('formula.loot.sources')}", "", ui("formula.loot.sources_note"), ""]
                + _table([ui("gear.source_label"), ui("formula.loot.lambda"), ui("formula.loot.jewel")], sources)
                + [f"### {ui('formula.loot.by_level')}", "", ui("formula.loot.by_level_note"), ""]
                + _formula(ui("formula.loot.curve"))
                + _table([ui("formula.level"), ui("formula.loot.common"), ui("formula.loot.magic"), ui("formula.loot.rare")], levels)
                + [ui("formula.loot.unique", chance=_pct(loot.get("uniqueChance", 0)), level=loot.get("rareGuaranteeMinLevel", 0)), ""])

    def vanilla(v):
        return [ui("formula.vanilla-drops.text"), ""] + _formula(ui("formula.vanilla-drops.formula", s=_n(v["per_star"]), cap=v["cap"]))

    def xp(v):
        return ([ui("formula.experience.text"), ""]
                + _formula(ui("formula.experience.formula", h=_n(v["per_health"]), s=_n(v["per_star"]), m=_n(_values()["loot"].get("per_modifier", 0.5))))
                + [ui("formula.experience.notes", radius=_n(v["radius"]), boss=_n(v["boss_radius"]), night=_pct(v["night"]),
                      event=_pct(v["runic_event"])), ""])

    for fid, body in (("loot", drops), ("vanilla-drops", vanilla), ("experience", xp)):
        md += _section(ctx, fid, page, body)
    return "\n".join(md + _footer(ctx))


# ---- Combat and building ------------------------------------------------------------------------


def page_combat_formulas(ctx: Ctx) -> str:
    ui, page, d = ctx.loc.ui, COMBAT_PAGE, ctx.loc.difficulty
    t = d.get("tunables", {})
    md = [f"# {ui('formula.combat')}", ""] + _intro(ctx, "combat")

    def crit_mult(v):
        return [ui("formula.crit-multiplier.text", term=_term(ctx, "crit", page)), ""] + _formula(
            ui("formula.crit-multiplier.formula", base=_n(v["base"]))) + [ui("formula.crit-multiplier.notes"), ""]

    def crit_chance(v):
        return ([ui("formula.crit-chance.text"), ""]
                + _formula(ui("formula.crit-chance.formula"))
                + [ui("formula.crit-chance.bases", knives=_pct(v["knives"]), polearms=_pct(v["polearms"]),
                      other=_pct(v["other"]), spells=_pct(v["spells"]), ceiling=_pct(v["ceiling"])), ""])

    def evasion(v):
        def acc(level: int, stars: int = 0) -> float:
            base = t["evasion.accuracy.base"] + t["evasion.accuracy.per-level"] * level ** max(0.1, t["evasion.accuracy.growth"])
            return max(1, base) * (1 + max(0, t["evasion.accuracy.per-star"]) * stars)

        def chance(rating: float, a: float) -> float:
            return max(0.0, min(min(0.999999, t["evasion.cap"]), 1 - max(1, t["evasion.hit-factor"]) * a / (a + rating)))

        ratings = (50, 100, 200, 400)
        rows = [[name, _n(acc(lvl), 0), *(_pct(chance(r, acc(lvl))) for r in ratings)] for name, lvl in _biomes(ctx)]
        return ([ui("formula.evasion.text", evade=_term(ctx, "evade", page), accuracy=_term(ctx, "enemy-accuracy", page)), ""]
                + _formula(ui("formula.evasion.accuracy", base=_n(t["evasion.accuracy.base"]), per=_n(t["evasion.accuracy.per-level"]),
                              star=_pct(t["evasion.accuracy.per-star"])))
                + _formula(ui("formula.evasion.chance", h=_n(t["evasion.hit-factor"]), cap=_pct(t["evasion.cap"])))
                + [ui("formula.evasion.notes"), ""]
                + _table([ui("bosses.biome"), ui("formula.evasion.acc_col"), *(ui("formula.evasion.rating_col", n=r) for r in ratings)], rows))

    def resist(v):
        return ([ui("formula.resistances.text", term=_term(ctx, "resist", page)), ""]
                + _formula(ui("formula.resistances.formula", cap=_pct(v["cap"]), hard=_pct(v["hard_cap"])))
                + [ui("formula.resistances.notes"), ""])

    def pen(v):
        names = [ctx.loc.vkey(f"biome_{s.lower()}", s) for s in d["stages"]]
        rows = [[n, _n(a), _pct(r)] for n, a, r in zip(names, d["armorPen"], d["resistPen"])]
        mods = {m["id"]: m for m in ctx.loc.monsters.get("mods", [])}
        piercing = mods.get("piercing", {}).get("name", "Piercing")
        from .monster_pages import mod_anchor

        return ([ui("formula.enemy-penetration.text", armour=_term(ctx, "armour-penetration", page),
                    resist=_term(ctx, "resistance-penetration", page), effect=_pct(t.get("armor.effect", 1))), ""]
                + _table([ui("bosses.biome"), ui("formula.pen.armour"), ui("formula.pen.resist")], rows)
                + [ui("formula.enemy-penetration.notes", piercing=f"[{piercing}]({rel(mod_anchor('piercing'), page)})"), ""])

    def build(v):
        from .building_pages import BUILDINGS_PAGE

        return ([ui("formula.build-cost.text", cap=_pct(v["cap"]), buildings=rel(BUILDINGS_PAGE, page)), ""]
                + _formula(ui("formula.build-cost.formula", cap=_pct(v["cap"])))
                + [ui("formula.build-cost.notes", refund=_term(ctx, "refund", page)), ""])

    for fid, body in (("crit-multiplier", crit_mult), ("crit-chance", crit_chance), ("evasion", evasion),
                      ("resistances", resist), ("enemy-penetration", pen), ("build-cost", build)):
        md += _section(ctx, fid, page, body)
    return "\n".join(md + _footer(ctx))


def page_formulas(ctx: Ctx) -> dict[str, str]:
    if not ctx.loc.difficulty:
        return {}
    return {CREATURES_PAGE: page_creature_formulas(ctx), LOOT_PAGE: page_loot_formulas(ctx),
            COMBAT_PAGE: page_combat_formulas(ctx)}


FORMULA_PAGES = {  # formula id -> its page, for links from other pages
    **{f: CREATURES_PAGE for f in ("creature-level", "creature-strength", "boss-step", "stars", "boss-stars", "monster-power")},
    **{f: LOOT_PAGE for f in ("loot", "vanilla-drops", "experience")},
    **{f: COMBAT_PAGE for f in ("crit-multiplier", "crit-chance", "evasion", "resistances", "enemy-penetration", "build-cost")},
}
