"""Generated pages. Each generator returns {docs path: markdown}.

All game text comes from the rendered data (the mod's own tooltip code); all wiki text from
loc.ui(). Content the game ships but has not finished is shown with an "Unimplemented" badge
instead of being hidden.
"""

import html
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from .data import GameData
from .i18n import Localizer
from .icons import DOCS_DIR as ICONS_DIR
from .icons import Icons
from .markup import glossary_path, plain, rel, slugs, summary, to_html, to_md


@dataclass
class Ctx:
    data: GameData
    loc: Localizer
    icons: Icons | None = None  # None when icons are turned off

    @cached_property
    def tree_nodes(self) -> list[dict]:
        """Raw tree nodes joined with their rendered text (key "r"). Rendered options get their
        raw icon id, so everything shown about an option is in one place."""
        out = []
        for n in self.data.tree["nodes"]:
            r = self.loc.nodes.get(n["id"])
            if r is None:
                continue
            for o, raw in zip(r["options"], n.get("options") or []):
                o["icon"] = raw.get("icon")
            out.append({**n, "r": r})
        return out

    @cached_property
    def by_id(self) -> dict[str, dict]:
        return {n["id"]: n for n in self.tree_nodes}

    @cached_property
    def neighbours(self) -> dict[str, list[str]]:
        adj = defaultdict(list)
        for a, b in self.data.tree["links"]:
            adj[a].append(b)
            adj[b].append(a)
        return adj


# Node types that get a page of their own.
PAGE_SIZES = ("Keystone", "Notable")


def node_path(n: dict) -> str:
    return f"passives/node/{n['id']}.md"


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


def _icon(ctx: Ctx, key: str | None, page: str, cls: str = "pov-icon") -> str:
    """<img> for a game icon id, sized by CSS class; "" when there is none or icons are off."""
    path = ctx.icons.path(key) if ctx.icons else None
    # The site generator resolves <img src> relative to the Markdown file, like Markdown links.
    return f'<img class="{cls}" src="{rel(path, page)}" alt="" loading="lazy">' if path else ""


def _title(ctx: Ctx, n: dict) -> str:
    title = plain(n["r"]["title"]).strip()
    return title if title and title != n["id"] else ""


def _name(ctx: Ctx, n: dict, page: str | None = None) -> str:
    """Node name in bold, linked to the node's page when it has one and `page` is given."""
    title = _title(ctx, n)
    text = f"**{_cell(title)}**" if title else f"<i>{ctx.loc.ui('page.unnamed')}</i> `{n['id']}`"
    icon = _icon(ctx, n.get("icon"), page) if page else ""
    if page and n["size"] in PAGE_SIZES:
        text = f"[{text}]({rel(node_path(n), page)})"
    return icon + text


def _branch(ctx: Ctx, n: dict) -> str:
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
    """Option name in bold; like in game, its description shows on hover."""
    title = f"**{to_md(o['title'], ctx.loc, page)}**"
    if o["extra"]:
        tip = html.escape(plain(" ".join(o["extra"])), quote=True)
        title = f'<span class="pov-desc" title="{tip}">{title}</span>'
    return _icon(ctx, o.get("icon"), page) + title


def _option_effect(ctx: Ctx, page: str, o: dict) -> str:
    """An option's stat lines (the game's option row). Options that only grant a mechanic have
    none: their description is the effect then."""
    lines = [to_md(s, ctx.loc, page) for s in (o["stats"] or o["extra"])]
    badges = _badges(ctx, o)
    return "<br>".join(lines) + (f"<br>{badges}" if badges else "")


def _footer(ctx: Ctx) -> list[str]:
    meta = ctx.data.meta
    return ["", f"<small>{ctx.loc.ui('page.data_version', version=meta['version'], date=meta['extracted'][:10])}</small>", ""]


def _unimplemented_section(ctx: Ctx, nodes: list[dict], page: str) -> list[str]:
    if not nodes:
        return []
    loc = ctx.loc
    rows = [[_name(ctx, n, page), _branch(ctx, n), n["r"]["category"] or ""] for n in sorted(nodes, key=lambda n: (n["branch"], n["id"]))]
    return [
        f"## {loc.ui('page.unimplemented')} ({len(nodes)})",
        "",
        f'??? note "{loc.ui("page.unimplemented_note")}"',
        "",
        *("    " + line for line in _table([loc.ui("col.name"), loc.ui("col.branch"), loc.ui("col.category")], rows)),
    ]


# ---- Passive tree ------------------------------------------------------------------------------


def page_keystones(ctx: Ctx) -> dict[str, str]:
    page, loc = "passives/keystones.md", ctx.loc
    nodes = [n for n in ctx.tree_nodes if n["size"] == "Keystone"]
    live = sorted((n for n in nodes if _is_implemented(n)), key=lambda n: n["r"]["title"])
    md = [f"# {loc.ui('nav.keystones')}", ""]
    md += _table(
        [loc.ui("col.name"), loc.ui("col.branch"), loc.ui("col.category"), loc.ui("col.effect")],
        [[_name(ctx, n, page), _branch(ctx, n), n["r"]["category"] or "", _effect(ctx, page, n["r"])] for n in live],
    )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)], page)
    return {page: "\n".join(md + _footer(ctx))}


def page_notables(ctx: Ctx) -> dict[str, str]:
    """Notables grouped by category. Their mastery options are on the Masteries page."""
    page, loc = "passives/notables.md", ctx.loc
    nodes = [n for n in ctx.tree_nodes if n["size"] == "Notable"]
    by_cat = defaultdict(list)
    for n in nodes:
        if _is_implemented(n):
            by_cat[n["r"]["category"] or ""].append(n)
    md = [f"# {loc.ui('nav.notables')}", "", loc.ui("page.notables_intro", count=sum(map(len, by_cat.values()))), ""]
    for cat in sorted(by_cat, key=lambda c: (c == "", c.lower())):
        md += [f"## {cat or loc.ui('page.uncategorized')}", ""]
        md += _table(
            [loc.ui("col.name"), loc.ui("col.branch"), loc.ui("col.effect")],
            [[_name(ctx, n, page), _branch(ctx, n), _effect(ctx, page, n["r"])] for n in sorted(by_cat[cat], key=lambda n: n["r"]["title"])],
        )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)], page)
    return {page: "\n".join(md + _footer(ctx))}


def page_masteries(ctx: Ctx) -> dict[str, str]:
    """Choice nodes, by category: each distinct option once, with how many nodes offer it."""
    page, loc = "passives/masteries.md", ctx.loc
    groups: dict[str, dict] = defaultdict(dict)
    for n in ctx.tree_nodes:
        if n["size"] == "Keystone" or not n["r"]["options"]:
            continue
        for o in n["r"]["options"]:
            key = (o["title"], tuple(o["stats"]), tuple(o["extra"]))
            entry = groups[n["r"]["category"] or ""].setdefault(key, {"option": o, "nodes": set()})
            entry["nodes"].add(n["id"])
    md = [f"# {loc.ui('nav.masteries')}", "", loc.ui("page.masteries_intro"), ""]
    for cat in sorted(groups, key=lambda c: (c == "", c.lower())):
        options = sorted(groups[cat].values(), key=lambda e: plain(e["option"]["title"]))
        rows = []
        for e in options:
            o = e["option"]
            rows.append([_option_title(ctx, page, o), _option_effect(ctx, page, o), str(len(e["nodes"]))])
        md += [f"## {cat or loc.ui('page.uncategorized')}", ""]
        md += _table([loc.ui("col.option"), loc.ui("col.effect"), loc.ui("col.offered_by")], rows)
    return {page: "\n".join(md + _footer(ctx))}


def page_nodes(ctx: Ctx) -> dict[str, str]:
    """One page per keystone and notable, placeholders included (marked unimplemented)."""
    loc, pages = ctx.loc, {}
    for n in ctx.tree_nodes:
        if n["size"] not in PAGE_SIZES:
            continue
        page, r = node_path(n), n["r"]
        kind = loc.ui(f"size.{n['size']}")
        md = [f"# {_title(ctx, n) or loc.ui('page.unnamed')}", ""]
        if not _is_implemented(n):
            md += ["!!! warning \"" + loc.ui("page.unimplemented") + "\"", f"    {loc.ui('page.unimplemented_node')}", ""]
        md += [
            _icon(ctx, n.get("icon"), page, "pov-icon-lg")
            + f"<b>{kind}</b> · {_branch(ctx, n)}" + (f" · {r['category']}" if r["category"] else "")
            + f" · [{loc.ui('tree.show')}]({rel(TREE_PAGE, page)}#{n['id']})",
            "",
        ]

        effect = _effect(ctx, page, r)
        if effect:
            md += ['<div class="pov-tooltip" markdown>', "", effect, "", "</div>", ""]

        # Mastery options, apart from the node's own effect.
        if r["options"]:
            md += [f"## {loc.ui('page.mastery_options')}", ""]
            md += _table(
                [loc.ui("col.option"), loc.ui("col.effect")],
                [[_option_title(ctx, page, o), _option_effect(ctx, page, o)] for o in r["options"]],
            )

        # Details.
        info = [
            [loc.ui("col.type"), kind],
            [loc.ui("col.branch"), _branch(ctx, n)],
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
            md += _table(
                [loc.ui("col.name"), loc.ui("col.type"), loc.ui("col.effect")],
                [[_name(ctx, m, page), loc.ui(f"size.{m['size']}"), _effect(ctx, page, m["r"])] for m in near],
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
        raw = {k: n[k] for k in ("mods", "options", "masteryId", "icon") if n.get(k)}
        if raw:
            md += [f'??? abstract "{loc.ui("page.game_data")}"', "", "    ```json"]
            md += ["    " + line for line in json.dumps(raw, ensure_ascii=False, indent=2).splitlines()]
            md += ["    ```", ""]
        pages[page] = "\n".join(md + _footer(ctx))
    return pages


# ---- Tree viewer -------------------------------------------------------------------------------

TREE_PAGE = "passives/tree.md"
TREE_DATA = "passives/tree-data.json"
# Order matters: the viewer refers to sizes and branches by index.
SIZES = ["Small", "Travel", "Notable", "Keystone", "Socket", "Mastery", "Starter", "Portal", "Root"]
# The game's branch colours (Tree.cs) and node diameters (TreeStyle.Size).
BRANCH_COLORS = {
    "War": (0.91, 0.35, 0.27), "Steel": (0.8, 0.43, 0.61), "Flesh": (0.85, 0.68, 0.32),
    "Wind": (0.34, 0.8, 0.78), "Eitr": (0.68, 0.5, 0.95), "Toil": (0.51, 0.65, 0.87),
}
DEFAULT_COLOR = (0.96, 0.85, 0.6)
DIAMETERS = {"Keystone": 58, "Notable": 43.84, "Starter": 43.84, "Portal": 76, "Mastery": 50, "Socket": 50,
             "Small": 30, "Travel": 30, "Root": 64}


def _hex(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in c)


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
    loc, tree = ctx.loc, ctx.data.tree
    hidden = set(tree.get("hiddenLinks") or [])
    curves = tree.get("linkCurve") or {}
    index = {n["id"]: i for i, n in enumerate(ctx.tree_nodes)}
    branches = sorted({n["branch"] for n in ctx.tree_nodes})

    nodes = []
    for n in ctx.tree_nodes:
        flags = (1 if n["size"] in PAGE_SIZES else 0) | (0 if _is_implemented(n) else 2) | (4 if n["r"]["options"] else 0)
        nodes.append([
            n["id"], n["x"], n["y"], SIZES.index(n["size"]) if n["size"] in SIZES else 0, branches.index(n["branch"]),
            _title(ctx, n), _tooltip_html(ctx, n), flags,
            (ctx.icons.path(n.get("icon")) or "").removeprefix(f"{ICONS_DIR}/") if ctx.icons else "",
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
        "sizes": [{"name": loc.ui(f"size.{s}"), "d": DIAMETERS.get(s, 30)} for s in SIZES],
        "branches": [{"name": loc.text(f"@branch.{b}", b), "color": _hex(BRANCH_COLORS.get(b, DEFAULT_COLOR))} for b in branches],
        "ui": {k: loc.ui(f"tree.{k}") for k in ("search", "matches", "reset", "hint")},
        # Relative to the page's rendered URL (passives/tree/), like the attributes below.
        "iconBase": f"../{rel(ICONS_DIR, TREE_PAGE)}/",
    }
    md = [
        "---",
        "hide:",
        "  - navigation",
        "  - toc",
        "---",
        "",
        f"# {loc.ui('nav.tree')}",
        "",
        # URLs relative to the page's rendered URL, passives/tree/ (directory URLs), hence the
        # extra "../". (Not "data-src": the site generator rewrites *src attributes as file paths.)
        f'<div class="pov-tree" data-tree="../{rel(TREE_DATA, TREE_PAGE)}" '
        f'data-node-base="../{rel("passives/node", TREE_PAGE)}/"></div>',
        "",
        loc.ui("tree.help"),
        *_footer(ctx),
    ]
    return {TREE_PAGE: "\n".join(md), TREE_DATA: json.dumps(data, ensure_ascii=False, separators=(",", ":"))}


# ---- Glossary ----------------------------------------------------------------------------------


def _references(ctx: Ctx) -> dict[str, dict]:
    """slug -> where the game text links it: {"keystones"|"notables"|"options": [...], "small": Counter, "terms": set}."""
    refs: dict[str, dict] = defaultdict(lambda: {"Keystone": [], "Notable": [], "options": [], "small": Counter(), "terms": set()})
    for n in ctx.tree_nodes:
        r = n["r"]
        own = [s for line in r["stats"] + r["extra"] for s in slugs(line)]
        for slug in set(own):
            if n["size"] in ("Keystone", "Notable"):
                refs[slug][n["size"]].append(n)
            else:
                for line in r["stats"] + r["extra"]:
                    if slug in slugs(line):
                        refs[slug]["small"][line] += 1
        for o in r["options"]:
            for slug in {s for line in o["stats"] + o["extra"] for s in slugs(line)}:
                refs[slug]["options"].append(o)
    for key, term in ctx.loc.wiki.items():
        for slug in {s for line in term["text"] for s in slugs(line)}:
            if slug != key:
                refs[slug]["terms"].add(key)
    return refs


def page_glossary(ctx: Ctx) -> dict[str, str]:
    loc, wiki = ctx.loc, ctx.loc.wiki
    refs = _references(ctx)
    pages = {}
    order = sorted(wiki, key=lambda k: plain(wiki[k]["title"]).lower())

    # One page per term.
    for key in order:
        page, term, ref = glossary_path(key), wiki[key], refs.get(key)
        md = [f"# {plain(term['title'])}", ""]
        md += [to_md(line, loc, page) + "\n" for line in term["text"]] or [f"*{loc.ui('page.no_text')}*", ""]
        if ref:
            md += [f"## {loc.ui('page.referenced_by')}", ""]
            for size, label in (("Keystone", "nav.keystones"), ("Notable", "nav.notables")):
                if ref[size]:
                    md += [f"### {loc.ui(label)}", ""]
                    md += _table(
                        [loc.ui("col.name"), loc.ui("col.effect")],
                        [[_name(ctx, n, page), _effect(ctx, page, n["r"])] for n in sorted(ref[size], key=lambda n: n["r"]["title"])],
                    )
            if ref["options"]:
                distinct = {(o["title"], tuple(o["stats"])): o for o in ref["options"]}
                md += [f"### {loc.ui('nav.masteries')}", ""]
                md += _table(
                    [loc.ui("col.option"), loc.ui("col.effect")],
                    [[_option_title(ctx, page, o), _option_effect(ctx, page, o)] for o in sorted(distinct.values(), key=lambda o: plain(o["title"]))],
                )
            if ref["small"]:
                md += [f"### {loc.ui('page.small_passives')}", ""]
                md += _table(
                    [loc.ui("col.stat"), loc.ui("col.nodes")],
                    [[to_md(line, loc, page), str(c)] for line, c in sorted(ref["small"].items(), key=lambda kv: -kv[1])],
                )
            if ref["terms"]:
                md += [f"### {loc.ui('page.see_also')}", ""]
                md += [
                    f"- [{plain(wiki[k]['title'])}]({rel(glossary_path(k), page)})"
                    for k in sorted(ref["terms"], key=lambda k: plain(wiki[k]["title"]).lower())
                ]
        pages[page] = "\n".join(md + _footer(ctx))
    return pages


GENERATORS: list[Callable[[Ctx], dict[str, str]]] = [page_tree, page_keystones, page_notables, page_masteries, page_nodes, page_glossary]

# Navigation: (ui title key, page path | children). Titles are translated per language.
# Glossary term pages are reached from keyword links and search.
NAV = [
    ("nav.home", "index.md"),
    ("nav.passives", [
        ("nav.tree", "passives/tree.md"),
        ("nav.keystones", "passives/keystones.md"),
        ("nav.notables", "passives/notables.md"),
        ("nav.masteries", "passives/masteries.md"),
    ]),
    ("nav.about", "about.md"),
]
