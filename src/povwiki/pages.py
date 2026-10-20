"""Generated pages. Each generator returns {docs path: markdown}.

The site has one section per skill tree (TreeSpec): the passive tree and the craft tree. Both
are parsed by the game the same way and get the same kinds of pages (viewer, notables, mastery
options, node pages) under their own URL prefix, since node ids overlap between the trees.

All game text comes from the rendered data (the mod's own tooltip code); all wiki text from
loc.ui(). Content the game ships but has not finished is shown with an "Unimplemented" badge
instead of being hidden (except in the tree viewers, which show the playable tree only).
Jewel-revealed slots are left out entirely: they are empty until a jewel fills them.
"""

import hashlib
import html
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property

from .data import GameData
from .i18n import Localizer
from .icons import DOCS_DIR as ICONS_DIR
from .icons import FRAME_KINDS, Icons, frame_kind
from .markup import glossary_path, plain, rel, slugs, summary, to_html, to_md

# Node types that get a page of their own.
PAGE_SIZES = ("Keystone", "Notable")
# Node types that are part of the tree's structure even without stats.
STRUCTURAL_SIZES = ("Root", "Starter", "Socket", "Portal")


def _hex(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in c)


@dataclass(frozen=True)
class TreeSpec:
    key: str  # URL prefix and ui string section: "passives", "crafting"
    colors: dict[str, str]  # branch -> viewer colour
    default_color: str
    pages: tuple[str, ...]  # which list pages this tree has
    sizes: str = "size"  # ui section naming node types ("Notable", "Crafting notable"...)


PASSIVES = TreeSpec(
    key="passives",
    # The game's branch colours (Tree.cs).
    colors={b: _hex(c) for b, c in {
        "War": (0.91, 0.35, 0.27), "Steel": (0.8, 0.43, 0.61), "Flesh": (0.85, 0.68, 0.32),
        "Wind": (0.34, 0.8, 0.78), "Eitr": (0.68, 0.5, 0.95), "Toil": (0.51, 0.65, 0.87),
    }.items()},
    default_color=_hex((0.96, 0.85, 0.6)),
    pages=("tree", "keystones", "notables", "masteries"),
)
CRAFTING = TreeSpec(
    key="crafting",
    # The game tints the whole craft tree alike; the viewer colours sectors so they stand apart.
    colors={"forge": "#d9764a", "wood": "#7cb35a", "beast": "#c95b5b", "table": "#d9b64a",
            "mead": "#a77fd9", "road": "#4fb3c9"},
    default_color=_hex((0.96, 0.85, 0.6)),
    pages=("tree", "professions", "notables", "masteries"),
    sizes="craft_size",
)


@dataclass
class Ctx:
    data: GameData
    loc: Localizer
    spec: TreeSpec = PASSIVES
    icons: Icons | None = None  # None when icons are turned off
    others: list = field(default_factory=list)  # the other trees' contexts (for the glossary)

    @cached_property
    def raw_tree(self) -> dict:
        return self.data.craft_tree if self.spec is CRAFTING else self.data.tree

    @cached_property
    def rendered(self) -> dict[str, dict]:
        return self.loc.craft["nodes"] if self.spec is CRAFTING else self.loc.nodes

    @cached_property
    def tree_nodes(self) -> list[dict]:
        """Raw tree nodes joined with their rendered text (key "r"). Rendered options get their
        raw data, so everything about an option is in one place. Jewel-revealed slots are left
        out: they have no effect of their own (the jewel provides what appears there)."""
        out = []
        for n in self.raw_tree["nodes"]:
            r = self.rendered.get(n["id"])
            if r is None or _jewel_slot(n):
                continue
            for o, raw in zip(r["options"], n.get("options") or []):
                o["raw"] = raw
            out.append({**n, "r": r})
        return out

    @cached_property
    def option_groups(self) -> dict[tuple, dict]:
        """Distinct mastery options, each with the nodes that offer it. Many nodes offer the same
        option under different ids (e.g. "+5 Strength"). Options are the same when their title
        and stats are, even if their descriptions are worded differently (e.g. Allied
        Adrenaline: same stat, two wordings); text-only options compare by text."""
        groups: dict[tuple, dict] = {}
        for n in self.tree_nodes:
            for o in n["r"]["options"]:
                mods = o["raw"].get("mods") or []
                key = (o["title"], json.dumps(mods, sort_keys=True)) if mods else (o["title"], tuple(o["stats"]), tuple(o["extra"]))
                g = groups.setdefault(key, {"options": [], "nodes": [], "category": n["r"]["category"]})
                g["options"].append(o)
                if n not in g["nodes"]:
                    g["nodes"].append(n)
        for key, g in groups.items():
            ids = sorted(o["id"] for o in g["options"] if o["id"])
            g["slug"] = ids[0] if ids else "x" + hashlib.sha1(repr(key).encode()).hexdigest()[:10]
        return groups

    @cached_property
    def group_of(self) -> dict[int, dict]:
        return {id(o): g for g in self.option_groups.values() for o in g["options"]}

    @cached_property
    def by_id(self) -> dict[str, dict]:
        return {n["id"]: n for n in self.tree_nodes}

    @cached_property
    def neighbours(self) -> dict[str, list[str]]:
        adj = defaultdict(list)
        for a, b in self.raw_tree["links"]:
            adj[a].append(b)
            adj[b].append(a)
        return adj

    @cached_property
    def sector_names(self) -> dict[str, str]:
        return {s["id"]: s["name"] for s in self.loc.craft["sectors"]} if self.spec is CRAFTING else {}

    def ui(self, key: str, **fmt) -> str:
        """A string of this tree's ui section, e.g. ui("notables") -> crafting.notables."""
        return self.loc.ui(f"{self.spec.key}.{key}", **fmt)

    def path(self, name: str) -> str:
        return f"{self.spec.key}/{name}"


def node_path(ctx: Ctx, n: dict) -> str:
    return ctx.path(f"node/{n['id']}.md")


def option_path(ctx: Ctx, group: dict) -> str:
    return ctx.path(f"mastery/{group['slug']}.md")


def _jewel_slot(n: dict) -> bool:
    """A slot a socketed unique jewel fills (e.g. Three Faces of Delusion): JewelReveal only."""
    mods = n.get("mods") or []
    return bool(mods) and all(m["stat"] == "JewelReveal" for m in mods)


# ---- Helpers -----------------------------------------------------------------------------------


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows),
        "",
    ]


def _is_implemented(n: dict) -> bool:
    """A node does something: it has stat lines or options. The rest are placeholders."""
    r = n["r"]
    return bool(r["stats"] or r["extra"] or r["options"])


def _badge(label: str, tip: str) -> str:
    return f'<span class="pov-badge" title="{html.escape(plain(tip), quote=True)}">{label}</span>'


def _badges(ctx: Ctx, r: dict) -> str:
    """Badges for unfinished content. Tooltips use the game's own wording where it has one."""
    loc, out = ctx.loc, []
    if r.get("broken"):
        out.append(_badge(loc.ui("badge.broken"), loc.text("@ui.tree.the-author-has-turned-this", loc.ui("badge.broken_tip"))))
    elif r.get("reserved"):
        out.append(_badge(loc.ui("badge.broken"), loc.text("@ui.tree.reserved-option", loc.ui("badge.reserved_tip"))))
    if r.get("unformatted"):
        out.append(_badge(loc.ui("badge.unformatted"), loc.ui("badge.unformatted_tip", stats=", ".join(r["unformatted"]))))
    return " ".join(out)


def _img(path: str | None, page: str, px: int) -> str:
    # The site generator resolves <img src> relative to the Markdown file, like Markdown links.
    # Explicit width/height: the image keeps its size even before (or without) the stylesheet.
    if not path:
        return ""
    return f'<img class="pov-art" src="{rel(path, page)}" width="{px}" height="{px}" alt="" loading="lazy">'


def _node_art(ctx: Ctx, n: dict, page: str, px: int = 64) -> str:
    """A node's icon in its in-game frame."""
    if not ctx.icons:
        return ""
    return _img(ctx.icons.framed_path(n["r"]["icon"], frame_kind(n["size"], bool(n["r"]["options"]))), page, px)


def _option_art(ctx: Ctx, o: dict, page: str, px: int = 56) -> str:
    if not ctx.icons:
        return ""
    return _img(ctx.icons.framed_path(o["icon"], "mastery"), page, px)


def _node_table(ctx: Ctx, page: str, header: list[str], nodes: list[dict], cells: Callable[[dict], list[str]]) -> list[str]:
    """A table with one row per node, and a leading icon column when icons are on."""
    if not ctx.icons:
        return _table(header, [cells(n) for n in nodes])
    return _table(["", *header], [[_node_art(ctx, n, page), *cells(n)] for n in nodes])


def _option_table(ctx: Ctx, page: str, header: list[str], options: list[dict], cells: Callable[[dict], list[str]]) -> list[str]:
    if not ctx.icons:
        return _table(header, [cells(o) for o in options])
    return _table(["", *header], [[_option_art(ctx, o, page), *cells(o)] for o in options])


def _title(ctx: Ctx, n: dict) -> str:
    title = plain(n["r"]["title"]).strip()
    return title if title and title != n["id"] else ""


def _name(ctx: Ctx, n: dict, page: str | None = None) -> str:
    """Node name in bold, linked to the node's page when it has one and `page` is given."""
    title = _title(ctx, n)
    text = f"**{_cell(title)}**" if title else f"<i>{ctx.loc.ui('page.unnamed')}</i> `{n['id']}`"
    if page and n["size"] in PAGE_SIZES:
        text = f"[{text}]({rel(node_path(ctx, n), page)})"
    return text


def _kind(ctx: Ctx, n: dict) -> str:
    return ctx.loc.ui(f"{ctx.spec.sizes}.{n['size']}")


def _branch(ctx: Ctx, n: dict) -> str:
    """Passive tree: the attribute branch. Craft tree: the sector."""
    if ctx.spec is CRAFTING:
        return ctx.sector_names.get(n["branch"]) or ctx.ui("core")
    return ctx.loc.text(f"@branch.{n['branch']}", n["branch"])


def _lines(ctx: Ctx, page: str, r: dict) -> list[str]:
    lines = [to_md(s, ctx.loc, page) for s in r["stats"]]
    lines += [f"<i>{to_md(s, ctx.loc, page)}</i>" for s in r["extra"]]
    return lines


def _effect(ctx: Ctx, page: str, r: dict) -> str:
    """A node's own effect: stat lines, then extra text in italics. Mastery options are
    listed separately, never mixed into the effect."""
    lines = _lines(ctx, page, r)
    badges = _badges(ctx, r)
    return "<br>".join(lines) + (f"<br>{badges}" if badges else "")


def _option_title(ctx: Ctx, page: str, o: dict) -> str:
    """Option name in bold, linked to the option's page."""
    title = f"**{_cell(plain(o['title']))}**"
    group = ctx.group_of.get(id(o))
    return f"[{title}]({rel(option_path(ctx, group), page)})" if group else title


def _describes_differently(o: dict) -> bool:
    """The game shows an option's numbers in its row and its description on hover; when both
    exist and the description adds something, the wiki shows both. Like the game's tooltip
    (TreeWindow.OptionTitleLink), a description the row text already contains adds nothing."""
    if not (o["stats"] and o["extra"]):
        return False
    row = plain(" ".join(o["stats"])).strip().rstrip(".")
    description = plain(" ".join(o["extra"])).strip().rstrip(".")
    return description not in row


def _option_effect(ctx: Ctx, page: str, o: dict) -> str:
    """An option's effect: its stat lines (the game's option row), then its description in
    italics when that adds something. Options that only grant a mechanic have no stat lines:
    the description is the effect then."""
    lines = [to_md(s, ctx.loc, page) for s in (o["stats"] or o["extra"])]
    if _describes_differently(o):
        lines += [f"<i>{to_md(s, ctx.loc, page)}</i>" for s in o["extra"]]
    badges = _badges(ctx, o)
    return "<br>".join(lines) + (f"<br>{badges}" if badges else "")


def _category_key(cat: str | None) -> str:
    """The game spells some categories in two cases ("Armour" / "armour"): group them as one."""
    return (cat or "").strip().lower()


def _category_titles(cats) -> dict[str, str]:
    """Group key -> display title, preferring a capitalised spelling."""
    titles: dict[str, str] = {}
    for cat in cats:
        cat = (cat or "").strip()
        key = _category_key(cat)
        if key not in titles or (cat[:1].isupper() and not titles[key][:1].isupper()):
            titles[key] = cat
    return titles


def _tree_link(ctx: Ctx, n: dict, page: str) -> str:
    """"Show on tree" link. The #node anchor only exists in the viewer's script, so the link must
    not point at tree.md: the site generator would check the anchor and warn, once per node. It
    points at the tree's directory URL instead, written relative to the .md file (the generator
    rewrites hrefs in raw HTML that way too)."""
    return f'<a href="{rel(ctx.path("tree"), page)}/#{n["id"]}">{ctx.loc.ui("tree.show")}</a>'


def _footer(ctx: Ctx) -> list[str]:
    meta = ctx.data.meta
    return ["", f"<small>{ctx.loc.ui('page.data_version', version=meta['version'], date=meta['extracted'][:10])}</small>", ""]


def _unimplemented_section(ctx: Ctx, nodes: list[dict], page: str) -> list[str]:
    if not nodes:
        return []
    loc = ctx.loc
    table = _node_table(
        ctx, page, [loc.ui("col.name"), ctx.ui("branch"), loc.ui("col.category")],
        sorted(nodes, key=lambda n: (n["branch"], n["id"])),
        lambda n: [_name(ctx, n, page), _branch(ctx, n), n["r"]["category"] or ""],
    )
    return [
        f"## {loc.ui('page.unimplemented')} ({len(nodes)})",
        "",
        f'??? note "{loc.ui("page.unimplemented_note")}"',
        "",
        *("    " + line for line in table),
    ]


# ---- List pages --------------------------------------------------------------------------------


def page_keystones(ctx: Ctx) -> dict[str, str]:
    page, loc = ctx.path("keystones.md"), ctx.loc
    nodes = [n for n in ctx.tree_nodes if n["size"] == "Keystone"]
    live = sorted((n for n in nodes if _is_implemented(n)), key=lambda n: n["r"]["title"])
    md = [f"# {ctx.ui('keystones')}", ""]
    md += _node_table(
        ctx, page, [loc.ui("col.name"), ctx.ui("branch"), loc.ui("col.category"), loc.ui("col.effect")], live,
        lambda n: [_name(ctx, n, page), _branch(ctx, n), n["r"]["category"] or "", _effect(ctx, page, n["r"])],
    )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)], page)
    return {page: "\n".join(md + _footer(ctx))}


def page_notables(ctx: Ctx) -> dict[str, str]:
    """Notables grouped by category (craft tree: by profession). Their mastery options are on
    the Masteries page."""
    page, loc = ctx.path("notables.md"), ctx.loc
    nodes = [n for n in ctx.tree_nodes if n["size"] == "Notable"]
    by_cat = defaultdict(list)
    for n in nodes:
        if _is_implemented(n):
            by_cat[_category_key(n["r"]["category"])].append(n)
    titles = _category_titles(n["r"]["category"] for n in nodes)
    md = [f"# {ctx.ui('notables')}", "", ctx.ui("notables_intro", count=sum(map(len, by_cat.values()))), ""]
    for cat in sorted(by_cat, key=lambda c: (c == "", c)):
        md += [f"## {titles.get(cat) or loc.ui('page.uncategorized')}", ""]
        md += _node_table(
            ctx, page, [loc.ui("col.name"), ctx.ui("branch"), loc.ui("col.effect")],
            sorted(by_cat[cat], key=lambda n: n["r"]["title"]),
            lambda n: [_name(ctx, n, page), _branch(ctx, n), _effect(ctx, page, n["r"])],
        )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)], page)
    return {page: "\n".join(md + _footer(ctx))}


def page_masteries(ctx: Ctx) -> dict[str, str]:
    """Choice nodes, by category: each distinct option once, with how many nodes offer it."""
    page, loc = ctx.path("masteries.md"), ctx.loc
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for g in ctx.option_groups.values():
        if any(n["size"] != "Keystone" for n in g["nodes"]):
            by_cat[_category_key(g["category"])].append(g)
    titles = _category_titles(g["category"] for g in ctx.option_groups.values())
    md = [f"# {ctx.ui('masteries')}", "", loc.ui("page.masteries_intro"), ""]
    for cat in sorted(by_cat, key=lambda c: (c == "", c)):
        groups = sorted(by_cat[cat], key=lambda g: plain(g["options"][0]["title"]))
        count = {id(g["options"][0]): len(g["nodes"]) for g in groups}
        md += [f"## {titles.get(cat) or loc.ui('page.uncategorized')}", ""]
        md += _option_table(
            ctx, page, [loc.ui("col.option"), loc.ui("col.effect"), loc.ui("col.offered_by")],
            [g["options"][0] for g in groups],
            lambda o: [_option_title(ctx, page, o), _option_effect(ctx, page, o), str(count[id(o)])],
        )
    return {page: "\n".join(md + _footer(ctx))}


def profession_path(ctx: Ctx, prof: str) -> str:
    return ctx.path(f"profession/{prof}.md")


def _profession_icon(ctx: Ctx, prof: str, page: str, px: int) -> str:
    """The profession's badge art (craftbadge.icon-<profession>), when icons are on."""
    if not ctx.icons:
        return ""
    return _img(ctx.icons.path(f"PassiveTree.craftbadge.icon-{prof}.png"), page, px)


def _boss_gate(ctx: Ctx, boss: int) -> str:
    return ctx.ui("boss_gate", boss=ctx.loc.ui(f"boss.{boss}")) if boss > 0 else ""


def _quest_families(ctx: Ctx, prof: str) -> list[list[dict]]:
    """The profession's composed quest families (the ones the game offers), first offered first."""
    by_template = defaultdict(list)
    for t in ctx.loc.craft["quests"]["tasks"]:
        if t["profession"] == prof and t["template"] and t["issuable"]:
            by_template[t["template"]].append(t)
    first = lambda t: next((i for i, s in enumerate(t["stages"]) if s["offered"]), 99)  # noqa: E731
    return sorted((sorted(v, key=lambda t: (first(t), t["conditions"], t["target"], t["facts"])) for v in by_template.values()),
                  key=lambda fam: (min(first(t) for t in fam), fam[0]["action"]))


def page_professions(ctx: Ctx) -> dict[str, str]:
    """Craft tree: an overview of sectors and professions, and a page per profession with its
    stages, notables and quests."""
    page, loc = ctx.path("professions.md"), ctx.loc
    quests = loc.craft["quests"]
    notables = [n for n in ctx.tree_nodes if n["size"] == "Notable" and _is_implemented(n)]
    # A notable's profession is its shelf line (TreeWindow.CraftShelf): its own profession, or
    # the one its cluster (chunk) belongs to. That line is the node's category.
    by_shelf = defaultdict(list)
    for n in notables:
        by_shelf[n["r"]["category"]].append(n)
    unavailable = loc.text("@ui.crafttree.profession-not-available", "This profession is not available in the game yet.")
    pages = {}

    md = [f"# {ctx.ui('professions')}", "", ctx.ui("professions_intro"), ""]
    for sector in loc.craft["sectors"]:
        md += [f"## {sector['name']}", ""]
        rows = []
        for prof in sector["profs"]:
            info = quests["professions"].get(prof["id"], {"areas": [], "unavailable": False})
            link = f"[**{prof['name']}**]({rel(profession_path(ctx, prof['id']), page)})"
            if info["unavailable"]:
                link += " " + _badge(loc.ui("badge.broken"), unavailable)
            rows.append([
                _profession_icon(ctx, prof["id"], page, 48), link, str(len(info["areas"])),
                str(len(by_shelf.get(prof["name"], []))), str(len(_quest_families(ctx, prof["id"]))),
            ])
        md += _table(["", ctx.ui("profession"), ctx.ui("stages"), ctx.ui("notables"), ctx.ui("quest_families")], rows)
    pages[page] = "\n".join(md + _footer(ctx))

    for sector in loc.craft["sectors"]:
        for prof in sector["profs"]:
            pages.update(_profession_page(ctx, sector, prof, by_shelf.get(prof["name"], []), unavailable))
    return pages


def _profession_page(ctx: Ctx, sector: dict, prof: dict, notables: list[dict], unavailable: str) -> dict[str, str]:
    loc, page = ctx.loc, profession_path(ctx, prof["id"])
    info = ctx.loc.craft["quests"]["professions"].get(prof["id"], {"areas": [], "unavailable": False})
    levels = len(info["areas"]) + 1  # quests scale with areas revealed: 0 .. all
    art = _profession_icon(ctx, prof["id"], page, 96)
    md = [f"# {prof['name']}", ""]
    md += [(f'<span class="pov-art-lg">{art}</span>' if art else "") + f"<b>{ctx.ui('profession')}</b> · {sector['name']}", ""]
    if info["unavailable"]:
        md += [f'!!! warning "{loc.ui("page.unimplemented")}"', f"    {unavailable}", ""]

    # Stages.
    if info["areas"]:
        md += [f"## {ctx.ui('stages')}", "", ctx.ui("stages_intro"), ""]
        md += _table(
            [ctx.ui("craft_xp"), ctx.ui("tier"), ctx.ui("area"), ctx.ui("lore")],
            [[f"{a['xp']:,}", str(a["tier"]), str(a["number"]),
              (f"<i>{to_md(a['lore'], loc, page)}</i>" if a["lore"] else "")
              + (" " + _badge(loc.ui("badge.broken"), loc.ui("badge.reserved_tip")) if a["reserved"] else "")]
             for a in sorted(info["areas"], key=lambda a: (a["xp"], a["number"]))],
        )

    # Notables.
    if notables:
        md += [f"## {ctx.ui('notables')}", ""]
        md += _node_table(ctx, page, [loc.ui("col.name"), loc.ui("col.effect")], sorted(notables, key=lambda n: n["r"]["title"]),
                          lambda n: [_name(ctx, n, page), _effect(ctx, page, n["r"])])

    # Quests.
    families = _quest_families(ctx, prof["id"])
    if families:
        md += [f"## {ctx.ui('quests')}", "", ctx.ui("quests_intro"), ""]
        stage_cols = [ctx.ui("revealed_n", n=i) for i in range(levels)]
        for fam in families:
            lead = fam[0]
            first = min(next((i for i, s in enumerate(t["stages"]) if s["offered"]), 99) for t in fam)
            boss = min(t["boss"] for t in fam)
            meta = [ctx.ui("offered_from", n=first) if first else ctx.ui("offered_start")] + ([_boss_gate(ctx, boss)] if boss else [])
            md += [f"### {plain(lead['action'])}", "", " · ".join(meta), ""]
            md += _table([ctx.ui("reward_by_stage"), *stage_cols],  # by areas revealed
                         [["", *(f"{s['reward']:,}" for s in lead["stages"])]])
            life = loc.text("@craft.composer.condition.life", "in one life (death resets progress)")
            rows = []
            for t in fam:
                conditions = [*t["facts"], *([life] if "death" in t["resets"] else [])]
                rows.append([
                    ", ".join(conditions) or ctx.ui("none"),
                    t["target"] or ctx.ui("any"),
                    *(f"{s['count']:,}" if s["offered"] else ctx.ui("none") for s in t["stages"]),
                ])
            unit = lead["shown"].split(" · ")[1].split(" ", 1)[1] if " · " in lead["shown"] else ""
            md += [f'??? note "{ctx.ui("variants", count=len(fam))}"', ""]
            md += ["    " + line for line in _table(
                [ctx.ui("conditions"), ctx.ui("target"), *(f"{c} ({unit})" if unit else c for c in stage_cols)], rows)]

    # Tasks in the files that the quest system never offers.
    dead = [t for t in ctx.loc.craft["quests"]["tasks"] if t["profession"] == prof["id"] and not t["template"]]
    if dead:
        md += [f"## {ctx.ui('not_offered')} ({len(dead)})", "", f'??? note "{ctx.ui("not_offered_note")}"', ""]
        md += ["    " + line for line in _table(
            [ctx.ui("task"), ""],
            [[to_md(t["text"], loc, page), _badge(loc.ui("badge.broken"), ctx.ui("not_offered_note"))
              + (f" `{ctx.ui('removed')}`" if t["removed"] else "")] for t in dead],
        )]
    return {page: "\n".join(md + _footer(ctx))}


def page_options(ctx: Ctx) -> dict[str, str]:
    """One page per distinct mastery option: effect, description, the nodes that offer it."""
    loc, pages = ctx.loc, {}
    for g in ctx.option_groups.values():
        o, page = g["options"][0], option_path(ctx, g)
        md = [f"# {plain(o['title'])}", ""]
        art = _option_art(ctx, o, page, 128)
        meta = [f"<b>{ctx.ui('mastery_option')}</b>"] + ([g["category"]] if g["category"] else [])
        md += [(f'<span class="pov-art-lg">{art}</span>' if art else "") + " · ".join(meta), ""]
        if o.get("reserved") or o.get("broken"):
            md += [f'!!! warning "{loc.ui("page.unimplemented")}"', f"    {_badges(ctx, o)}", ""]

        if o["stats"]:
            md += [f"## {loc.ui('page.effect')}", "", '<div class="pov-tooltip" markdown>', "",
                   "<br>".join(to_md(x, loc, page) for x in o["stats"]), "", "</div>", ""]
        wordings = list(dict.fromkeys(tuple(x["extra"]) for x in g["options"] if x["extra"]))
        if wordings and (not o["stats"] or _describes_differently(o) or len(wordings) > 1):
            md += [f"## {loc.ui('page.description')}", "", loc.ui("page.description_note"), ""]
            if len(wordings) > 1:
                md += [loc.ui("page.description_variants", count=len(wordings)), ""]
            for extra in wordings:
                md += ['<div class="pov-tooltip" markdown>', "", "<br>".join(to_md(x, loc, page) for x in extra), "", "</div>", ""]

        from .building_pages import building_link, building_of_flag

        built = building_of_flag(ctx)
        if unlocked := [built[f] for f in dict.fromkeys(x.get("flag") for x in g["options"]) if f in built]:
            md += [f"## {loc.ui('buildings.unlocks')}", "", ", ".join(building_link(ctx, b, page) for b in unlocked), ""]

        md += [f"## {loc.ui('page.offered_by')} ({len(g['nodes'])})", ""]
        md += _node_table(
            ctx, page, [loc.ui("col.name"), loc.ui("col.type"), ctx.ui("branch"), ""], g["nodes"],
            lambda n: [_name(ctx, n, page), _kind(ctx, n), _branch(ctx, n), _tree_link(ctx, n, page)],
        )
        md += [f'??? abstract "{loc.ui("page.game_data")}"', "", "    ```json"]
        md += ["    " + line for line in json.dumps(o["raw"], ensure_ascii=False, indent=2).splitlines()]
        md += ["    ```", ""]
        if len(g["options"]) > 1:
            ids = ", ".join(f"`{x['id']}`" for x in g["options"])
            md += [f"<small>{loc.ui('page.option_ids')}: {ids}</small>", ""]
        pages[page] = "\n".join(md + _footer(ctx))
    return pages


def page_nodes(ctx: Ctx) -> dict[str, str]:
    """One page per keystone and notable, placeholders included (marked unimplemented)."""
    loc, pages = ctx.loc, {}
    for n in ctx.tree_nodes:
        if n["size"] not in PAGE_SIZES:
            continue
        page, r = node_path(ctx, n), n["r"]
        kind = _kind(ctx, n)
        md = [f"# {_title(ctx, n) or loc.ui('page.unnamed')}", ""]
        if not _is_implemented(n):
            md += ["!!! warning \"" + loc.ui("page.unimplemented") + "\"", f"    {loc.ui('page.unimplemented_node')}", ""]
        art = _node_art(ctx, n, page, 128)
        md += [
            (f'<span class="pov-art-lg">{art}</span>' if art else "")
            + f"<b>{kind}</b> · {_branch(ctx, n)}" + (f" · {r['category']}" if r["category"] else "")
            + f" · {_tree_link(ctx, n, page)}",
            "",
        ]

        effect = _effect(ctx, page, r)
        if effect:
            md += ['<div class="pov-tooltip" markdown>', "", effect, "", "</div>", ""]

        # Mastery options, apart from the node's own effect.
        if r["options"]:
            md += [f"## {loc.ui('page.mastery_options')}", ""]
            md += _option_table(
                ctx, page, [loc.ui("col.option"), loc.ui("col.effect")], r["options"],
                lambda o: [_option_title(ctx, page, o), _option_effect(ctx, page, o)],
            )

        # Details.
        info = [
            [loc.ui("col.type"), kind],
            [ctx.ui("branch"), _branch(ctx, n)],
            [loc.ui("col.category"), r["category"] or "—"],
            [loc.ui("col.topics"), ", ".join(dict.fromkeys(t for t in r["topics"] if t)) or "—"],
            [loc.ui("col.position"), f"{n['x']:g}, {n['y']:g}"],
            [loc.ui("col.id"), f"`{n['id']}`"],
        ]
        md += [f"## {loc.ui('page.details')}", ""] + _table([loc.ui("col.property"), loc.ui("col.value")], info)

        # Connections.
        near = [ctx.by_id[x] for x in ctx.neighbours.get(n["id"], []) if x in ctx.by_id]
        if near:
            md += [f"## {loc.ui('page.connections')}", ""]
            md += _node_table(
                ctx, page, [loc.ui("col.name"), loc.ui("col.type"), loc.ui("col.effect")], near,
                lambda m: [_name(ctx, m, page), _kind(ctx, m), _effect(ctx, page, m["r"])],
            )

        # Keywords.
        keys = dict.fromkeys(
            s for line in r["stats"] + r["extra"] + [x for o in r["options"] for x in o["stats"] + o["extra"]]
            for s in slugs(line) if s in loc.wiki
        )
        if keys:
            md += [f"## {loc.ui('page.keywords')}", ""]
            md += [f"- [{plain(loc.wiki[k]['title'])}]({rel(glossary_path(k), page)}): {_cell(summary(loc.wiki[k], 160))}" for k in keys]
            md.append("")

        # Raw game data, poedb style.
        raw = {k: n[k] for k in ("mods", "options", "masteryId", "icon", "prof", "sector") if n.get(k)}
        if raw:
            md += [f'??? abstract "{loc.ui("page.game_data")}"', "", "    ```json"]
            md += ["    " + line for line in json.dumps(raw, ensure_ascii=False, indent=2).splitlines()]
            md += ["    ```", ""]
        pages[page] = "\n".join(md + _footer(ctx))
    return pages


# ---- Tree viewer -------------------------------------------------------------------------------

# Order matters: the viewer refers to sizes and branches by index.
SIZES = ["Small", "Travel", "Notable", "Keystone", "Socket", "Mastery", "Starter", "Portal", "Root"]
# The game's node diameters (TreeStyle.Size).
DIAMETERS = {"Keystone": 58, "Notable": 43.84, "Starter": 43.84, "Portal": 76, "Mastery": 50, "Socket": 50,
             "Small": 30, "Travel": 30, "Root": 64}


def _tooltip_html(ctx: Ctx, n: dict) -> str:
    r, loc = n["r"], ctx.loc
    body = [f'<div class="pov-tt-line">{to_html(s)}</div>' for s in r["stats"]]
    body += [f'<div class="pov-tt-extra">{to_html(s)}</div>' for s in r["extra"]]
    if r["options"]:
        body.append(f'<div class="pov-tt-head">{html.escape(loc.ui("page.mastery_options"))}</div>')
        for o in r["options"]:
            lines = o["stats"] or o["extra"]
            text = "; ".join(to_html(s) for s in lines)
            mark = f' <span class="pov-badge">{html.escape(loc.ui("badge.broken"))}</span>' if o.get("reserved") or o.get("broken") else ""
            body.append(f'<div class="pov-tt-opt"><b>{to_html(o["title"])}</b>' + (f": {text}" if text else "") + f"{mark}</div>")
    if not _is_implemented(n):
        body.append(f'<div class="pov-tt-head"><span class="pov-badge">{html.escape(loc.ui("page.unimplemented"))}</span></div>')
    elif r.get("unformatted"):
        body.append(f'<div class="pov-tt-head"><span class="pov-badge">{html.escape(loc.ui("badge.unformatted"))}</span></div>')
    return "".join(body)


def page_tree(ctx: Ctx) -> dict[str, str]:
    """The interactive tree: a page with the viewer, and its data."""
    loc, tree = ctx.loc, ctx.raw_tree
    page, data_path = ctx.path("tree.md"), ctx.path("tree-data.json")
    hidden = set(tree.get("hiddenLinks") or [])
    curves = tree.get("linkCurve") or {}
    branches = sorted({n["branch"] for n in ctx.tree_nodes})

    nodes = []
    # Placeholders are left out. Starters, sockets, portals and the root have no stats of their
    # own but are part of the playable tree.
    shown = [n for n in ctx.tree_nodes if _is_implemented(n) or n["size"] in STRUCTURAL_SIZES]
    index = {n["id"]: i for i, n in enumerate(shown)}
    for n in shown:
        flags = (1 if n["size"] in PAGE_SIZES else 0) | (4 if n["r"]["options"] else 0)
        nodes.append([
            n["id"], n["x"], n["y"], SIZES.index(n["size"]) if n["size"] in SIZES else 0, branches.index(n["branch"]),
            _title(ctx, n), _tooltip_html(ctx, n), flags,
            (ctx.icons.path(n["r"]["icon"]) or "").removeprefix(f"{ICONS_DIR}/") if ctx.icons else "",
            FRAME_KINDS.index(frame_kind(n["size"], bool(n["r"]["options"]))),
        ])
    links = []
    for a, b in tree["links"]:
        key = f"{min(a, b)}|{max(a, b)}"  # Tree.LinkKey: ordinal order
        if key in hidden or a not in index or b not in index:
            continue
        c = curves.get(key)
        links.append([index[a], index[b], *c] if c else [index[a], index[b]])

    data = {
        "nodes": nodes,
        "links": links,
        "sizes": [{"name": loc.ui(f"{ctx.spec.sizes}.{s}"), "d": DIAMETERS.get(s, 30)} for s in SIZES],
        "branches": [
            {"name": _branch(ctx, {"branch": b}), "color": ctx.spec.colors.get(b, ctx.spec.default_color)} for b in branches
        ],
        "ui": {k: loc.ui(f"tree.{k}") for k in ("search", "matches", "reset", "hint")},
        # Relative to the page's rendered URL (<tree>/tree/), like the attributes below.
        "iconBase": f"../{rel(ICONS_DIR, page)}/" if ctx.icons else "",
        # The game's painted frames: iconBase + "frame/<kind>-<locked|allocated>.webp".
        "frames": list(FRAME_KINDS) if ctx.icons else [],
    }
    md = [
        "---",
        "hide:",
        "  - navigation",
        "  - toc",
        "---",
        "",
        f"# {ctx.ui('tree')}",
        "",
        # URLs relative to the page's rendered URL, <tree>/tree/ (directory URLs), hence the
        # extra "../". (Not "data-src": the site generator rewrites *src attributes as file paths.)
        f'<div class="pov-tree" data-tree="../{rel(data_path, page)}" '
        f'data-node-base="../{rel(ctx.path("node"), page)}/"></div>',
        "",
        ctx.ui("tree_help"),
        *_footer(ctx),
    ]
    return {page: "\n".join(md), data_path: json.dumps(data, ensure_ascii=False, separators=(",", ":"))}


# ---- Glossary ----------------------------------------------------------------------------------


def _references(ctx: Ctx) -> dict[str, dict]:
    """slug -> where this tree's game text links it: notables/keystones, options, small nodes."""
    refs: dict[str, dict] = defaultdict(lambda: {"Keystone": [], "Notable": [], "options": [], "small": Counter()})
    for n in ctx.tree_nodes:
        r = n["r"]
        own = [s for line in r["stats"] + r["extra"] for s in slugs(line)]
        for slug in set(own):
            if n["size"] in PAGE_SIZES:
                refs[slug][n["size"]].append(n)
            else:
                for line in r["stats"] + r["extra"]:
                    if slug in slugs(line):
                        refs[slug]["small"][line] += 1
        for o in r["options"]:
            for slug in {s for line in o["stats"] + o["extra"] for s in slugs(line)}:
                refs[slug]["options"].append(o)
    return refs


def _references_section(ctx: Ctx, ref: dict, page: str) -> list[str]:
    loc, md = ctx.loc, []
    for size, label in (("Keystone", "keystones"), ("Notable", "notables")):
        if ref[size]:
            md += [f"### {ctx.ui(label)}", ""]
            md += _node_table(
                ctx, page, [loc.ui("col.name"), loc.ui("col.effect")], sorted(ref[size], key=lambda n: n["r"]["title"]),
                lambda n: [_name(ctx, n, page), _effect(ctx, page, n["r"])],
            )
    if ref["options"]:
        distinct = {(o["title"], tuple(o["stats"])): o for o in ref["options"]}
        md += [f"### {ctx.ui('masteries')}", ""]
        md += _option_table(
            ctx, page, [loc.ui("col.option"), loc.ui("col.effect")], sorted(distinct.values(), key=lambda o: plain(o["title"])),
            lambda o: [_option_title(ctx, page, o), _option_effect(ctx, page, o)],
        )
    if ref["small"]:
        md += [f"### {ctx.ui('small_nodes')}", ""]
        md += _table(
            [loc.ui("col.stat"), loc.ui("col.nodes")],
            [[to_md(line, loc, page), str(c)] for line, c in sorted(ref["small"].items(), key=lambda kv: -kv[1])],
        )
    return md


def _related_pages(ctx: Ctx) -> dict[str, list[tuple[str, str, str]]]:
    """Wiki terms -> pages of this site about the same thing (title, path, what it is), for "See also"."""
    from .building_pages import WILD, building_path, display_name
    from .monster_pages import MODS_PAGE

    found: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    by_id = {b["id"]: b for b in ctx.loc.buildings}
    links = {"craft-wild-sowing": [WILD], "craft-cuttings": [WILD], "azurite": ["PT_AzuriteKiln"]}
    for term, ids in links.items():
        found[term] += [(display_name(ctx, by_id[i]), building_path(i), ctx.loc.ui("buildings.kind"))
                        for i in ids if i in by_id]
    from .monster_pages import BOSSES_PAGE, CREATURES_PAGE

    if ctx.loc.bosses.get("mistMother"):
        found["boss"].append((ctx.loc.ui("bosses.title"), BOSSES_PAGE, ctx.loc.ui("monsters.title")))
        found["rune-monolith"].append((ctx.loc.ui("creatures.runic"), CREATURES_PAGE + "#runic", ctx.loc.ui("monsters.title")))
    if ctx.loc.monsters.get("mods"):
        for term in ("item-quantity", "item-rarity"):
            found[term].append((ctx.loc.ui("monsters.mods"), MODS_PAGE, ctx.loc.ui("monsters.title")))
    return found


def page_glossary(ctx: Ctx) -> dict[str, str]:
    """A page per term of the mod's in-game wiki, with what references it in every tree."""
    from .formula_pages import term_formulas
    from .gear_pages import keyword_uniques_section, uniques_by_keyword
    from .item_pages import keyword_mods_section, mods_by_keyword

    loc, wiki = ctx.loc, ctx.loc.wiki
    trees = [ctx, *ctx.others]
    refs = {t.spec.key: _references(t) for t in trees}
    mods, uniques = mods_by_keyword(ctx), uniques_by_keyword(ctx)  # item text links keywords too
    related = _related_pages(ctx)
    terms = defaultdict(set)
    for key, term in wiki.items():
        for slug in {s for line in term["text"] for s in slugs(line)}:
            if slug != key:
                terms[slug].add(key)

    pages = {}
    for key in sorted(wiki, key=lambda k: plain(wiki[k]["title"]).lower()):
        page, term = glossary_path(key), wiki[key]
        md = [f"# {plain(term['title'])}", ""]
        md += [to_md(line, loc, page) + "\n" for line in term["text"]] or [f"*{loc.ui('page.no_text')}*", ""]
        md += term_formulas(ctx, key, page)  # the keyword's formulas, right under its definition
        sections = [(t, refs[t.spec.key][key]) for t in trees if key in refs[t.spec.key]]
        if sections or terms.get(key) or mods.get(key) or uniques.get(key):
            md += [f"## {loc.ui('page.referenced_by')}", ""]
        for t, ref in sections:
            body = _references_section(t, ref, page)
            if body:
                # One heading per tree, so passive and craft references are told apart.
                md += [f"### {t.ui('title')}", ""] + [line.replace("### ", "#### ", 1) if line.startswith("### ") else line for line in body]
        if mods.get(key) or uniques.get(key):
            md += [f"### {loc.ui('items.title')}", ""]
            if mods.get(key):
                md += keyword_mods_section(ctx, mods[key], page)
            if uniques.get(key):
                md += keyword_uniques_section(ctx, uniques[key], page)
        if terms.get(key) or related.get(key):
            md += [f"### {loc.ui('page.see_also')}", ""]
            md += [f"- [{title}]({rel(target, page)}) <small>{kind}</small>" for title, target, kind in related.get(key, [])]
            md += [
                f"- [{plain(wiki[k]['title'])}]({rel(glossary_path(k), page)})"
                for k in sorted(terms.get(key, ()), key=lambda k: plain(wiki[k]["title"]).lower())
            ]
        pages[page] = "\n".join(md + _footer(ctx))
    return pages


# Generators per tree, by the page names a TreeSpec lists; the rest run for every tree.
LIST_PAGES = {
    "tree": page_tree, "keystones": page_keystones, "notables": page_notables,
    "masteries": page_masteries, "professions": page_professions,
}
PER_TREE = [page_options, page_nodes]
# Run once, with the first tree's context (and the others in ctx.others).
GLOBAL = [page_glossary]
TREES = [PASSIVES, CRAFTING]


def nav() -> list:
    """Navigation: (ui title key, page path | children). Titles are translated per language.
    Glossary term pages are reached from keyword links and search."""
    from .gear_pages import _GROUPS, group_path

    return [
        ("nav.home", "index.md"),
        *((f"{t.key}.title", [(f"{t.key}.{p}", f"{t.key}/{p}.md") for p in t.pages]
           + ([("buildings.title", "crafting/buildings.md")] if t is CRAFTING else [])) for t in TREES),
        ("items.title", [("items.mods", "items/mods.md"), ("items.bases", "items/bases.md"),
                         ("gear.currency", [("gear.currency_all", "items/currency.md"),
                                            *((f"gear.group.{g}", group_path(g)) for g in _GROUPS)]),
                         ("gear.jewels", "items/jewels.md"),
                         ("gear.uniques", "items/uniques.md")]),
        ("monsters.title", [("monsters.mods", "monsters/mods.md"), ("bosses.title", "monsters/bosses.md"),
                            ("creatures.title", "monsters/creatures.md")]),
        ("formula.title", [("formula.creatures", "mechanics/creatures.md"), ("formula.loot_page", "mechanics/loot.md"),
                           ("formula.combat", "mechanics/combat.md")]),
        ("nav.about", "about.md"),
    ]
