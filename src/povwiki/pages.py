"""Generated pages. Each generator returns {docs path: markdown}.

All game text comes from the rendered data (the mod's own tooltip code); all wiki text from
loc.ui(). Content the game ships but has not finished is shown with an "Unimplemented" badge
instead of being hidden.
"""

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


def _badges(ctx: Ctx, r: dict) -> str:
    """Badges for unfinished content: broken (disabled by the game) or fallback stat text."""
    out = []
    if r.get("broken"):
        out.append(f'<span class="pov-badge" title="{ctx.loc.ui("badge.broken_tip")}">{ctx.loc.ui("badge.broken")}</span>')
    if r.get("unformatted"):
        tip = ctx.loc.ui("badge.unformatted_tip", stats=", ".join(r["unformatted"]))
        out.append(f'<span class="pov-badge" title="{tip}">{ctx.loc.ui("badge.unformatted")}</span>')
    return " ".join(out)


def _name(ctx: Ctx, n: dict) -> str:
    title = n["r"]["title"].strip()
    if not title or title == n["id"]:
        return f"<i>{ctx.loc.ui('page.unnamed')}</i> `{n['id']}`"
    return f"**{_cell(plain(title))}**"


def _branch(ctx: Ctx, n: dict) -> str:
    return ctx.loc.text(f"@branch.{n['branch']}", n["branch"])


def _lines(ctx: Ctx, page: str, r: dict) -> list[str]:
    lines = [to_md(s, ctx.loc, page) for s in r["stats"]]
    lines += [f"<i>{to_md(s, ctx.loc, page)}</i>" for s in r["extra"]]
    return lines


def _effect(ctx: Ctx, page: str, r: dict) -> str:
    """A node's tooltip body: stat lines, extra text in italics, then its options."""
    lines = _lines(ctx, page, r)
    if r["options"]:
        lines.append(ctx.loc.ui("page.choose_one"))
        for o in r["options"]:
            body = "; ".join(_lines(ctx, page, o))
            badges = _badges(ctx, o)
            lines.append(f"• <b>{to_md(o['title'], ctx.loc, page)}</b>" + (f": {body}" if body else "") + (f" {badges}" if badges else ""))
    badges = _badges(ctx, r)
    return "<br>".join(lines) + (f"<br>{badges}" if badges else "")


def _footer(ctx: Ctx) -> list[str]:
    meta = ctx.data.meta
    return ["", f"<small>{ctx.loc.ui('page.data_version', version=meta['version'], date=meta['extracted'][:10])}</small>", ""]


def _unimplemented_section(ctx: Ctx, nodes: list[dict]) -> list[str]:
    if not nodes:
        return []
    loc = ctx.loc
    rows = [[_name(ctx, n), _branch(ctx, n), n["r"]["category"] or ""] for n in sorted(nodes, key=lambda n: (n["branch"], n["id"]))]
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
        [[_name(ctx, n), _branch(ctx, n), n["r"]["category"] or "", _effect(ctx, page, n["r"])] for n in live],
    )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)])
    return {page: "\n".join(md + _footer(ctx))}


def page_notables(ctx: Ctx) -> dict[str, str]:
    """Notables without choices, grouped by category. Notables with choices are masteries."""
    page, loc = "passives/notables.md", ctx.loc
    nodes = [n for n in ctx.tree_nodes if n["size"] == "Notable" and not n["r"]["options"]]
    by_cat = defaultdict(list)
    for n in nodes:
        if _is_implemented(n):
            by_cat[n["r"]["category"] or ""].append(n)
    md = [f"# {loc.ui('nav.notables')}", "", loc.ui("page.notables_intro", count=sum(map(len, by_cat.values()))), ""]
    for cat in sorted(by_cat, key=lambda c: (c == "", c.lower())):
        md += [f"## {cat or loc.ui('page.uncategorized')}", ""]
        md += _table(
            [loc.ui("col.name"), loc.ui("col.branch"), loc.ui("col.effect")],
            [[_name(ctx, n), _branch(ctx, n), _effect(ctx, page, n["r"])] for n in sorted(by_cat[cat], key=lambda n: n["r"]["title"])],
        )
    md += _unimplemented_section(ctx, [n for n in nodes if not _is_implemented(n)])
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
            badges = _badges(ctx, o)
            rows.append([
                f"**{to_md(o['title'], ctx.loc, page)}**",
                "<br>".join(_lines(ctx, page, o)) + (f"<br>{badges}" if badges else ""),
                str(len(e["nodes"])),
            ])
        md += [f"## {cat or loc.ui('page.uncategorized')}", ""]
        md += _table([loc.ui("col.option"), loc.ui("col.effect"), loc.ui("col.offered_by")], rows)
    return {page: "\n".join(md + _footer(ctx))}


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

    # Index, A-Z.
    index = "glossary/index.md"
    md = [f"# {loc.ui('nav.glossary')}", "", loc.ui("page.glossary_intro", count=len(wiki)), ""]
    letter = None
    for key in order:
        title = plain(wiki[key]["title"])
        if title[:1].upper() != letter:
            letter = title[:1].upper()
            md += ["", f"## {letter}", ""]
        md.append(f"- [{title}]({rel(glossary_path(key), index)}) — {_cell(summary(wiki[key], 140))}")
    pages[index] = "\n".join(md + _footer(ctx))

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
                        [[_name(ctx, n), _effect(ctx, page, n["r"])] for n in sorted(ref[size], key=lambda n: n["r"]["title"])],
                    )
            if ref["options"]:
                distinct = {(o["title"], tuple(o["stats"])): o for o in ref["options"]}
                md += [f"### {loc.ui('nav.masteries')}", ""]
                md += _table(
                    [loc.ui("col.option"), loc.ui("col.effect")],
                    [[f"**{to_md(o['title'], loc, page)}**", "<br>".join(_lines(ctx, page, o))] for o in sorted(distinct.values(), key=lambda o: plain(o["title"]))],
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


GENERATORS: list[Callable[[Ctx], dict[str, str]]] = [page_keystones, page_notables, page_masteries, page_glossary]

# Navigation: (ui title key, page path | children). Titles are translated per language.
# Glossary term pages are reachable from the glossary index and from keyword links.
NAV = [
    ("nav.home", "index.md"),
    ("nav.passives", [
        ("nav.keystones", "passives/keystones.md"),
        ("nav.notables", "passives/notables.md"),
        ("nav.masteries", "passives/masteries.md"),
    ]),
    ("nav.glossary", "glossary/index.md"),
    ("nav.about", "about.md"),
]
