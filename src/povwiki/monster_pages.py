"""Monsters: the modifiers creatures can wear, and the rarity their stars give them.

- Modifiers (harness/monsters.py): each one's in-game name, description and icon, with its
  numbers at the server defaults. Some descriptions round (Swift: "half again" is 1.40×), so
  the numbers are shown beside them.
- Rarity: which star counts show as magic, rare and unique, in the game's colours.
"""

import html

from .markup import glossary_path, rel
from .pages import Ctx, _badge, _footer, _img, _table

MODS_PAGE = "monsters/mods.md"
_ELEMENTS = ("burning", "chilling", "shocking", "venomous")  # RarityMods.Fill: one per creature


def mod_anchor(mod_id: str) -> str:
    """Link target of one modifier, for pages that name it (bosses that never roll it...)."""
    return f"{MODS_PAGE}#mod-{mod_id}"


def _stars(stars: list[int], last: bool) -> str:
    if last:  # the top rarity has no ceiling
        return f"{stars[0]}+"
    return str(stars[0]) if len(stars) == 1 else f"{stars[0]}–{stars[-1]}"


def _settings(mod: dict) -> str:
    return "<br>".join(
        f'<span title="{html.escape(s["about"], quote=True)}">{s["label"]}</span>: **{s["value"]}**'
        for s in mod["settings"])


def page_monster_mods(ctx: Ctx) -> dict[str, str]:
    monsters, ui, page = ctx.loc.monsters, ctx.loc.ui, MODS_PAGE
    if not monsters.get("mods"):
        return {}
    names = {m["id"]: m["name"] for m in monsters["mods"]}
    md = [f"# {ui('monsters.mods')}", "", ui("monsters.mods_intro"), ""]

    md += [f"## {ui('monsters.rarity')}", "", ui("monsters.rarity_intro"), ""]
    tiers = monsters["rarity"]
    md += _table([ui("monsters.rarity_col"), ui("monsters.stars")], [
        [f'<span style="color:{t["color"]}">**{t["name"]}**</span>', _stars(t["stars"], t is tiers[-1])]
        for t in tiers])
    md += [ui("monsters.rarity_loot", quantity=rel(glossary_path("item-quantity"), page),
              rarity=rel(glossary_path("item-rarity"), page)), ""]

    off = set(monsters.get("bossOff") or [])
    md += [f"## {ui('monsters.modifiers')} ({len(monsters['mods'])})", "", ui("monsters.values_note"), ""]
    rows = []
    for m in monsters["mods"]:
        icon = _img(ctx.icons.path(m["icon"]), page, 40) if ctx.icons else ""
        badge = " " + _badge(ui("monsters.no_bosses"), ui("monsters.no_bosses_tip")) if m["id"] in off else ""
        rows.append([icon, f'<span id="mod-{m["id"]}"></span>**{m["name"]}**{badge}', m["about"], _settings(m) or "—"])
    md += _table(["", ui("col.name"), ui("monsters.in_game"), ui("monsters.values")], rows)

    md += [f"## {ui('monsters.rules')}", ""]
    md += [f"- {ui('monsters.rule_random')}"]
    md += [f"- {ui('monsters.rule_element', mods=', '.join(names[e] for e in _ELEMENTS if e in names))}"]
    if "blink" in names:
        md += [f"- {ui('monsters.rule_blink', mod=names['blink'])}"]
    if off:
        md += [f"- {ui('monsters.rule_bosses', mods=', '.join(names.get(i, i) for i in sorted(off, key=lambda i: names.get(i, i))))}"]
    md += [""]
    return {page: "\n".join(md + _footer(ctx))}


# ---- Bosses and creatures -----------------------------------------------------------------------

BOSSES_PAGE = "monsters/bosses.md"
CREATURES_PAGE = "monsters/creatures.md"
_SLOTS = ("Common", "Brute", "Special", "Champion")  # RunicBiomeKin.Slot


def boss_path(prefab: str) -> str:
    return f"monsters/boss/{prefab}.md"


def _mod_bosses(ctx: Ctx) -> dict[str, dict]:
    """prefab -> the mod's boss (Mist Mother, then the monolith bosses)."""
    b = ctx.loc.bosses
    found = {b["mistMother"]["prefab"]: b["mistMother"]} if b.get("mistMother") else {}
    found.update({m["prefab"]: m for m in (b.get("monolith") or {}).get("bosses", [])})
    return found


def _boss_tables(ctx: Ctx) -> set[str]:
    """Creatures with a loot table of the mod (Valheim's bosses, Kall included)."""
    return {cr for t in ctx.data.loot.get("tables") or [] for cr in t["creatures"]}


def creature_link(ctx: Ctx, prefab: str, page: str) -> str:
    """A creature's name, linked to its boss page (the mod's) or its row in the bosses list."""
    name = ctx.loc.creature(prefab)
    if prefab in _mod_bosses(ctx):
        return f"[{name}]({rel(boss_path(prefab), page)})"
    if prefab in _boss_tables(ctx) or any(v["prefab"] == prefab for v in ctx.loc.bosses.get("vanilla", [])):
        return f"[{name}]({rel(BOSSES_PAGE, page)}#{prefab.lower()})"
    return name


def _vh_creature(ctx: Ctx, prefab: str) -> dict:
    return ((ctx.loc.valheim or {}).get("creatures") or {}).get(prefab) or {}


def _trophy(ctx: Ctx, prefab: str, page: str, px: int) -> str:
    """A Valheim creature pictured by its trophy (its CharacterDrop)."""
    from .base_pages import _icon

    trophy = _vh_creature(ctx, prefab).get("trophy")
    return _icon(ctx, trophy, page, px) if trophy else ""


def _boss_art(ctx: Ctx, boss: dict, page: str, px: int) -> str:
    return _img(ctx.icons.path(boss["pin"]), page, px) if ctx.icons else ""


def _named(ctx: Ctx, prefab: str, page: str, px: int = 24) -> str:
    """A Valheim creature's trophy and name on one line, for table cells."""
    return f'<span class="pov-inline">{_trophy(ctx, prefab, page, px)}{ctx.loc.creature(prefab)}</span>'


def _biome_name(ctx: Ctx, biome: str) -> str:
    return ctx.loc.vkey(f"biome_{biome.lower()}", biome)


def _num(v: float) -> str:
    return f"{v:g}"


def _x(v: float) -> str:
    return f"×{round(v, 2):g}"


def _drops(ctx: Ctx, prefab: str, page: str) -> list[list[str]]:
    """What a boss can drop (LootCatalog.Tables): icon, item, chance, amount, first-kill bonus."""
    from .base_pages import _icon, bases
    from .gear_pages import _link, _pct, _unique_icon, _unique_name, unique_path

    ui, rows, found = ctx.loc.ui, [], bases(ctx)
    for t in ctx.data.loot.get("tables") or []:
        if prefab not in t["creatures"]:
            continue
        total = sum(x["weight"] for x in t["entries"]) or 1
        first = ui("gear.first_drop", n=_num(t["firstDrop"])) if t.get("firstDrop", 1) > 1 else ""
        for e in t["entries"]:
            item, lo, hi = e["id"], e.get("stackMin", 1), e.get("stackMax", 1)
            if item in ctx.loc.gear.get("uniques", {}):
                icon, link = _unique_icon(ctx, item, page, 32), f"[{_unique_name(ctx, item)}]({rel(unique_path(item), page)})"
            else:
                icon, link = _icon(ctx, item, page, 32), _link(ctx, item, page, found)
            rows.append([icon, link, _pct(t["chance"] * e["weight"] / total),
                         f"{lo}–{hi}" if hi > lo else str(lo), first])
    return rows


def _drops_history(ctx: Ctx, prefab: str, page: str) -> list[str]:
    """What patches changed in this boss's drop tables."""
    from .patch_pages import history

    return history(ctx, "drops", [t["id"] for t in ctx.data.loot.get("tables") or [] if prefab in t["creatures"]], page)


def _drops_section(ctx: Ctx, prefab: str, page: str) -> list[str]:
    ui, rows = ctx.loc.ui, _drops(ctx, prefab, page)
    if not rows:
        return []
    header = ["", ui("bosses.item"), ui("gear.chance"), ui("gear.amount"), ""]
    return [f"## {ui('bosses.drops')}", ""] + _table(header, rows)


def page_bosses(ctx: Ctx) -> dict[str, str]:
    b, ui, page = ctx.loc.bosses, ctx.loc.ui, BOSSES_PAGE
    if not b.get("mistMother"):
        return {}
    pages, mine = {}, _mod_bosses(ctx)
    md = [f"# {ui('bosses.title')}", "", ui("bosses.intro"), ""]
    md += [f"## {ui('bosses.mod_bosses')} ({len(mine)})", ""]
    rows = []
    for prefab, boss in mine.items():
        where = boss.get("altar") or b["monolith"]["altar"]
        rows.append([_boss_art(ctx, boss, page, 48), f"**{creature_link(ctx, prefab, page)}**", where,
                     ", ".join(r[1] for r in _drops(ctx, prefab, page))])
    md += _table(["", ui("col.name"), ui("bosses.summoned_at"), ui("bosses.drops")], rows)

    md += [f"## {ui('bosses.vanilla')}", "", ui("bosses.vanilla_intro"), ""]
    biomes = {v["prefab"]: v["biome"] for v in b.get("vanilla", [])}
    # Valheim's bosses in biome order, then those that only have a loot table (Kall).
    order = list(biomes) + sorted(_boss_tables(ctx) - set(biomes) - set(mine))
    rows = []
    for prefab in order:
        anchor = f'<span id="{prefab.lower()}"></span>'
        biome = _biome_name(ctx, biomes[prefab]) if prefab in biomes else "—"
        rows.append([_trophy(ctx, prefab, page, 40), f"{anchor}**{ctx.loc.creature(prefab)}**", biome,
                     ", ".join(r[1] for r in _drops(ctx, prefab, page)) or "—"])
    md += _table(["", ui("col.name"), ui("bosses.biome"), ui("bosses.drops")], rows)
    pages[page] = "\n".join(md + _footer(ctx))

    pages[boss_path(b["mistMother"]["prefab"])] = _mist_mother_page(ctx, b["mistMother"])
    for boss in b["monolith"]["bosses"]:
        pages[boss_path(boss["prefab"])] = _monolith_page(ctx, boss, b["monolith"])
    return pages


def _boss_head(ctx: Ctx, boss: dict, page: str) -> list[str]:
    ui = ctx.loc.ui
    md = [f"# {boss['name']}", ""]
    if art := _boss_art(ctx, boss, page, 96):
        md += [art, ""]
    md += [f"<b>{ui('bosses.kind')}</b> · {ui('bosses.based_on', creature=ctx.loc.creature(boss['source']))}", ""]
    return md


def _quote(text: str, fill: str) -> list[str]:
    """One of the game's own messages, its {0} filled in."""
    return [f"> *{text.replace('{0}', fill)}*", ""] if text else []


def _mist_mother_page(ctx: Ctx, m: dict) -> str:
    ui, page = ctx.loc.ui, boss_path(m["prefab"])
    md = _boss_head(ctx, m, page)
    md += [f"## {ui('bosses.summoning')}", "", ui("bosses.mother_summon", altar=m["altar"]), ""]
    md += _quote(m.get("altarFill", ""), "…")
    hp, dmg = m["health"] * m["wardenHealth"], m["damage"] * m["wardenDamage"]
    md += [f"## {ui('bosses.stats')}", ""]
    md += [ui("bosses.mother_stats", hp=_x(hp), dmg=_x(dmg),
              hp_parts=f"{_num(round(m['health'], 2))} × {_num(m['wardenHealth'])}",
              dmg_parts=f"{_num(round(m['damage'], 2))} × {_num(m['wardenDamage'])}"), ""]
    rows = []
    for biome, anchor in m["anchors"].items():
        if biome == "Ocean":  # not a mist biome
            continue
        base = _vh_creature(ctx, anchor).get("health")
        rows.append([_biome_name(ctx, biome), _named(ctx, anchor, page),
                     _num(base) if base else "—", _num(round(base * hp)) if base else "—"])
    md += _table([ui("bosses.mist_biome"), ui("bosses.anchor"), ui("bosses.anchor_health"), ui("bosses.mother_health")], rows)
    md += [ui("bosses.before_difficulty"), ""]
    md += _drops_section(ctx, m["prefab"], page)
    md += [ui("bosses.see_blight", link=rel(CREATURES_PAGE, page) + "#blight"), ""]
    md += _drops_history(ctx, m["prefab"], page)
    return "\n".join(md + _footer(ctx))


def _monolith_page(ctx: Ctx, boss: dict, shared: dict) -> str:
    from .gear_pages import _link, currency_path

    ui, page, t = ctx.loc.ui, boss_path(boss["prefab"]), shared["tunables"]
    md = _boss_head(ctx, boss, page)
    md += [f"## {ui('bosses.summoning')}", ""]
    visage = _link(ctx, boss["visage"], page, {})
    md += [f"- {ui('bosses.monolith_summon', n=shared['offering'], visage=visage, altar=shared['altar'])}"]
    if blood := ctx.loc.loot["items"].get("PT_RuneOfBloodChallenge"):
        md += [f"- {ui('bosses.blood', rune=f'[{blood['name']}]({rel(currency_path('PT_RuneOfBloodChallenge'), page)})')}"]
    md += [f"- {ui('bosses.altars', n=_num(t['altars-per-biome']), altar=shared['altar'])}", ""]
    md += _quote(shared.get("revealed", ""), "…")

    md += [f"## {ui('bosses.stats')}", ""]
    level = ui("bosses.level_altar") if not boss["level"] else _num(boss["level"])
    md += [f"- {ui('bosses.health', hp=_num(boss['health']), level=boss['native'])}",
           f"- {ui('bosses.damage', x=_x(boss['damage']), creature=ctx.loc.creature(boss['source']))}",
           f"- {ui('bosses.level', level=level)}", ""]

    md += [f"## {ui('bosses.mechanics')}", ""]
    md += _quote(shared.get("stoneText", ""), boss["name"].split(",")[0])
    s = shared["spikes"]
    md += [f"- {ui('bosses.stone', first=_num(t['stone-first']), every=_num(t['stone-every']), lasts=_num(t['stone-seconds']))}",
           f"- {ui('bosses.servants', every=_num(t['call-every']), n=_num(t['call-count']), max=_num(t['call-max']))}",
           f"- {ui('bosses.spikes', first=s['first'], every=s['every'], n=s['count'].get(boss['prefab'], 10), dmg=s['damage'], warn=_num(round(s['warn'], 2)), radius=_num(round(s['radius'], 2)))}",
           f"- {ui('bosses.dome', x=_num(round(t['dome-scale'], 2)))}", ""]
    md += _drops_section(ctx, boss["prefab"], page)
    md += _drops_history(ctx, boss["prefab"], page)
    return "\n".join(md + _footer(ctx))


def page_creatures(ctx: Ctx) -> dict[str, str]:
    b, ui, page = ctx.loc.bosses, ctx.loc.ui, CREATURES_PAGE
    runic = b.get("runic")
    if not runic:
        return {}
    md = [f"# {ui('creatures.title')}", "", ui("creatures.intro"), ""]

    md += [f"## {ui('creatures.runic')} {{ #runic }}", "", ui("creatures.runic_intro"), ""]
    by_id = {k["id"]: k for k in runic["kinds"]}
    base = {s["rank"]: s["source"] for s in runic["base"]}

    def who(entry: str) -> str:
        """A roster entry: a biome kin id, or "kin:<rank>" for the forest's own runic greydwarves."""
        if entry.startswith("kin:"):
            source = base.get(entry.split(":", 1)[1], entry)
        else:
            source = by_id[entry]["sources"][0] if entry in by_id else entry
        return _named(ctx, source, page)

    rows = [[f"**{_biome_name(ctx, biome)}**", *("<br>".join(dict.fromkeys(who(e) for e in roster[slot])) for slot in _SLOTS)]
            for biome, roster in runic["rosters"].items()]
    md += _table([ui("bosses.biome"), *(ui(f"creatures.slot_{s.lower()}") for s in _SLOTS)], rows)

    blight, mother = b["blight"], b["mistMother"]
    md += [f"## {ui('creatures.blight')} {{ #blight }}", ""]
    md += [ui("creatures.blight_intro", hp=_x(mother["health"]), dmg=_x(mother["damage"]),
              mother=f"[{mother['name']}]({rel(boss_path(mother['prefab']), page)})"), ""]
    md += _table(["", ui("creatures.creature"), ui("creatures.in_mist")], [
        [_trophy(ctx, sp, page, 32), ctx.loc.creature(sp), f"**{name}**"] for sp, name in blight["names"].items() if name])
    h = blight["hare"]
    md += [f"### {ui('creatures.blight_hare')}", "", f"{_trophy(ctx, 'Hare', page, 48)}", ""]
    md += [ui("creatures.hare", hare=ctx.loc.creature("Hare"), sight=_num(h["sight"]), burst=_num(round(h["burst"], 2)),
              dmg=_num(h["damage"]), radius=_num(h["radius"]), blunt=round(h["blunt"] * 100),
              poison=round(h["poison"] * 100)), ""]
    return {page: "\n".join(md + _footer(ctx))}


def summons_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """On a visage's (or blood rune's) page: the bosses it calls (or strengthens)."""
    ui, called = ctx.loc.ui, []
    for boss in (ctx.loc.bosses.get("monolith") or {}).get("bosses", []):
        if item == boss["visage"] or item == "PT_RuneOfBloodChallenge":
            called.append(creature_link(ctx, boss["prefab"], page))
    if not called:
        return []
    return [f"## {ui('bosses.summons')}", "", ", ".join(called), ""]


TAMING_PAGE = "monsters/taming.md"
# CraftBeast (Any Beast): which creatures it makes tameable besides the animals (AnimalAI), and the
# taming window: a player with the mastery stamps nearby beasts every 3 s, within 25 m, and their
# taming moves on for 12 s after a stamp.
_BEAST_EXTRA = ("Neck", "Bjorn", "Unbjorn")
_BEAST_RANGE, _BEAST_WINDOW = 25, 12
# Tameable.TamingUpdate: every 3 s a fed, calm creature loses 3 s of taming time; DecreaseRemainingTime
# multiplies it while a player within m_tamingSpeedMultiplierRange has a taming boost (60 m, x2).
_TAME_RANGE, _TAME_BOOST = 60, 2
_HERDER = ("craft-any-beast", "craft-herd-call", "craft-beast-portal", "craft-stable-keeper", "craft-beast-bearer",
           "craft-named-herd")


def _time(ctx: Ctx, seconds: float) -> str:
    ui = ctx.loc.ui
    return ui("taming.minutes", n=_num(seconds / 60)) if seconds >= 60 and seconds % 60 == 0 else ui("taming.seconds", n=_num(seconds))


def _thing(ctx: Ctx, prefab: str, page: str) -> str:
    """An item (icon and name) or a creature (trophy and name), for table cells."""
    from .base_pages import _icon, _item_name

    if prefab in ((ctx.loc.valheim or {}).get("items") or {}):
        return f'<span class="pov-inline">{_icon(ctx, prefab, page, 24)}{_item_name(ctx, prefab)}</span>'
    return _named(ctx, prefab, page)


def page_taming(ctx: Ctx) -> dict[str, str]:
    """Tameable creatures (Valheim's Tameable, MonsterAI foods, Procreation), the ones the Any Beast
    mastery adds (CraftBeast), and the crafting tree's herder masteries."""
    from .formula_pages import _term
    from .markup import to_md

    creatures = (ctx.loc.valheim or {}).get("creatures") or {}
    if not any(c.get("tame") for c in creatures.values()):
        return {}
    ui, page = ctx.loc.ui, TAMING_PAGE
    # Tameable animals: those that also breed (summons arrive tame and don't: the spirit caller's,
    # which carry a copy of their animal's components, are left out by name).
    tame = {p: c for p, c in creatures.items() if c.get("tame") and c.get("breed") and not c["boss"] and "_spiritcaller" not in p}
    items = (ctx.loc.valheim or {}).get("items") or {}
    mead = next((p for p, s in items.items() if s.get("m_consumeStatusEffect") == "Potion_tamer" and not p.startswith("MeadBase")), None)
    md = [f"# {ui('taming.title')}", "", ui("taming.intro", taming=_term(ctx, "taming", page)), "",
          ui("taming.how", range=_TAME_RANGE, mead=_thing(ctx, mead, page) if mead else "", boost=_TAME_BOOST), ""]

    def foods(c: dict) -> str:
        return " ".join(f'<span class="pov-chip">{_thing(ctx, f, page)}</span>' for f in (c.get("ai") or {}).get("foods") or [])

    def notes(t: dict) -> str:
        return "<br>".join(([ui("taming.starts_tame")] if t["startsTamed"] else [])
                           + ([ui("taming.commandable")] if t["commandable"] else []))

    rows = [[_named(ctx, p, page, 32), foods(c), "—" if c["tame"]["startsTamed"] else _time(ctx, c["tame"]["taming"]),
             _time(ctx, c["tame"]["fed"]), _thing(ctx, c["tame"]["saddle"], page) if c["tame"]["saddle"] else "—", notes(c["tame"])]
            for p, c in tame.items()]
    md += _table([ui("creatures.creature"), ui("taming.foods"), ui("taming.taming_time"), ui("taming.fed"), ui("taming.saddle"),
                  ui("taming.notes")], rows)

    md += [f"## {ui('taming.breeding')} {{ #breeding }}", "", ui("taming.breeding_intro"), ""]
    rows = [[_named(ctx, p, page, 32), _thing(ctx, b["offspring"], page) if b["offspring"] else "—",
             ui("taming.check_cell", pct=round((1 - b["chance"]) * 100), every=_time(ctx, b["interval"])), _num(b["love"]),
             _time(ctx, b["duration"]),
             ui("taming.limit_cell", n=b["max"], range=_num(b["range"])), ui("taming.meters", n=_num(b["partner"]))]
            for p, c in tame.items() for b in [c["breed"]]]
    md += _table([ui("creatures.creature"), ui("taming.offspring"), ui("taming.check"), ui("taming.love"), ui("taming.gestation"), ui("taming.limit"), ui("taming.partner")], rows)

    # Any Beast: animals get the boar's foods and taming values; the extras the wolf's values, and
    # its foods when they eat nothing.
    boar, wolf = creatures.get("Boar") or {}, creatures.get("Wolf") or {}
    animals = [p for p, c in creatures.items() if (c.get("ai") or {}).get("kind") == "animal" and not c["boss"]
               and not c.get("tame") and not ctx.loc.creature(p).startswith("$")]
    extras = [p for p in _BEAST_EXTRA if (creatures.get(p) or {}).get("ai") and not creatures[p].get("tame")]
    if boar.get("tame") and wolf.get("tame"):
        md += [f"## {ui('taming.any_beast')} {{ #any-beast }}", "",
               ui("taming.any_beast_intro", mastery=_term(ctx, "craft-any-beast", page, start=True), boar=ctx.loc.creature("Boar"),
                  wolf=ctx.loc.creature("Wolf"), extra=", ".join(ctx.loc.creature(p) for p in extras),
                  range=_BEAST_RANGE, window=_BEAST_WINDOW), ""]
        rows = [[" ".join(f'<span class="pov-chip">{_named(ctx, p, page, 32)}</span>' for p in animals), foods(boar),
                 _time(ctx, boar["tame"]["taming"]), _time(ctx, boar["tame"]["fed"])]] if animals else []
        for p in extras:
            own = (creatures[p].get("ai") or {}).get("foods")
            rows.append([_named(ctx, p, page, 32), foods(creatures[p] if own else wolf),
                         _time(ctx, wolf["tame"]["taming"]), _time(ctx, wolf["tame"]["fed"])])
        md += _table([ui("creatures.creature"), ui("taming.foods"), ui("taming.taming_time"), ui("taming.fed")], rows)

    herder = [k for k in _HERDER if k in ctx.loc.wiki]
    if herder:
        md += [f"## {ui('taming.herder')} {{ #herder }}", "", ui("taming.herder_intro"), ""]
        md += _table([ui("taming.mastery"), ui("taming.effect")],
                     [[_term(ctx, k, page, start=True), " ".join(to_md(line, ctx.loc, page) for line in ctx.loc.wiki[k]["text"])]
                      for k in herder])
    return {page: "\n".join(md + _footer(ctx))}
