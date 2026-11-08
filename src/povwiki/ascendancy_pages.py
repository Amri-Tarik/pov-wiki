"""Ascendancy classes (6.0): an index, a page per class, and the class circles of the tree viewer.

The classes come from the harness (harness/classes.py: ClassTrees, Subclasses, TreePaths). Each class
tree is drawn in a circle with the class's art, like Path of Building's ascendancy circles: around
the passive tree in its viewer, on the side of the class's path (the gate node of the path's sector,
TreePaths.GateOf), and alone on the class's page.
"""

import html
import json
import math
import re
import unicodedata

from .markup import rel, to_html, to_md
from .pages import Ctx, _footer, _img, _table

INDEX = "ascendancy/index.md"
_ART_RING = 0.84  # class nodes fill this share of a circle's radius
_ROLE_ORDER = {"start": 0, "notable": 1, "small": 2}


def classes(ctx: Ctx) -> dict:
    """{"classes": [...], "paths": [...], "points": int} as rendered, or {} before 6.0."""
    return ctx.loc.data.rendered(ctx.loc.lang.mod).get("classes") or {}


NOTABLES = "ascendancy/notables.md"
_ENGLISH: dict[str, dict[str, str]] = {}


def _english(ctx: Ctx) -> dict[str, str]:
    """Class key -> English name and node id -> English title. Pages are named after the English
    text in every language (the language switcher and search links pair pages by path)."""
    version = ctx.data.version
    if version not in _ENGLISH:  # the rendered text is large: read once per version
        names = {}
        for c in (ctx.loc.data.rendered("english").get("classes") or {}).get("classes") or []:
            names[c["key"]] = c["name"]
            names.update((n["id"], n["title"]) for n in c["nodes"])
        _ENGLISH[version] = names
    return _ENGLISH[version]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("-")


def class_path(ctx: Ctx, key: str) -> str:
    """A class's page: "asc-gladiator-concept" -> ascendancy/arena-spearman."""
    return f"ascendancy/{_slug(_english(ctx).get(key) or key.removeprefix('asc-')) or key}.md"


def notable_path(ctx: Ctx, n: dict) -> str:
    """A class notable's page: ascendancy/notable/rhythm-of-the-colossus (titles are unique across classes)."""
    return f"ascendancy/notable/{_slug(_english(ctx).get(n['id']) or n['local']) or n['local']}.md"


def _page_url(path: str, page: str) -> str:
    """A link from the viewer (which sits one folder deeper than its page) to a page's folder URL."""
    href = f"../{rel(path, page)}"
    return href.removesuffix(".md") + "/" if href.endswith(".md") else href


def _art_image(c: dict) -> str:
    """The class's portrait (ClassTrees.Def.Art "class:<key>" -> classart.<key>-512.png)."""
    return f"PassiveTree.classart.{c['art'].removeprefix('class:')}-512.png"


def _art(ctx: Ctx, c: dict) -> str | None:
    return ctx.icons.art_path(_art_image(c)) if ctx.icons else None


def _path_name(data: dict, key: str) -> str:
    return next((p["name"] for p in data.get("paths") or [] if p["key"] == key), key)


def _access(ctx: Ctx, c: dict) -> str:
    return ctx.loc.ui("ascendancy.access_common" if c["public"] else "ascendancy.access_early")


def _ordered(c: dict) -> list[dict]:
    """The class's nodes, start first, then from the start outwards (breadth first over its links)."""
    by_id = {n["id"]: n for n in c["nodes"]}
    near: dict[str, list[str]] = {n["id"]: [] for n in c["nodes"]}
    for a, b in c["links"]:
        if a in near and b in near:
            near[a].append(b)
            near[b].append(a)
    seen, out = set(), []
    queue = [n["id"] for n in c["nodes"] if n["role"] == "start"]
    while queue:
        i = queue.pop(0)
        if i in seen:
            continue
        seen.add(i)
        out.append(by_id[i])
        queue += sorted(near[i], key=lambda j: (_ROLE_ORDER.get(by_id[j]["role"], 3), by_id[j]["title"]))
    return out + [n for n in c["nodes"] if n["id"] not in seen]


def _lines(ctx: Ctx, n: dict, page: str) -> str:
    return "<br>".join(to_md(s, ctx.loc, page) for s in n["stats"] + n["extra"]) or "—"


# ---- Viewer -------------------------------------------------------------------------------------

def _extent(c: dict) -> tuple[float, float, float]:
    """Centre (x, y) and radius of a class tree's nodes."""
    xs, ys = [n["x"] for n in c["nodes"]], [n["y"] for n in c["nodes"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return cx, cy, max(math.hypot(n["x"] - cx, n["y"] - cy) for n in c["nodes"]) + 40


def _gates(ctx: Ctx) -> dict[str, tuple[float, float]]:
    """Branch -> position of the gate node of that sector (TreePaths.GateOf: a neighbour of the root)."""
    tree, by_id = ctx.raw_tree, {n["id"]: n for n in ctx.tree_nodes}
    out = {}
    for a, b in tree.get("links") or []:
        other = b if a == "root" else a if b == "root" else None
        if other in by_id:
            n = by_id[other]
            out.setdefault(n["branch"], (n["x"], n["y"]))
    return out


def circles(ctx: Ctx) -> list[dict]:
    """Where each class circle goes around the passive tree: beyond the tree's edge in the direction
    of its path's gate, a path's classes side by side across that direction."""
    data = classes(ctx)
    if not data.get("classes") or not ctx.tree_nodes:
        return []
    edge = max(math.hypot(n["x"], n["y"]) for n in ctx.tree_nodes)
    radius = max(_extent(c)[2] for c in data["classes"]) / _ART_RING
    gates, out = _gates(ctx), []
    for p in data.get("paths") or []:
        mine = [c for c in data["classes"] if c["path"] == p["key"]]
        gx, gy = gates.get(p["branch"], (0.0, 0.0))
        angle = math.atan2(gy, gx) if (gx or gy) else 0.0
        ux, uy = math.cos(angle), math.sin(angle)  # outwards
        vx, vy = -uy, ux  # across
        dist = edge + radius * 1.35
        for k, c in enumerate(mine):
            off = (k - (len(mine) - 1) / 2) * radius * 2.75
            out.append({"class": c, "x": ux * dist + vx * off, "y": uy * dist + vy * off, "r": radius})
    return out


def overlay(ctx: Ctx, page: str, sizes: list[str], frame_kinds: tuple, frame_kind, icons_dir: str,
            placed: list[dict] | None = None) -> tuple[list, list, list]:
    """The viewer rows for class circles: (nodes, links between them as index pairs within these
    nodes, circles). Node rows follow page_tree's layout plus an 11th field, the page to open."""
    placed = circles(ctx) if placed is None else placed
    nodes, links, rings = [], [], []
    for pc in placed:
        c = pc["class"]
        cx, cy, _ = _extent(c)
        base = len(nodes)
        index = {}
        href = _page_url(class_path(ctx, c["key"]), page)
        for n in c["nodes"]:
            size = "Root" if n["role"] == "start" else n["size"] if n["size"] in sizes else "Small"
            tip = "".join(f'<div class="pov-tt-line">{to_html(s)}</div>' for s in n["stats"])
            tip += "".join(f'<div class="pov-tt-extra">{to_html(s)}</div>' for s in n["extra"])
            icon = (ctx.icons.path(n["icon"]) or "").removeprefix(f"{icons_dir}/") if ctx.icons else ""
            index[n["id"]] = base + len(index)
            nodes.append([n["id"], pc["x"] + n["x"] - cx, pc["y"] + n["y"] - cy, sizes.index(size), -1,
                          html.escape(n["title"]), tip, 0, icon, frame_kinds.index(frame_kind(size)),
                          _page_url(notable_path(ctx, n), page) if n["role"] == "notable" else f"{href}#{n['local']}"])
        links += [[index[a], index[b]] for a, b in c["links"] if a in index and b in index]
        art = _art(ctx, c)
        rings.append({"x": pc["x"], "y": pc["y"], "r": pc["r"], "name": c["name"], "href": href,
                      "art": f"../{rel(art, page)}" if art else ""})
    return nodes, links, rings


# ---- Pages --------------------------------------------------------------------------------------

def page_ascendancy(ctx: Ctx) -> dict[str, str]:
    data = classes(ctx)
    if not data.get("classes"):
        return {}
    ui, page = ctx.loc.ui, INDEX
    from .formula_pages import _values, shown

    v = _values().get("ascendancy", {})
    md = [f"# {ui('ascendancy.title')}", "", ui("ascendancy.intro"), ""]
    if shown(ctx, "ascendancy"):
        knobs = (ctx.loc.difficulty or {}).get("knobs") or {}
        md += [f"## {ui('ascendancy.how')}", "",
               ui("ascendancy.points", points=data.get("points") or v.get("cap", 8), per=v.get("per_tier", 2)), "",
               ui("ascendancy.change", respec=f"{(knobs.get('asc.respec') or {}).get('value', 5):g}"), ""]
    md += [ui("ascendancy.access_note"), "", ui("ascendancy.viewer", tree=f"{rel('passives/tree.md', page)}"), "",
           ui("ascendancy.notables_line", notables=rel(NOTABLES, page)), ""]
    for p in data.get("paths") or []:
        mine = [c for c in data["classes"] if c["path"] == p["key"]]
        if not mine:
            continue
        md += [f"## {p['name']}", "", f"<small>{html.escape(p['attr'])}</small>", ""]
        rows = []
        for c in mine:
            art = _art(ctx, c)
            rows.append([_img(art, page, 64) if art else "", f"**[{c['name']}]({rel(class_path(ctx, c['key']), page)})**<br>{html.escape(c['sub'])}",
                         _access(ctx, c), str(sum(1 for n in c["nodes"] if n["role"] != "start"))])
        md += _table(["", ui("ascendancy.col_class"), ui("ascendancy.col_access"), ui("ascendancy.col_nodes")], rows)
    pages = {page: "\n".join(md + _footer(ctx))}
    for c in data["classes"]:
        pages.update(_class_page(ctx, data, c))
        for n in c["nodes"]:
            if n["role"] == "notable":
                pages.update(_notable_page(ctx, data, c, n))
    pages.update(_notables_page(ctx, data))
    return pages


def _class_link(ctx: Ctx, c: dict, page: str) -> str:
    return f"[{c['name']}]({rel(class_path(ctx, c['key']), page)})"


def _node_icon(ctx: Ctx, n: dict, page: str, px: int) -> str:
    return _img(ctx.icons.path(n["icon"]), page, px) if ctx.icons and n["icon"] else ""


def _node_name(ctx: Ctx, n: dict, page: str) -> str:
    """A node's name in bold: notables link their own page."""
    name = f"**{html.escape(n['title'])}**"
    return f"[{name}]({rel(notable_path(ctx, n), page)})" if n["role"] == "notable" else name


def _notables_page(ctx: Ctx, data: dict) -> dict[str, str]:
    """Every class notable, by path and class."""
    ui, page = ctx.loc.ui, NOTABLES
    every = [n for c in data["classes"] for n in c["nodes"] if n["role"] == "notable"]
    md = [f"# {ui('ascendancy.notables')}", "", ui("ascendancy.notables_intro", count=len(every), index=rel(INDEX, page)), ""]
    for p in data.get("paths") or []:
        mine = [c for c in data["classes"] if c["path"] == p["key"]]
        if not mine:
            continue
        md += [f"## {p['name']}", ""]
        for c in mine:
            md += [f"### {_class_link(ctx, c, page)}", ""]
            rows = [[_node_icon(ctx, n, page, 32), _node_name(ctx, n, page), _lines(ctx, n, page)]
                    for n in _ordered(c) if n["role"] == "notable"]
            md += _table(["", ui("col.name"), ui("ascendancy.col_effect")], rows)
    return {page: "\n".join(md + _footer(ctx))}


def _notable_page(ctx: Ctx, data: dict, c: dict, n: dict) -> dict[str, str]:
    from .pages import _keywords_section

    ui, page = ctx.loc.ui, notable_path(ctx, n)
    md = [f"# {n['title']}", ""]
    icon = _node_icon(ctx, n, page, 96)
    md += [(f'<span class="pov-art-lg">{icon}</span>' if icon else "")
           + f"<b>{ui('ascendancy.notable_kind')}</b> · {_class_link(ctx, c, page)} · {_path_name(data, c['path'])}"
           + f" · [{ui('ascendancy.notables')}]({rel(NOTABLES, page)})", ""]
    md += ['<div class="pov-tooltip" markdown>', "", _lines(ctx, n, page), "", "</div>", ""]
    by_id = {m["id"]: m for m in c["nodes"]}
    others = [b if a == n["id"] else a for a, b in c["links"] if n["id"] in (a, b)]
    near = [by_id[i] for i in others if i in by_id]
    if near:
        md += [f"## {ui('page.connections')}", ""]
        md += _table(["", ui("col.name"), ui("ascendancy.col_role"), ui("ascendancy.col_effect")],
                     [[_node_icon(ctx, m, page, 32), _node_name(ctx, m, page),
                       ui(f"ascendancy.role_{m['role']}") if m["role"] in _ROLE_ORDER else m["role"], _lines(ctx, m, page)]
                      for m in near])
    md += _keywords_section(ctx, page, n["stats"] + n["extra"], [])
    return {page: "\n".join(md + _footer(ctx))}


def _class_page(ctx: Ctx, data: dict, c: dict) -> dict[str, str]:
    from .icons import DOCS_DIR, FRAME_KINDS, frame_kind
    from .pages import DIAMETERS, SIZES

    ui, page = ctx.loc.ui, class_path(ctx, c["key"])
    data_path = page.removesuffix(".md") + "-tree.json"
    art = _art(ctx, c)
    md = [f"# {c['name']}", ""]
    if art:
        md += [_img(art, page, 160), ""]
    md += [f"*{html.escape(c['sub'])}*", "",
           ui("ascendancy.class_line", path=_path_name(data, c["path"]), access=_access(ctx, c),
              index=rel(INDEX, page), title=ui("ascendancy.title")), ""]
    # Its tree, in the viewer (tree.js), alone in its circle.
    radius = _extent(c)[2] / _ART_RING
    nodes, links, rings = overlay(ctx, page, SIZES, FRAME_KINDS, frame_kind, DOCS_DIR,
                                  placed=[{"class": c, "x": 0.0, "y": 0.0, "r": radius}])
    for row in nodes:  # on its own page a node opens its row below
        if "#" in row[10]:
            row[10] = "#" + row[10].split("#", 1)[1]
    viewer = {
        "nodes": nodes, "links": links, "classes": rings,
        "sizes": [{"name": ui(f"{ctx.spec.sizes}.{s}"), "d": DIAMETERS.get(s, 30)} for s in SIZES],
        "branches": [], "ui": {k: ui(f"tree.{k}") for k in ("search", "matches", "reset", "hint")},
        "iconBase": f"../{rel(DOCS_DIR, page)}/" if ctx.icons else "",
        "frames": list(FRAME_KINDS) if ctx.icons else [],
    }
    md += [f'<div class="pov-tree pov-tree-class" data-tree="../{rel(data_path, page)}" data-node-base="./" data-height="60vh"></div>', ""]
    md += [f"## {ui('ascendancy.nodes')}", ""]
    rows = []
    for n in _ordered(c):
        rows.append([_node_icon(ctx, n, page, 32), f'<span id="{n["local"]}"></span>' + _node_name(ctx, n, page),
                     ui(f"ascendancy.role_{n['role']}") if n["role"] in _ROLE_ORDER else n["role"], _lines(ctx, n, page)])
    md += _table(["", ui("col.name"), ui("ascendancy.col_role"), ui("ascendancy.col_effect")], rows)
    return {page: "\n".join(md + _footer(ctx)), data_path: json.dumps(viewer, ensure_ascii=False)}
