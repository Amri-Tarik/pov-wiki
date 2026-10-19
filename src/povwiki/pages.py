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
from .markup import glossary_path, plain, rel, slugs, summary, to_md


@dataclass
class Ctx:
    data: GameData
    loc: Localizer

    @cached_property
    def tree_nodes(self) -> list[dict]:
        """Raw tree nodes joined with their rendered text (key "r")."""
        return [{**n, "r": self.loc.nodes[n["id"]]} for n in self.data.tree["nodes"] if n["id"] in self.loc.nodes]

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


def _title(ctx: Ctx, n: dict) -> str:
    title = plain(n["r"]["title"]).strip()
    return title if title and title != n["id"] else ""


def _name(ctx: Ctx, n: dict, page: str | None = None) -> str:
    """Node name in bold, linked to the node's page when it has one and `page` is given."""
    title = _title(ctx, n)
    text = f"**{_cell(title)}**" if title else f"<i>{ctx.loc.ui('page.unnamed')}</i> `{n['id']}`"
    if page and n["size"] in PAGE_SIZES:
        return f"[{text}]({rel(node_path(n), page)})"
    return text


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
        return f'<span class="pov-desc" title="{tip}">{title}</span>'
    return title


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
        md += [f"<b>{kind}</b> · {_branch(ctx, n)}" + (f" · {r['category']}" if r["category"] else ""), ""]

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


GENERATORS: list[Callable[[Ctx], dict[str, str]]] = [page_keystones, page_notables, page_masteries, page_nodes, page_glossary]

# Navigation: (ui title key, page path | children). Titles are translated per language.
# Glossary term pages are reached from keyword links and search.
NAV = [
    ("nav.home", "index.md"),
    ("nav.passives", [
        ("nav.keystones", "passives/keystones.md"),
        ("nav.notables", "passives/notables.md"),
        ("nav.masteries", "passives/masteries.md"),
    ]),
    ("nav.about", "about.md"),
]
