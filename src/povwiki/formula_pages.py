"""Mechanics: the game's formulas (formulas/registry.toml).

Each formula is one block (`_BODIES`), shown on its Mechanics page and at the top of the
glossary page of every keyword it explains (`TERM_FORMULAS`: crit chance and crit damage on
Critical hit...). Its words are in i18n ([formula] strings), its numbers from the registry
("values": setting defaults, numbers written inline in the code) or read live from the game data
(biome tables, catalog, tunables). A formula whose code changed since it was checked is not
shown: its block says it is being re-checked (povwiki.formulas).
"""

from functools import cache

from .markup import glossary_path, plain, rel
from .pages import Ctx, _footer, _table

CREATURES_PAGE = "mechanics/creatures.md"
LOOT_PAGE = "mechanics/loot.md"
COMBAT_PAGE = "mechanics/combat.md"
EXPERIENCE_PAGE = "mechanics/experience.md"


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


def _term(ctx: Ctx, key: str, page: str, start: bool = False) -> str:
    """A glossary term of the mod's wiki by its title there, linked (not on its own page);
    lower-cased unless it starts the sentence."""
    term = ctx.loc.wiki.get(key)
    if not term:
        return ""
    title = plain(term["title"])
    title = title if start else title[:1].lower() + title[1:]
    return title if glossary_path(key) == page else f"[{title}]({rel(glossary_path(key), page)})"


def _biomes(ctx: Ctx) -> list[tuple[str, int]]:
    """(name, level) of each progression biome (Ocean shares Mistlands' level; left out)."""
    return [(ctx.loc.vkey(f"biome_{b['id'].lower()}", b["id"]), b["level"])
            for b in ctx.loc.loot["biomes"] if b["id"] != "Ocean"]


def _stages(ctx: Ctx) -> list[str]:
    return [ctx.loc.vkey(f"biome_{s.lower()}", s) for s in ctx.loc.difficulty["stages"]]


def _anchor(fid: str, page: str) -> str:
    """Where a formula's section is, from a page."""
    return f"{rel(FORMULA_PAGES[fid], page)}#{fid}"


# ---- Formulas: each one's block, for any page ---------------------------------------------------


def _area_biomes(ctx: Ctx) -> list[dict]:
    """Progression biomes with their level and band (Ocean shares Mistlands'; left out)."""
    return [b for b in ctx.loc.loot["biomes"] if b["id"] != "Ocean"]


def _biome(ctx: Ctx, b: dict) -> str:
    return ctx.loc.vkey(f"biome_{b['id'].lower()}", b["id"])


def _range_start(b: dict) -> int:
    """Where full experience starts in a biome: its recommended player level (5.1.1), else its level."""
    return b.get("recommended", b["level"])


def _range_end(b: dict) -> int:
    """The last player level with full experience in a biome (before grace)."""
    return _range_start(b) + b.get("recommendedBand", b.get("band", 0))


def _level(ctx, page, v):
    ui = ctx.loc.ui
    rows = [[_biome(ctx, b), str(b["level"]), str(_range_end(b))] for b in _area_biomes(ctx)]
    return ([ui("formula.creature-level.text", falloff=_anchor("experience-falloff", page)), ""]
            + _table([ui("bosses.biome"), ui("formula.level"), ui("formula.creature-level.full_col")], rows))


def _item_level(ctx, page, v):
    from .base_pages import BASES_PAGE
    from .gear_pages import UNIQUES_PAGE

    ui = ctx.loc.ui
    return ([ui("formula.item-level.text", areas=_anchor("creature-level", page)), "",
             ui("formula.item-level.crafted", bases=rel(BASES_PAGE, page)), ""]
            + _idols(ctx)
            + [ui("formula.item-level.gates", mods=rel("items/mods.md", page), uniques=rel(UNIQUES_PAGE, page)), ""])


def _idols(ctx) -> list[str]:
    """The level each upgrade idol counts as (CraftLevel.ByPrefix: Upgrader<tier>Weapon/Armor, by
    the tier's biome since 5.1.2), from the levels the game gives them."""
    from .base_pages import _item_name

    items, by_level = ctx.loc.items, {b["level"]: b for b in _area_biomes(ctx)}
    rows = []
    for tier in range(10):
        found = [p for p in (f"Upgrader{tier}Weapon", f"Upgrader{tier}Armor") if p in items]
        if found:
            level = items[found[0]]["craftLevel"]
            biome = _biome(ctx, by_level[level]) if level in by_level else "—"
            rows.append([" / ".join(_item_name(ctx, p) for p in found), biome, str(level)])
    if not rows:
        return []
    return [ctx.loc.ui("formula.item-level.idols"), ""] + _table(
        [ctx.loc.ui("formula.item-level.idol_col"), ctx.loc.ui("bosses.biome"), ctx.loc.ui("formula.level")], rows)


def _falloff(ctx, page, v):
    ui = ctx.loc.ui
    grace, gap, floor = v["grace"], v["gap"], v["floor"]

    def share(over: int) -> float:  # BiomeLevels.ExperienceShare, levels past the end of the range
        d = over - grace
        return 1.0 if d <= 0 else max(floor, floor ** (d / max(1, gap - grace)))

    steps = (1, 2, 3, 5, 8, gap)
    rows = [[_biome(ctx, b), f"{_range_start(b)}–{_range_end(b) + grace}",
             str(_range_end(b) + grace + gap)] for b in _area_biomes(ctx)]
    return ([ui("formula.experience-falloff.text"), ""]
            + _formula(ui("formula.experience-falloff.formula", floor=_n(floor), gap=gap))
            + [ui("formula.experience-falloff.notes", floor=_pct(floor), gap=gap), ""]
            + _table([ui("formula.experience-falloff.over_col"), *(f"+{n}" for n in steps)],
                     [[ui("formula.experience-falloff.share_col"), *(_pct(share(n)) for n in steps)]])
            + _table([ui("bosses.biome"), ui("formula.experience-falloff.full_col"), ui("formula.experience-falloff.floor_col", floor=_pct(floor))], rows))


def _player_levels(ctx, page, v):
    import struct

    ui = ctx.loc.ui

    def f32(x: float) -> float:  # the game computes in single precision
        return struct.unpack("f", struct.pack("f", x))[0]

    def to_next(level: int) -> int:  # Plugin.XpForLevel: Mathf.Round(base × level^exponent)
        return round(f32(f32(v["base"]) * f32(max(1, level) ** f32(v["exponent"]))))

    total, totals = 0, {}
    for level in range(1, int(v["max"])):
        totals[level] = total
        total += to_next(level)
    totals[int(v["max"])] = total
    shown = [lvl for lvl in (2, 10, 25, 50, 75, 100, 125, 150, 175, int(v["max"])) if lvl <= v["max"]]
    rows = [[str(lvl), f"{to_next(lvl):,}" if lvl < v["max"] else "—", f"{totals[lvl]:,}"] for lvl in shown]
    return ([ui("formula.player-levels.text", max=int(v["max"])), ""]
            + _formula(ui("formula.player-levels.formula", base=_n(v["base"], 3), exp=_n(v["exponent"], 3)))
            + _table([ui("formula.level"), ui("formula.player-levels.next_col"), ui("formula.player-levels.total_col")], rows)
            + [ui("formula.player-levels.points", points=_n(v["points"])), "",
               ui("formula.player-levels.death", death=_pct(v["death"]), term=_term(ctx, "death-xp", page)), ""])


def _strength(ctx, page, v):
    ui, d = ctx.loc.ui, ctx.loc.difficulty
    rows = [[n, f"×{_n(h, 3)}", f"×{_n(dm, 3)}", f"×{_n(bh, 3)}", f"×{_n(bd, 3)}"]
            for n, h, dm, bh, bd in zip(_stages(ctx), d["health"], d["damage"], d["bossHealth"], d["bossDamage"])]
    species = ", ".join(f"{ctx.loc.creature(s)} ×{_n(f)}" for s, f in d["species"].items() if s != "Draugr_Ranged")
    presets = [[ui(f"formula.preset.{k}"), _n(p["Health"]), _n(p["Damage"]), f"{_n(p['Star'])}%", _n(p["MaxStars"])]
               for k, p in d["presets"].items()]
    return ([ui("formula.creature-strength.text"), ""]
            + _formula(ui("formula.creature-strength.health")) + _formula(ui("formula.creature-strength.damage"))
            + [ui("formula.creature-strength.terms", tamed=_pct(v["tamed"]), power=_anchor("monster-power", page),
                  stars=_anchor("stars", page)), ""]
            + [f"### {ui('formula.stage_table')}", "", ui("formula.stage_note"), ""]
            + _table([ui("bosses.biome"), ui("formula.health"), ui("formula.damage"), ui("formula.boss_health"),
                      ui("formula.boss_damage")], rows)
            + [ui("formula.creature-strength.species", species=species), ""]
            + ([ui("formula.creature-strength.fixed", creatures=", ".join(ctx.loc.creature(c) for c in d["fixedHealth"])), ""]
               if d.get("fixedHealth") else [])
            + [f"### {ui('formula.presets')}", "", ui("formula.presets_note"), ""]
            + _formula(ui("formula.creature-strength.soften"))
            + _table([ui("formula.preset_col"), ui("formula.health_scale"), ui("formula.damage_scale"),
                      ui("formula.star_chance"), ui("formula.max_stars")], presets))


def _boss_step(ctx, page, v):
    ui, d = ctx.loc.ui, ctx.loc.difficulty
    near, far = d["bossStep"]
    rows = [[n, f"{_n(a, 0)} m", f"{_n(b, 0)} m"] for n, a, b in list(zip(_stages(ctx), d["ringNear"], d["ringFar"]))[:-1]]
    return ([ui("formula.boss-step.text", near=_pct(near), far=_pct(far)), ""]
            + _formula(ui("formula.boss-step.formula", near=_n(near), far=_n(far)))
            + _table([ui("bosses.biome"), ui("formula.ring_near"), ui("formula.ring_far")], rows)
            + [ui("formula.boss-step.species"), ""])


def _stars(ctx, page, v):
    from .monster_pages import MODS_PAGE

    ui, p = ctx.loc.ui, v["chance"]
    odds = [["0", _pct(1 - p)], ["1", _pct(p * (1 - p))], ["2+", _pct(p * p)]]
    return ([ui("formula.stars.text", rarity=rel(MODS_PAGE, page)), ""]
            + _formula(ui("formula.stars.health", h=_n(v["health"]))) + _formula(ui("formula.stars.damage", d=_n(v["damage"])))
            + [ui("formula.stars.chance", chance=_pct(p), above=_pct(v["above_two"]), mods=v["mods_per_star"],
                  home=v["home_max_level"] - 1), ""]
            + _table([ui("monsters.stars"), ui("formula.odds")], odds))


def _boss_stars(ctx, page, v):
    from .monster_pages import BOSSES_PAGE

    ui = ctx.loc.ui
    return ([ui("formula.boss-stars.text", chance=_pct(v["chance"]), two=_pct(v["two"]), bosses=rel(BOSSES_PAGE, page)), ""]
            + _formula(ui("formula.boss-stars.health", h=_n(v["health"]))) + _formula(ui("formula.boss-stars.damage", d=_n(v["damage"])))
            + [ui("formula.boss-stars.notes", mods=v["mods_per_star"]), ""])


def _power(ctx, page, v):
    ui, mp = ctx.loc.ui, ctx.loc.difficulty["monsterPower"]
    step, cap = mp["step"] + mp["biome-step"], mp["max"]
    return ([ui("formula.monster-power.text"), ""]
            + _formula(ui("formula.monster-power.formula", step=_n(step), max=_n(cap)))
            + [ui("formula.monster-power.notes", n=round((cap - 1) / step) if step else 0, loot=_anchor("loot", page)), ""])


def _one(v: float) -> str:
    return f"1 in {round(1 / v):,}" if 0 < v < 1 else (f"{v:.2g}" if v else "—")


def loot_per_kill(ctx: Ctx, s: dict) -> dict[str, float]:
    """Average drops per kill (or chest) of a source at quantity 1 and no rarity (LootDrops.Roll):
    its expected draws (lambda) split by the group weights; equipment draws give magic-or-better
    gear at the base drop rate (more in chests), currency at the currency rate."""
    v = _values().get("loot", {})
    total = max(0.0001, s.get("gear", 0) + s.get("currency", 0) + s.get("jewel", 0))
    chest = v.get("chest", 3.5) if s["id"] in ("chest", "dungeon-chest") else 1
    return {"gear": s["lambda"] * s.get("gear", 0) / total * v.get("gear_rate", 0.25) * chest,
            "currency": s["lambda"] * s.get("currency", 0) / total * v.get("currency_rate", 0.125) * v.get("currency_boost", 1),
            "gems": s["lambda"] * s.get("jewel", 0) / total}


def _loot(ctx, page, v):
    ui, loot = ctx.loc.ui, ctx.data.loot
    stars = loot.get("stars", {})

    def source(s):
        name = ui(f"gear.source.{s['id']}")
        return name if name != f"gear.source.{s['id']}" else s["id"]

    sources = []
    for s in loot.get("sources", []):
        per = loot_per_kill(ctx, s)
        sources.append([source(s), _one(per["gear"]), _one(per["currency"]), _one(per["gems"])])
    levels = [[str(r["level"]), _n(r["common"]), _n(r["magic"]), _n(r["rare"])] for r in loot.get("rarityByLevel", [])]
    return ([ui("formula.loot.text", quantity=_term(ctx, "item-quantity", page), rarity=_term(ctx, "item-rarity", page)), ""]
            + _formula(ui("formula.loot.quantity", star=_n(stars.get("quantityPerStar", 0)), mod=_n(v["per_modifier"])))
            + _formula(ui("formula.loot.rarity", star=_n(stars.get("rarityPerStar", 0))))
            + [ui("formula.loot.notes"), ""]
            + [f"### {ui('formula.loot.sources')}", "", ui("formula.loot.sources_note"), ""]
            + _table([ui("gear.source_label"), ui("formula.loot.gear"), ui("formula.loot.currency"), ui("formula.loot.jewel")], sources)
            + [ui("formula.loot.gates"), ""]
            + [f"### {ui('formula.loot.by_level')}", "", ui("formula.loot.by_level_note"), ""]
            + _formula(ui("formula.loot.curve"))
            + _table([ui("formula.level"), ui("formula.loot.common"), ui("formula.loot.magic"), ui("formula.loot.rare")], levels)
            + [ui("formula.loot.unique", chance=_pct(loot.get("uniqueChance", 0)), level=loot.get("rareGuaranteeMinLevel", 0)), ""])


def _vanilla_drops(ctx, page, v):
    ui = ctx.loc.ui
    return [ui("formula.vanilla-drops.text"), ""] + _formula(ui("formula.vanilla-drops.formula", s=_n(v["per_star"]), cap=v["cap"]))


def _experience(ctx, page, v):
    ui = ctx.loc.ui
    return ([ui("formula.experience.sources", falloff=_anchor("experience-falloff", page),
                craft=_term(ctx, "craft-experience", page)), ""]
            + [ui("formula.experience.text"), ""]
            + _formula(ui("formula.experience.formula", h=_n(v["per_health"]), s=_n(v["per_star"]),
                          m=_n(_values()["loot"].get("per_modifier", 0.5))))
            + [ui("formula.experience.notes", radius=_n(v["radius"]), boss=_n(v["boss_radius"]), night=_pct(v["night"]),
                  event=_pct(v["runic_event"])), ""])


def _crit_multiplier(ctx, page, v):
    ui = ctx.loc.ui
    return ([ui("formula.crit-multiplier.text", term=_term(ctx, "crit", page, start=True)), ""]
            + _formula(ui("formula.crit-multiplier.formula", base=_n(v["base"]))) + [ui("formula.crit-multiplier.notes"), ""])


def _crit_chance(ctx, page, v):
    ui = ctx.loc.ui
    return ([ui("formula.crit-chance.text"), ""] + _formula(ui("formula.crit-chance.formula"))
            + [ui("formula.crit-chance.bases", knives=_pct(v["knives"]), polearms=_pct(v["polearms"]),
                  other=_pct(v["other"]), spells=_pct(v["spells"]), ceiling=_pct(v["ceiling"])), ""])


def _evasion(ctx, page, v):
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})

    def accuracy(level: int, stars: int = 0) -> float:  # Evasion.AccuracyAt
        base = t["evasion.accuracy.base"] + t["evasion.accuracy.per-level"] * level ** max(0.1, t["evasion.accuracy.growth"])
        return max(1, base) * (1 + max(0, t["evasion.accuracy.per-star"]) * stars)

    def chance(rating: float, a: float) -> float:  # DefenceMath.Chance
        return max(0.0, min(min(0.999999, t["evasion.cap"]), 1 - max(1, t["evasion.hit-factor"]) * a / (a + rating)))

    ratings = (50, 100, 200, 400)
    rows = [[name, _n(accuracy(lvl), 0), *(_pct(chance(r, accuracy(lvl))) for r in ratings)] for name, lvl in _biomes(ctx)]
    return ([ui("formula.evasion.text", evade=_term(ctx, "evade", page, start=True), accuracy=_term(ctx, "enemy-accuracy", page)), ""]
            + _formula(ui("formula.evasion.accuracy", base=_n(t["evasion.accuracy.base"]), per=_n(t["evasion.accuracy.per-level"]),
                          star=_pct(t["evasion.accuracy.per-star"])))
            + _formula(ui("formula.evasion.chance", h=_n(t["evasion.hit-factor"]), cap=_pct(t["evasion.cap"])))
            + [ui("formula.evasion.notes"), ""]
            + _table([ui("bosses.biome"), ui("formula.evasion.acc_col"), *(ui("formula.evasion.rating_col", n=r) for r in ratings)], rows))


def _resistances(ctx, page, v):
    ui = ctx.loc.ui
    return ([ui("formula.resistances.text", term=_term(ctx, "resist", page, start=True)), ""]
            + _formula(ui("formula.resistances.formula", cap=_pct(v["cap"]), hard=_pct(v["hard_cap"])))
            + [ui("formula.resistances.notes"), ""])


def _armour(ctx, page, v):
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})

    def taken(damage: float, armour: float) -> float:  # Valheim's DamageTypes.ApplyArmor
        return damage - armour if armour < damage / 2 else min(1.0, damage / (armour * 4)) * damage

    hits, armours = (20, 50, 100, 200, 500), (25, 50, 100, 200)
    rows = [[str(a), *(_n(taken(h, a), 1) for h in hits)] for a in armours]
    return ([ui("formula.armour.text", term=_term(ctx, "armor", page, start=True)), ""]
            + _formula(ui("formula.armour.formula"))
            + _formula(ui("formula.armour.effective", effect=_n(t.get("armor.effect", 1))))
            + [ui("formula.armour.notes", pen=_anchor("enemy-penetration", page)), ""]
            + _table([ui("formula.armour.armour_col"), *(ui("formula.armour.hit_col", n=h) for h in hits)], rows))


def _penetration(ctx, page, v):
    from .monster_pages import mod_anchor

    ui, d = ctx.loc.ui, ctx.loc.difficulty
    t = d.get("tunables", {})
    rows = [[n, _n(a), _pct(r)] for n, a, r in zip(_stages(ctx), d["armorPen"], d["resistPen"])]
    piercing = next((m["name"] for m in ctx.loc.monsters.get("mods", []) if m["id"] == "piercing"), "Piercing")
    return ([ui("formula.enemy-penetration.text", armour=_term(ctx, "armour-penetration", page),
                resist=_term(ctx, "resistance-penetration", page), effect=_pct(t.get("armor.effect", 1))), ""]
            + _table([ui("bosses.biome"), ui("formula.pen.armour"), ui("formula.pen.resist")], rows)
            + [ui("formula.enemy-penetration.notes", piercing=f"[{piercing}]({rel(mod_anchor('piercing'), page)})"), ""])


def _build_cost(ctx, page, v):
    from .building_pages import BUILDINGS_PAGE

    ui = ctx.loc.ui
    return ([ui("formula.build-cost.text", cap=_pct(v["cap"]), buildings=rel(BUILDINGS_PAGE, page)), ""]
            + _formula(ui("formula.build-cost.formula", cap=_pct(v["cap"])))
            + [ui("formula.build-cost.notes", refund=_term(ctx, "refund", page)), ""])


# Each page's formulas, in order.
def _mastery(ctx, stat: str) -> tuple[str, str | None]:
    """The passive mastery option granting this stat: its title (the tree's own name) and page."""
    from .pages import option_path

    for g in ctx.option_groups.values():
        o = g["options"][0]
        if any(m.get("stat") == stat for m in o["raw"].get("mods") or []):
            return plain(o["title"]), option_path(ctx, g)
    return stat, None


def _mastery_link(ctx, stat: str, page: str) -> str:
    title, path = _mastery(ctx, stat)
    return f"[{title}]({rel(path, page)})" if path else title


def _strikes(ctx, page, v):
    """Additional strikes (Strikes): extra hits of a melee swing, at the nearest enemies not yet
    struck, or all into the first target with Focused Strikes; Double on Crit doubles them once."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    return ([ui("formula.strikes.text", strike=_term(ctx, "strike", page, start=True), interval=_n(t["strike.interval"]),
                radius=_n(t["strike.radius"]), reach=_n(t["strike.reach"])), ""]
            + _formula(ui("formula.strikes.formula", double=_mastery(ctx, "StrikeCritDouble")[0]))
            + [ui("formula.strikes.hits"), "",
               ui("formula.strikes.double", double=_mastery_link(ctx, "StrikeCritDouble", page)), "",
               ui("formula.strikes.focus", focus=_mastery_link(ctx, "StrikeFocusFire", page), pct=_pct(t["strike.focus-damage"])), "",
               ui("formula.strikes.combo", combo=_term(ctx, "series", page, start=True)), ""])


def _phantoms(ctx, page, v):
    """Phantom strikes (Phantoms): copies of a melee attack hit at a share of its finished damage,
    landing on random nearby enemies; Endless Apparition lets them chain."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    return ([ui("formula.phantom-strikes.text", phantom=_term(ctx, "phantom-strikes", page, start=True),
                radius=_n(t["phantom.radius"]), delay=_n(t["phantom.delay"]), interval=_n(t["phantom.interval"])), ""]
            + _formula(ui("formula.phantom-strikes.count"))
            + _formula(ui("formula.phantom-strikes.formula", share=_pct(t["phantom.damage"])))
            + [ui("formula.phantom-strikes.damage", share=_pct(t["phantom.damage"])), "",
               ui("formula.phantom-strikes.chain", recursion=_term(ctx, "phantom-recursion", page, start=True), max=v["max_pending"]), ""])


def _attributes(ctx, page, v):
    """Attributes (Progress.DeriveAttributes, StatText.SkillCenter/AttrPoints/AttrsFor): what each
    point gives, and how governing attributes set the weapon skill multiplier."""
    ui, d = ctx.loc.ui, ctx.loc.difficulty
    slugs = {"AttrMight": "might", "AttrFinesse": "finesse", "AttrSpirit": "spirit"}
    names = {a: _term(ctx, slug, page, start=True) for a, slug in slugs.items()}
    titles = {a: plain(ctx.loc.wiki[slug]["title"]) if slug in ctx.loc.wiki else a for a, slug in slugs.items()}

    def gives(key: str, amount: float, pct: bool, term: str) -> list[str]:
        one = f"{amount * 100:.4g}%" if pct else _n(amount, 3)  # per point: 0.125%, not rounded to 0.12%
        hundred = _pct(amount * 100) if pct else _n(amount * 100, 1)
        return [ui(key, x=one, term=_term(ctx, term, page)), ui(key, x=hundred, term=_term(ctx, term, page))]

    rows = []
    for attr, parts in (("AttrMight", [("formula.attributes.increased", v["health_regen"], True, "health-regen"),
                                       ("formula.attributes.plus", v["carry_weight"], False, "weight")]),
                        ("AttrFinesse", [("formula.attributes.increased_regen", v["stamina_regen"], True, "stamina"),
                                         ("formula.attributes.increased", v["evasion"], True, "evade")]),
                        ("AttrSpirit", [("formula.attributes.increased_regen", v["eitr_regen"], True, "eitr"),
                                        ("formula.attributes.plus", v["rune_shield"], False, "shield")])):
        cells = [gives(*p) for p in parts]
        rows.append([names[attr], "<br>".join(c[0] for c in cells), "<br>".join(c[1] for c in cells)])
    md = [ui("formula.attributes.text"), ""] + _table([ui("formula.attributes.attribute"), ui("formula.attributes.per_point"),
                                                       ui("formula.attributes.per_hundred")], rows)

    def center(points: float) -> float:  # StatText.SkillCenter
        return v["center"] * (1 + v["coef"] * (points / v["full_points"]) ** 0.75)

    md += [ui("formula.attributes.skill", factor=_term(ctx, "skill-factor", page), spread=_n(v["spread"])), ""]
    md += _formula(ui("formula.attributes.formula", center=_n(v["center"]), coef=_n(v["coef"]), full=_n(v["full_points"])))
    md += _table([ui("formula.attributes.points"), *(str(p) for p in (0, 50, 100, 200, 300, 500))],
                 [[ui("formula.attributes.midpoint"), *(_n(center(p), 2) for p in (0, 50, 100, 200, 300, 500))]])
    governing = d.get("governing") or {}
    skill_rows = [[ctx.loc.vkey(f"skill_{s.lower()}", s), ", ".join(titles[a] for a in attrs)]
                  for s, attrs in governing.items()]
    md += [ui("formula.attributes.governing"), ""] + _table([ui("formula.attributes.weapon"), ui("formula.attributes.governs")], skill_rows)
    md += [ui("formula.attributes.scepters", str=titles["AttrMight"], int=titles["AttrSpirit"]), ""]
    if _mastery(ctx, "MasteryAttrs1")[1]:
        md += [ui("formula.attributes.shifted", mastery=_mastery_link(ctx, "MasteryAttrs1", page), str=titles["AttrMight"],
                  dex=titles["AttrFinesse"],
                  pct=_pct(d.get("tunables", {}).get("attrs.might-covers", 0))), ""]
    return md


# Each ailment: its keyword, and the keyword of the damage that fills its gauge (AilmentDamage.Component).
_AILMENTS = {"bleed": "slash", "burn": "fire-damage", "poison": "poison-damage", "frost": "frost-damage", "shock": "lightning-damage"}


def _title_of(ctx, key: str) -> str:
    return plain(ctx.loc.wiki[key]["title"]) if key in ctx.loc.wiki else key


def _ail_gauge(ctx, page, v, ailment: str | None = None) -> list[str]:
    """The gauge: how much a hit fills, an example table, how long it lasts. With an ailment, the
    formula names its damage type and the table (the same for every ailment) is left out."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    threshold = t["ailment.threshold"]
    buildup = _title_of(ctx, "build-up").lower()
    damage = _title_of(ctx, _AILMENTS[ailment]).lower() if ailment else ui("formula.ailments.damage")
    md = _formula(ui("formula.ailments.formula", threshold=_pct(threshold), buildup=buildup, damage=damage))  # plain: no links in the block
    shares = (0.05, 0.1, 0.25, 0.5)
    md += [] if ailment else [ui("formula.ailments.example"), ""] + _table(
        [ui("formula.ailments.share"), *(_pct(s) for s in shares)],
        [[ui("formula.ailments.fill", amount=_pct(b), buildup=buildup), *(_pct(min(1.0, s / threshold * (1 + b))) for s in shares)] for b in (0, 1)])
    return md + [ui("formula.ailments.lasts", hold=_n(v["hold"]), drain=_pct(v["drain"]), total=_n(v["hold"] + 1 / v["drain"])), ""]


def _ail_effect(ctx, page, v, ailment: str) -> str:
    """What one ailment does with the damage that set it off."""
    ui = ctx.loc.ui
    if ailment == "bleed":
        return ui("formula.ailments.bleed", total=_pct(v["bleed_share"] * v["bleed_ticks"]), ticks=_n(v["bleed_ticks"]),
                  share=_pct(v["bleed_share"]))
    return ui(f"formula.ailments.{'chill' if ailment == 'frost' else ailment}", stagger=_term(ctx, "stagger", page))


def _ailments(ctx, page, v):
    """Ailments (AilmentGauges, Ailments, Combat.OpenWound): the gauge a hit fills, how long an
    ailment lasts, and what each one does with the damage that set it off."""
    ui = ctx.loc.ui
    term = {k: _term(ctx, k, page) for k in _AILMENTS}
    md = [ui("formula.ailments.text", gauge=_term(ctx, "ailment-gauge", page, start=True), **term), ""]
    md += _ail_gauge(ctx, page, v)
    md += [ui("formula.ailments.each"), ""]
    md += [f"- {_term(ctx, a, page, start=True)}: {_ail_effect(ctx, page, v, a)}" for a in _AILMENTS] + [""]
    return md


def _ailment_view(ailment: str):
    """One ailment's own entry, for its keyword page: what fills its gauge, what it does."""
    def view(ctx, page, v):
        ui = ctx.loc.ui
        return ([ui("formula.ailments.one", ailment=_title_of(ctx, ailment), damage=_term(ctx, _AILMENTS[ailment], page),
                    gauge=_term(ctx, "ailment-gauge", page)), ""]
                + _ail_gauge(ctx, page, v, ailment)
                + [ui("formula.ailments.does", text=_ail_effect(ctx, page, v, ailment)), ""])
    return view


def _rune_shield(ctx, page, v):
    """Rune shield (EnergyShield): its size, what it takes, its recharge; it halves stagger taken
    while it holds (RuneStaggerGuard)."""
    ui = ctx.loc.ui
    t = ctx.loc.difficulty.get("tunables", {})
    md = [ui("formula.rune-shield.text", shield=_term(ctx, "shield", page, start=True), block=_term(ctx, "block", page),
             stagger=_term(ctx, "stagger", page), guard=_pct(v["stagger_guard"])), ""]
    md += _formula(ui("formula.rune-shield.formula"))
    md += [ui("formula.rune-shield.notes", base=_n(v["base"]), cap=_pct(v["from_life_cap"])), ""]
    full = 1 / v["rate"]
    md += [ui("formula.rune-shield.recharge", delay=_n(v["delay"]), rate=_pct(v["rate"]), full=_n(full),
              cap=_pct(t.get("shield.delay-cap", 0)), floor=_n(v["min_delay"])), ""]
    return md


def _stagger(ctx, page, v):
    """Stagger (Valheim's gauge; Effects.Stagger, the slower enemy drain, stagger resistance)."""
    ui = ctx.loc.ui
    d = ctx.loc.difficulty
    buildup = _title_of(ctx, "build-up").lower()
    drain_enemy = v["drain_seconds"] / v["share"]
    md = [ui("formula.stagger.text", stagger=_term(ctx, "stagger", page, start=True), drain=_n(v["drain_seconds"]),
             enemy=_n(drain_enemy)), ""]
    md += _formula(ui("formula.stagger.formula", share=_pct(v["share"]), buildup=buildup))
    md += [ui("formula.stagger.yours", share=_pct(v["share"]), power=_term(ctx, "stagger-power", page)), "",
           ui("formula.stagger.forced", forced=_term(ctx, "stun-chance", page, start=True)), "",
           ui("formula.stagger.taken", res=_term(ctx, "stagger-res", page), cap=_pct(d.get("caps", {}).get("StaggerResistPct", 0)),
              shield=_term(ctx, "shield", page), guard=_pct(v["stagger_guard"])), ""]
    return md


def _charged(ctx, page, v):
    """Charged attacks (ChargedAttacks, AttackChargeState): one pending charge, spent by the next
    eligible weapon attack; its damage bonus, cooldowns, Unbound Charge and hit splash."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    return ([ui("formula.charged-attacks.text", charged=_term(ctx, "charged-attack", page, start=True),
                spells=_mastery_link(ctx, "ChargeApplicability", page)), ""]
            + _formula(ui("formula.charged-attacks.formula", inc=_pct(v["increase"])))
            + [ui("formula.charged-attacks.cooldown", source=_n(t["charge.source-cooldown"]), crit=_n(t["charge.source-cooldown.crit"]),
                  shared=_n(t["charge.cooldown"])), "",
               ui("formula.charged-attacks.alt", only_alt=_mastery_link(ctx, "MasteryCharged1", page),
                  no_alt=_mastery_link(ctx, "MasteryAlternative2", page)), "",
               ui("formula.charged-attacks.double", double=_term(ctx, "charged-effects-double", page, start=True),
                  inc=_pct(2 * v["increase"])), "",
               ui("formula.charged-attacks.splash", splash=_term(ctx, "hit-splash", page, start=True),
                  radius=_n(t["splash.radius"]), area=_term(ctx, "area", page)), ""])


def _area(ctx, page, v):
    """Area of effect (Blasts.AreaFactor): one factor on the radius, not on the area."""
    ui = ctx.loc.ui
    return ([ui("formula.area.text", area=_term(ctx, "area", page, start=True)), ""]
            + _formula(ui("formula.area.formula", floor=_n(v["floor"])))
            + [ui("formula.area.notes", slam=_term(ctx, "slam", page)), ""])


def _slams(ctx, page, v):
    """Slams (Slams.IsSlam, GroundStrike) and aftershocks (Aftershock.Roll/Initial/OnCharged)."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    return [ui("formula.slams.text", slam=_term(ctx, "slam", page, start=True), ground=_mastery_link(ctx, "MasterySlam1", page),
               radius=_n(t["slam.ground-radius"]), area=_term(ctx, "area", page)), "",
            ui("formula.slams.aftershock", aftershock=_term(ctx, "aftershock", page, start=True), delay=_n(t["aftershock.delay"])), "",
            ui("formula.slams.charged", charged=_term(ctx, "charged-attack", page), delay=_n(t["aftershock.delay"])), ""]


def _block(ctx, page, v):
    """Block (Valheim's Humanoid.BlockAttack; the mod's Preview.ShieldBlock and parry bonus)."""
    ui = ctx.loc.ui
    md = [ui("formula.block.text", block=_term(ctx, "block", page, start=True)), ""]
    md += _formula(ui("formula.block.power"))
    md += _formula(ui("formula.block.base", skill=_n(v["skill_share"])))
    md += _formula(ui("formula.block.parry"))
    md += [ui("formula.block.parry_text", window=_n(v["parry_window"])), "",
           ui("formula.block.blocked", armour=_term(ctx, "armor", page)), "",
           ui("formula.block.guard", stagger=_term(ctx, "stagger", page), glance=_term(ctx, "glance", page, start=True)), ""]
    return md


def _glancing(ctx, page, v):
    """Glancing blows (Glancing.Roll/Cut, Effects' damage-taken multiplier)."""
    ui, d = ctx.loc.ui, ctx.loc.difficulty
    cap = d.get("caps", {}).get("GlancingChance")  # none in 5.1.2: a chance of 100% or more always glances
    md = [ui("formula.glancing.text", glance=_term(ctx, "glance", page, start=True), chance=_pct(v["chance"]))
          + (" " + ui("formula.glancing.cap", cap=_pct(cap)) if cap else ""), ""]
    md += _formula(ui("formula.glancing.formula", cut=_pct(v["cut"]), lo=_pct(v["cut_min"]), hi=_pct(v["cut_max"])))
    md += [ui("formula.glancing.taken", floor=_pct(1 - v["taken_floor"])), "",
           ui("formula.glancing.block", block=_term(ctx, "block", page), guard=_mastery_link(ctx, "MasteryGlancing1", page)), ""]
    return md


def _thorns(ctx, page, v):
    """Thorns (Combat.Thorns: Amount, Fill, Falloff, ResponseMultiplier; ContactThorns)."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    md = [ui("formula.thorns.text", thorns=_term(ctx, "thorns", page, start=True), base=_n(t["thorns.increased.base"])), ""]
    md += _formula(ui("formula.thorns.formula"))
    md += [ui("formula.thorns.type"), "",
           ui("formula.thorns.range", full=_n(v["full_range"]), zero=_n(v["zero_range"])), "",
           ui("formula.thorns.block", block=_pct(t["thorns.block.share"]), shield=_mastery_link(ctx, "ShieldBlockThorns", page)), "",
           ui("formula.thorns.contact", carapace=_mastery_link(ctx, "ThornsContact", page)), ""]
    return md


def _armour_break(ctx, page, v):
    """Armour break (Corrosion: Strike, Bite, Carry): blunt fills a broken share that adds the enemy's
    armour back to your physical damage."""
    ui = ctx.loc.ui
    md = [ui("formula.armour-break.text", brk=_term(ctx, "corrosion", page, start=True), gauge=_term(ctx, "ailment-gauge", page),
             buildup=_term(ctx, "build-up", page), seconds=_n(v["seconds"])), ""]
    md += _formula(ui("formula.armour-break.fill"))
    md += _formula(ui("formula.armour-break.formula"))
    md += [ui("formula.armour-break.notes", armour=_term(ctx, "armor", page)), ""]
    return md


def _lifesteal(ctx, page, v):
    """Life leech (DamageNet: Sip, Leech, Pull)."""
    ui = ctx.loc.ui
    md = [ui("formula.lifesteal.text", leech=_term(ctx, "lifesteal", page, start=True)), ""]
    md += _formula(ui("formula.lifesteal.formula"))
    md += [ui("formula.lifesteal.rate", rate=_pct(v["rate"]), cap=_pct(v["ceiling"]), n=_n(v["ceiling"] / v["rate"])), ""]
    return md


def _impale(ctx, page, v):
    """Impale (Impale: Chance, Strike, Soften, LimitOf, PerStack, Window)."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    md = [ui("formula.impale.text", impale=_term(ctx, "impale", page, start=True), gauge=_term(ctx, "ailment-gauge", page),
             buildup=_term(ctx, "build-up", page)), ""]
    md += _formula(ui("formula.impale.chance"))
    md += _formula(ui("formula.impale.formula", stack=_pct(t["impale.stack"])))
    md += [ui("formula.impale.notes", limit=_n(t["impale.limit"]), window=_n(t["impale.window"]), floor=_n(v["min_window"])), ""]
    return md


def _endurance(ctx, page, v):
    """Endurance (Endurance.Threshold/Reduction/Reduce), after resistances in the mod's damage step."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    md = [ui("formula.endurance.text", endurance=_term(ctx, "endurance", page, start=True)), ""]
    md += _formula(ui("formula.endurance.formula"))
    md += [ui("formula.endurance.notes", base=_pct(t["endurance.base"]), cap=_pct(t["endurance.cap"]),
              rune=_mastery_link(ctx, "SteadfastRuneThreshold", page), shield=_term(ctx, "shield", page)), "",
           ui("formula.endurance.order", res=_term(ctx, "resist", page), block=_term(ctx, "block", page), armour=_term(ctx, "armor", page)), ""]
    return md


def _hit_flat(ctx, page, v):
    """Flat damage (Effects.AddFlatDamage, Oils.AddTo): what goes where, × the skill roll."""
    ui = ctx.loc.ui
    md = [ui("formula.hit-damage.flat", flat=_term(ctx, "flat-damage", page, start=True), factor=_term(ctx, "skill-factor", page)), ""]
    md += [f"- {ui(f'formula.hit-damage.flat_{k}')}" for k in ("main", "physical", "typed", "element", "elemental")] + [""]
    return md + [ui("formula.hit-damage.oil", oil=_term(ctx, "oil", page)), ""]


def _hit_conversion(ctx, page, v):
    """Conversion (Conversion.Hit, Gains; DamageModel.Grown): physical only, before increases;
    converted damage grows with both types' increases."""
    ui = ctx.loc.ui
    md = [ui("formula.hit-damage.conversion", conversion=_term(ctx, "conversion", page, start=True)), ""]
    md += _formula(ui("formula.hit-damage.conversion_formula"))
    return md + [ui("formula.hit-damage.converted"), "",
                 ui("formula.hit-damage.gain", gain=_term(ctx, "gain-as-extra", page, start=True)), ""]


def _hit_increases(ctx, page, v):
    """Increases (Effects.ContextOutgoingMult, DamageModel.TypeIncrease/Increase/Layer): one sum,
    each type adding its own."""
    ui = ctx.loc.ui
    md = [ui("formula.hit-damage.increases"), ""]
    md += _formula(ui("formula.hit-damage.increases_formula"))
    return md + [ui("formula.hit-damage.typed"), ""]


def _hit_more(ctx, page, v):
    """More multipliers (MoreDamage.Of, Rage.DamageMore), projectile and torch factors."""
    ui, t = ctx.loc.ui, ctx.loc.difficulty.get("tunables", {})
    return [ui("formula.hit-damage.more", rage=_term(ctx, "rage", page), per=_pct(t["rage.more-per-point"])), "",
            ui("formula.hit-damage.projectile", proj=_term(ctx, "proj", page, start=True), torch=_term(ctx, "torch", page)), ""]


def _hit_target(ctx, page, v):
    """On the enemy (XpSources Character_Damage.Prepare, CrossDamage): increases that depend on it
    join the same sum; its flat damage comes after the crit."""
    ui = ctx.loc.ui
    md = [ui("formula.hit-damage.target"), ""]
    md += [f"- {ui('formula.hit-damage.target_kind')}",
           f"- {ui('formula.hit-damage.target_backstab', backstab=_term(ctx, 'backstab', page))}",
           f"- {ui('formula.hit-damage.target_stagger', stagger=_term(ctx, 'stagger', page), x=_pct(v['staggered']))}",
           f"- {ui('formula.hit-damage.target_charged', charged=_term(ctx, 'charged-attack', page), x=_pct(_values()['charged-attacks']['increase']))}", ""]
    return md + [ui("formula.hit-damage.target_flat", crit=_term(ctx, "crit", page)), "",
                 ui("formula.hit-damage.target_both"), ""]


_HIT_PARTS = {"flat": _hit_flat, "conversion": _hit_conversion, "increases": _hit_increases, "more": _hit_more, "target": _hit_target}


def _hit_damage(ctx, page, v):
    """How a hit's damage is built, part by part (each part is also a keyword page's view)."""
    ui = ctx.loc.ui
    md = [ui("formula.hit-damage.text", order=f"[{ui('formula.hit-order.title')}]({_anchor('hit-order', page)})"), ""]
    for part, body in _HIT_PARTS.items():
        md += [f"### {ui(f'formula.hit-damage.{part}_title')} {{ #hit-{part} }}", ""] + body(ctx, page, v)
    return md


def _hit_view(part: str):
    def view(ctx, page, v):
        return _HIT_PARTS[part](ctx, page, v) + [
            ctx.loc.ui("formula.hit-damage.see_order", title=ctx.loc.ui("formula.hit-order.title"), link=_anchor("hit-order", page)), ""]
    return view


def _hit_order(ctx, page, v):
    """The order of a hit's steps: the mod's ModifyAttackBuild when the hit is made, then
    Character_Damage.Prepare and Valheim's RPC_Damage when it reaches the enemy."""
    ui = ctx.loc.ui
    def link(title: str, anchor: str, start: bool) -> str:  # a section of this page, lower-cased unless it starts the sentence
        return f"[{title if start else title[:1].lower() + title[1:]}]({rel(COMBAT_PAGE, page)}#{anchor})"

    part = lambda p, start=True: link(ui(f"formula.hit-damage.{p}_title"), f"hit-{p}", start)  # noqa: E731
    sec = lambda fid, start=False: link(ui(f"formula.{fid}.title"), fid, start)  # noqa: E731
    made = [ui("formula.hit-order.base", factor=_term(ctx, "skill-factor", page)),
            ui("formula.hit-order.oil", oil=_term(ctx, "oil", page)),
            ui("formula.hit-order.flat", flat=part("flat")),
            ui("formula.hit-order.conversion", conversion=part("conversion"), gain=_term(ctx, "gain-as-extra", page)),
            ui("formula.hit-order.increases", increases=part("increases")),
            ui("formula.hit-order.more", more=part("more"), rage=_term(ctx, "rage", page)),
            ui("formula.hit-order.projectile", proj=_term(ctx, "proj", page), torch=_term(ctx, "torch", page))]
    lands = [ui("formula.hit-order.crit", crit=sec("crit-multiplier", start=True)),
             ui("formula.hit-order.target", target=part("target", start=False)),
             ui("formula.hit-order.both"),
             ui("formula.hit-order.physical", brk=sec("armour-break", start=True), impale=sec("impale")),
             ui("formula.hit-order.resist", pen=sec("player-penetration"))]
    md = [ui("formula.hit-order.text"), "", f"**{ui('formula.hit-order.made')}**", ""]
    md += [f"{i}. {s}" for i, s in enumerate(made, 1)] + ["", f"**{ui('formula.hit-order.lands')}**", ""]
    md += [f"{i}. {s}" for i, s in enumerate(lands, len(made) + 1)] + [""]
    return md + [ui("formula.hit-order.notes"), ""]


_MODIFIERS = ("very_weak", "weak", "slightly_weak", "normal", "slightly_resistant", "resistant", "very_resistant", "immune")


def _player_penetration(ctx, page, v):
    """Your resistance penetration against creatures (Penetration, PenetrationMath): it adds to the
    share of damage Valheim's resistance step lets through, even against immunity."""
    ui = ctx.loc.ui
    md = [ui("formula.player-penetration.text", pen=_term(ctx, "resistance-penetration", page)), ""]
    md += _formula(ui("formula.player-penetration.formula"))
    pens = (0.1, 0.25, 0.5)
    md += _table([ui("formula.player-penetration.modifier"), ui("formula.player-penetration.resistance"), ui("formula.player-penetration.taken"),
                  *(ui("formula.player-penetration.with", x=_pct(p)) for p in pens)],
                 [[ui(f"formula.player-penetration.{m}"), _pct(v[m]), _pct(1 - v[m]), *(_pct(max(0.0, 1 - v[m] + p)) for p in pens)]
                  for m in _MODIFIERS])
    return md + [ui("formula.player-penetration.notes"), ""]


_PAGES = {
    CREATURES_PAGE: ("creatures", [("creature-strength", _strength), ("boss-step", _boss_step),
                                   ("stars", _stars), ("boss-stars", _boss_stars), ("monster-power", _power)]),
    LOOT_PAGE: ("loot", [("loot", _loot), ("vanilla-drops", _vanilla_drops)]),
    EXPERIENCE_PAGE: ("experience", [("creature-level", _level), ("item-level", _item_level), ("experience", _experience),
                                     ("experience-falloff", _falloff), ("player-levels", _player_levels)]),
    COMBAT_PAGE: ("combat", [("attributes", _attributes), ("hit-order", _hit_order), ("hit-damage", _hit_damage),
                             ("player-penetration", _player_penetration), ("crit-multiplier", _crit_multiplier), ("crit-chance", _crit_chance), ("evasion", _evasion),
                             ("resistances", _resistances), ("armour", _armour), ("rune-shield", _rune_shield), ("enemy-penetration", _penetration), ("stagger", _stagger),
                             ("block", _block), ("glancing", _glancing), ("endurance", _endurance), ("thorns", _thorns),
                             ("charged-attacks", _charged), ("strikes", _strikes), ("phantom-strikes", _phantoms), ("area", _area), ("slams", _slams),
                             ("ailments", _ailments), ("armour-break", _armour_break), ("impale", _impale), ("lifesteal", _lifesteal), ("build-cost", _build_cost)]),
}
_TITLES = {"creatures": "formula.creatures", "loot": "formula.loot_page", "combat": "formula.combat",
           "experience": "formula.experience_page"}
_BODIES = {fid: body for _, formulas in _PAGES.values() for fid, body in formulas}
FORMULA_PAGES = {fid: page for page, (_, formulas) in _PAGES.items() for fid, _ in formulas}

# Keywords of the mod's wiki -> the formulas that explain them, shown at the top of their page.
TERM_FORMULAS = {
    "crit": ["crit-chance", "crit-multiplier"],
    "armor": ["armour", "enemy-penetration"],
    "armour-penetration": ["enemy-penetration"],
    "evade": ["evasion"],
    "enemy-accuracy": ["evasion"],
    "resist": ["resistances"],
    "resistance-penetration": ["player-penetration", "resistances", "enemy-penetration"],
    "item-quantity": ["loot"],
    "item-rarity": ["loot"],
    "refund": ["build-cost"],
    "boss": ["boss-stars"],
    "xp": ["experience", "experience-falloff", "player-levels"],
    "biome-level": ["creature-level", "experience-falloff"],
    "death-xp": ["player-levels"],
    "strike": ["strikes"],
    "attributes": ["attributes"],
    "might": ["attributes"],
    "finesse": ["attributes"],
    "spirit": ["attributes"],
    "skill-factor": ["attributes"],
    "shield": ["rune-shield"],
    "stagger": ["stagger"],
    "stagger-res": ["stagger"],
    "stagger-power": ["stagger"],
    "stun-chance": ["stagger"],
    "ailment": ["ailments"],
    "ailment-damage": ["ailments"],
    "ailment-gauge": ["ailments:gauge"],
    "build-up": ["ailments:gauge"],
    "bleed": ["ailments:bleed"],
    "burn": ["ailments:burn"],
    "poison": ["ailments:poison"],
    "frost": ["ailments:frost"],
    "shock": ["ailments:shock"],
    "phantom-strikes": ["phantom-strikes"],
    "phantom-recursion": ["phantom-strikes"],
    "charged-attack": ["charged-attacks"],
    "charged-effects-double": ["charged-attacks"],
    "hit-splash": ["charged-attacks"],
    "area": ["area"],
    "slam": ["slams", "area"],
    "aftershock": ["slams"],
    "block": ["block"],
    "glance": ["glancing"],
    "thorns": ["thorns"],
    "lifesteal": ["lifesteal"],
    "impale": ["impale"],
    "corrosion": ["armour-break"],
    "endurance": ["endurance"],
    "flat-damage": ["hit-damage:flat"],
    "oil": ["hit-damage:flat"],
    "conversion": ["hit-damage:conversion"],
    "gain-as-extra": ["hit-damage:conversion"],
    "elemental-split": ["hit-damage:increases"],
    "physical": ["hit-damage:increases", "hit-damage:conversion"],
    **{k: ["hit-damage:increases"] for k in ("slash", "pierce", "blunt", "fire-damage", "frost-damage", "lightning-damage",
                                             "poison-damage", "spirit-damage")},
    "rage": ["hit-damage:more"],
    "proj": ["hit-damage:more"],
    "torch": ["hit-damage:more"],
    "backstab": ["hit-damage:target"],
}


def _views() -> dict[tuple[str, str], tuple[str, object]]:
    """Parts of a formula a keyword page shows instead of the whole block: (formula, view) ->
    (heading ui key, body)."""
    out = {("ailments", "gauge"): ("formula.ailments.gauge_title", lambda ctx, page, v: _ail_gauge(ctx, page, v))}
    out.update({("ailments", a): ("formula.ailments.how", _ailment_view(a)) for a in _AILMENTS})
    out.update({("hit-damage", p): (f"formula.hit-damage.{p}_title", _hit_view(p)) for p in _HIT_PARTS})
    return out


def formula_block(ctx: Ctx, fid: str, page: str, level: int = 2, anchor: bool = True, view: str | None = None,
                  heading: str | None = None) -> list[str]:
    """A formula's heading and block for a page, or a note that it is being re-checked. A view
    shows one part of it (a keyword page's own entry); a heading replaces its title."""
    ui = ctx.loc.ui
    title_key, body_of = _views()[(fid, view)] if view else (f"formula.{fid}.title", _BODIES[fid])
    head = "#" * level + f" {heading or ui(title_key)}" + (f" {{ #{fid} }}" if anchor else "")
    if not shown(ctx, fid):
        return [head, "", f'!!! warning "{ui("formula.rechecking_title")}"',
                f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]
    body = body_of(ctx, page, _values().get(fid, {}))
    # Sub-headings one level below the formula's own.
    body = ["#" * (level + 1) + line[3:] if line.startswith("### ") else line for line in body]
    return [head, ""] + body + [""]


def term_formulas(ctx: Ctx, key: str, page: str) -> list[str]:
    """The formulas of a keyword, for the top of its glossary page."""
    entries = TERM_FORMULAS.get(key, []) if ctx.loc.difficulty else []
    mechanics = ctx.loc.ui("formula.mechanics")
    # One formula goes under "Mechanics" (its title would repeat the keyword's); several keep
    # their titles below it.
    md = [f"## {mechanics}", ""] if len(entries) > 1 else []
    for entry in entries:
        fid, _, view = entry.partition(":")
        md += formula_block(ctx, fid, page, level=3 if len(entries) > 1 else 2, anchor=False, view=view or None,
                            heading=None if len(entries) > 1 else mechanics)
        title = ctx.loc.ui(_TITLES[_PAGES[FORMULA_PAGES[fid]][0]])
        link = f"{rel(COMBAT_PAGE, page)}#hit-{view}" if fid == "hit-damage" and view else _anchor(fid, page)  # its own part
        md += [ctx.loc.ui("formula.see_all", page=title, link=link), ""]
    return md


def page_formulas(ctx: Ctx) -> dict[str, str]:
    if not ctx.loc.difficulty:
        return {}
    pages = {}
    for page, (key, formulas) in _PAGES.items():
        md = [f"# {ctx.loc.ui(_TITLES[key])}", "", ctx.loc.ui(f"formula.{key}_intro"), "", ctx.loc.ui("formula.defaults_note"), ""]
        for fid, _ in formulas:
            md += formula_block(ctx, fid, page)
        pages[page] = "\n".join(md + _footer(ctx))
    return pages
