"""Weapon type pages: the item bases of a weapon type, with the passives that work with it.

A type is one or more of the mod's weapon kinds (ItemTags: kind.*). Its passives are the tree's
nodes of the type's categories (raw "cat", the same in every language) and the nodes and mastery
options whose stats name the type (mod "subject"). The keyword of the type in the mod's wiki
(Knives, Swords...) is shown on its page: keyword links go there instead of a glossary page.
"""

from collections import Counter, defaultdict

from .item_pages import biome
from .markup import rel, to_md
from .pages import (Ctx, _effect, _footer, _name, _node_table, _option_effect, _option_table, _option_title,
                    _table, plain)

WEAPONS_DIR = "items/weapons"


# (slug, kind tags, tree categories, stat subjects, keyword of the mod's wiki)
WEAPON_TYPES = [
    ("axes", ["kind.Axes"], ["Axes"], ["Axes"], "axe"),
    ("bombs", ["kind.Bombs"], ["Bombs"], ["Bombs"], None),
    ("bows", ["kind.Bows"], ["Bows"], ["Bows"], "bow"),
    ("clubs", ["kind.Clubs"], ["Clubs"], ["Clubs"], "club"),
    ("crossbows", ["kind.Crossbows"], ["Crossbows"], ["Crossbows"], "crossbow"),
    ("fists", ["kind.Unarmed"], ["Fists"], ["Fists"], "fists"),
    ("knives", ["kind.Knives"], ["Knives"], ["Knives"], "knife"),
    ("pickaxes", ["kind.Pickaxes"], ["Pickaxes"], ["Pickaxes"], "pickaxe"),
    ("polearms", ["kind.Polearms"], ["Polearms"], ["Polearms"], "polearm"),
    ("sceptres", ["kind.Scepters"], ["Scepters"], ["Scepters"], None),
    ("spears", ["kind.Spears"], ["Spears"], ["Spears"], "spear"),
    ("staves", ["kind.ElementalMagic", "kind.BloodMagic"], ["Staves", "Magical Weapons", "Blood Magic"],
     ["Staves", "ElementalMagic", "BloodMagic"], "staff"),
    ("swords", ["kind.Swords"], ["Swords"], ["Swords"], "sword"),
]


def weapon_path(slug: str) -> str:
    return f"{WEAPONS_DIR}/{slug}.md"


def weapon_type_of(tags) -> str | None:
    """The weapon type page of an item, by its kind tag."""
    return next((slug for slug, kinds, *_ in WEAPON_TYPES if any(k in tags for k in kinds)), None)


def weapon_terms() -> dict[str, str]:
    """Keyword of the mod's wiki -> its weapon type page (for keyword links)."""
    return {term: weapon_path(slug) for slug, _, _, _, term in WEAPON_TYPES if term}


def _subjects(mods) -> set[str]:
    return {m.get("subject") for m in mods or [] if m.get("subject")}


def _passives(ctx: Ctx, cats: list[str], subjects: list[str]):
    """Keystones, notables, mastery option groups and small-node stat lines of a weapon type."""
    cats, subjects = set(cats), set(subjects)
    nodes: dict[str, list[dict]] = defaultdict(list)
    small: Counter = Counter()
    for n in ctx.tree_nodes:
        if n.get("cat") in cats or _subjects(n.get("mods")) & subjects:
            if n["size"] in ("Keystone", "Notable"):
                nodes[n["size"]].append(n)
            else:
                for line in n["r"]["stats"] + n["r"]["extra"]:
                    small[line] += 1
    groups = [g for g in ctx.option_groups.values()
              if any(n.get("cat") in cats for n in g["nodes"]) or _subjects(g["options"][0]["raw"].get("mods")) & subjects]
    return nodes, groups, small


def _bases_table(ctx: Ctx, prefabs: list[str], found: dict, page: str) -> list[str]:
    from .base_pages import _icon, _level, _material_level, _recipe, _station, _summary, attack_kinds, attacks_cell, base_path

    def order(p: str) -> tuple:  # crafted items in progression order, then the ones only found as loot
        recipe = _recipe(ctx, p)
        return (_material_level(ctx, recipe) if recipe else 10**6), found[p]["name"]

    ui = ctx.loc.ui
    attacks = any(attack_kinds(found[p]) for p in prefabs)  # a column only where some are strikes or slams
    header = ["", ui("col.name"), ui("items.stats"), *([ui("items.attacks")] if attacks else []),
              ui("items.station"), ui("items.item_level")]
    return _table(header, [[
        _icon(ctx, p, page, 40),
        f"[**{found[p]['name']}**]({rel(base_path(p), page)})",
        _summary(ctx, found[p]),
        *([attacks_cell(ctx, found[p], page)] if attacks else []),
        _station(ctx, _recipe(ctx, p)),
        biome(ctx, _level(ctx, p)) if _level(ctx, p) else "—",
    ] for p in sorted(prefabs, key=order)])


def weapon_types(ctx: Ctx, found: dict) -> dict[str, list[str]]:
    """Weapon type slug -> the bases of that type."""
    out: dict[str, list[str]] = defaultdict(list)
    for prefab, b in found.items():
        if "weapon" in b["info"]["tags"] and (slug := weapon_type_of(b["info"]["tags"])):
            out[slug].append(prefab)
    return out


def weapon_title(ctx: Ctx, slug: str) -> str:
    return ctx.loc.ui(f"weapons.{slug}")


def weapons_index(ctx: Ctx, found: dict, page: str) -> list[str]:
    """The weapon types with how many bases each has, for the bases index."""
    ui, types = ctx.loc.ui, weapon_types(ctx, found)
    rows = [[f"[**{weapon_title(ctx, slug)}**]({rel(weapon_path(slug), page)})", str(len(types[slug]))]
            for slug, *_ in WEAPON_TYPES if types.get(slug)]
    return _table([ui("weapons.type"), ui("weapons.count")], rows)


def page_weapons(ctx: Ctx) -> dict[str, str]:
    from .base_pages import BASES_PAGE, bases
    from .pages import glossary_body

    found = bases(ctx)
    if not found:
        return {}
    loc, ui, pages = ctx.loc, ctx.loc.ui, {}
    types = weapon_types(ctx, found)
    for slug, kinds, cats, subjects, term in WEAPON_TYPES:
        if not types.get(slug):
            continue
        page = weapon_path(slug)
        md = [f"# {weapon_title(ctx, slug)}", "", ui("weapons.intro", bases=rel(BASES_PAGE, page)), ""]
        if term and term in loc.wiki:
            md += [to_md(line, loc, page) + "\n" for line in loc.wiki[term]["text"]]

        by_kind = defaultdict(list)
        for p in types[slug]:
            by_kind[next(k for k in kinds if k in found[p]["info"]["tags"])].append(p)
        md += [f"## {ui('weapons.bases')} ({len(types[slug])})", ""]
        for kind in kinds:
            if by_kind.get(kind):
                if len(kinds) > 1:
                    md += [f"### {ui(f'tag.{kind}').capitalize()} ({len(by_kind[kind])})", ""]
                md += _bases_table(ctx, by_kind[kind], found, page)

        nodes, groups, small = _passives(ctx, cats, subjects)
        if nodes or groups or small:
            md += [f"## {ui('weapons.passives')}", "", ui("weapons.passives_intro"), ""]
        for size, label in (("Keystone", "keystones"), ("Notable", "notables")):
            if nodes.get(size):
                md += [f"### {ctx.ui(label)} ({len(nodes[size])})", ""]
                md += _node_table(ctx, page, [loc.ui("col.name"), loc.ui("col.effect")],
                                  sorted(nodes[size], key=lambda n: plain(n["r"]["title"])),
                                  lambda n: [_name(ctx, n, page), _effect(ctx, page, n["r"])])
        if groups:
            md += [f"### {ctx.ui('masteries')} ({len(groups)})", ""]
            md += _option_table(ctx, page, [loc.ui("col.option"), loc.ui("col.effect")],
                                sorted((g["options"][0] for g in groups), key=lambda o: plain(o["title"])),
                                lambda o: [_option_title(ctx, page, o), _option_effect(ctx, page, o)])
        if small:
            md += [f"### {ctx.ui('small_nodes')}", ""]
            md += _table([loc.ui("col.stat"), loc.ui("col.nodes")],
                         [[to_md(line, loc, page), str(c)] for line, c in sorted(small.items(), key=lambda kv: -kv[1])])
        if term and term in loc.wiki:  # what else the keyword is found in: items, other trees
            md += glossary_body(ctx, term, page, definition=False)
        pages[page] = "\n".join(md + _footer(ctx))
    return pages
