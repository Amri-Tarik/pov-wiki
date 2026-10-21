"""Patch pages: what a mod update changed in the game data, found by comparing two versions.

A comparison needs both versions extracted and rendered, which only the machine that extracted
them has. So the build writes each comparison down (patches/<version>/<lang>.json: only the
entries that changed, as plain text) whenever the version before it is there too, and the pages
are made from those files: they keep working once the old data is gone.

Everything is compared as the site shows it: an entry (a node, a mod, a unique...) is its name
and its lines of text. Only the data is compared; a change in how the code uses it (a formula, a
mechanic) is not seen here: see the formulas' own check (povwiki.formulas).
"""

import difflib
import functools
import html
import json
import re

from .data import EXTRACTED, GameData, _version_key
from .i18n import Localizer
from .markup import glossary_path, plain, rel
from .pages import PAGE_SIZES, Ctx, _cell, _footer, _is_implemented, _kind, _title, node_path
from .paths import ROOT

PATCHES = ROOT / "patches"
INDEX = "patches/index.md"


def patch_path(version: str) -> str:
    return f"patches/{version}.md"


def versions() -> list[str]:
    """Versions with a comparison written down, newest first."""
    found = [p.name for p in PATCHES.glob("*") if p.is_dir()] if PATCHES.exists() else []
    return sorted(found, key=_version_key, reverse=True)


# ---- Snapshots: every entry of a version as name and text lines ---------------------------------


def _md_plain(s: str) -> str:
    """Markdown or game text as plain text: links, emphasis and tags dropped."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain(s))
    s = re.sub(r"<[^>]+>|\{[^{}]*\}", "", s)  # tags, and attribute lists ({ .pov-kw })
    return html.unescape(s.replace("**", "").replace("*", "")).strip()


def _entry(name: str, lines: list[str], link: str | None = None, kind: str = "") -> dict:
    return {"name": name, "lines": [x for x in (_md_plain(s) for s in lines) if x], "link": link, "kind": kind}


def _tree(ctx: Ctx) -> dict[str, dict]:
    out = {}
    for n in ctx.tree_nodes:
        if not _is_implemented(n):
            continue
        r = n["r"]
        lines = list(r["stats"]) + list(r["extra"])
        lines += [f"{o['title']}: " + "; ".join(_md_plain(s) for s in o["stats"] + o.get("extra", [])) for o in r["options"]]
        link = node_path(ctx, n) if n["size"] in PAGE_SIZES else f"{ctx.path('tree')}/#{n['id']}"
        out[n["id"]] = _entry(_title(ctx, n) or n["id"], lines, link, _kind(ctx, n))
    return out


def _affixes(ctx: Ctx) -> dict[str, dict]:
    from .item_pages import _title as affix_title
    from .item_pages import mod_path

    ui, out = ctx.loc.ui, {}
    for a in ctx.loc.loot["affixes"]:
        lines = [ui("patch.tier", tier=t["id"], lo=max(1, t["minLevel"]), hi=t["maxLevel"] if t.get("maxLevel") is not None else "∞",
                    weight=f"{t['weight']:g}") + " " + t["text"]["base"] for t in a["tiers"]]
        out[a["id"]] = _entry(affix_title(a), lines or [a["text"]], mod_path(a))
    return out


def _bases(ctx: Ctx) -> dict[str, dict]:
    """Item bases: the level crafted copies get, defences by quality and implicit lines."""
    from .base_pages import _DEFENCES, _level, base_path, bases

    ui, out = ctx.loc.ui, {}
    for prefab, b in bases(ctx).items():
        info, lines = b["info"], []
        if (level := _level(ctx, prefab)) is not None:
            lines.append(ui("patch.crafted_level", level=level))
        for q, d in enumerate(info.get("defences") or [], 1):
            if values := ", ".join(f"{ui(key)} {d[k]:g}" for k, key in _DEFENCES if d.get(k)):
                lines.append(f"{ui('items.quality_n', n=q)}: {values}")
        for i in info.get("implicits") or []:
            lines.append(i["text"] if "text" in i else " / ".join(t or "—" for t in i.get("byQuality") or []))
        out[prefab] = _entry(b["name"], lines, base_path(prefab))
    return out


def _uniques(ctx: Ctx) -> dict[str, dict]:
    from .gear_pages import UNIQUES_PAGE, _line_md, _unique_name, _unique_sources, unique_path

    gear, out = ctx.loc.gear, {}
    catalog = {u["id"]: u for u in ctx.data.loot.get("uniques") or []}
    for item, u in (gear.get("uniques") or {}).items():
        lines = [s.strip().removeprefix("- ") for line in u["lines"] for s in _line_md(ctx, line, UNIQUES_PAGE)]
        lines.append(ctx.loc.ui("patch.drops", sources=_unique_sources(ctx, item, catalog, UNIQUES_PAGE)))
        out[item] = _entry(_unique_name(ctx, item), lines, unique_path(item))
    return out


def _currency(ctx: Ctx) -> dict[str, dict]:
    from .base_pages import _item_name
    from .gear_pages import currency_path

    out = {}
    for item, v in (ctx.loc.loot.get("items") or {}).items():
        out[item] = _entry(_item_name(ctx, item), [v.get("action") or ""], currency_path(item))
    return out


def _drops(ctx: Ctx) -> dict[str, dict]:
    """Boss loot tables: what each drops and how often."""
    from .base_pages import _item_name
    from .gear_pages import _num, _pct, _unique_name
    from .monster_pages import BOSSES_PAGE, _mod_bosses, boss_path

    ui, out = ctx.loc.ui, {}
    for t in ctx.data.loot.get("tables") or []:
        total = sum(e["weight"] for e in t["entries"]) or 1
        bonus = ", " + ui("gear.first_drop", n=_num(t["firstDrop"])) if t.get("firstDrop", 1) > 1 else ""
        lines = []
        for e in t["entries"]:
            item = e["id"]
            name = _unique_name(ctx, item) if item in ctx.loc.gear.get("uniques", {}) else _item_name(ctx, item)
            lo, hi = e.get("stackMin", 1), e.get("stackMax", 1)
            amount = f" ×{lo}–{hi}" if hi > lo else (f" ×{lo}" if lo > 1 else "")
            lines.append(f"{name}{amount}: {_pct(t['chance'] * e['weight'] / total)}{bonus}")
        creatures = t["creatures"]
        first = creatures[0] if creatures else ""
        link = boss_path(first) if first in _mod_bosses(ctx) else f"{BOSSES_PAGE}#{first.lower()}"  # as creature_link
        out[t["id"]] = _entry(", ".join(ctx.loc.creature(c) for c in creatures), lines, link)
    return out


def _monster_mods(ctx: Ctx) -> dict[str, dict]:
    from .monster_pages import mod_anchor

    out = {}
    for m in ctx.loc.monsters.get("mods") or []:
        lines = [m.get("about") or ""] + [f"{s['label']}: {s['value']}" for s in m.get("settings") or []]
        out[m["id"]] = _entry(m["name"], lines, mod_anchor(m["id"]))
    return out


def _world(ctx: Ctx) -> dict[str, dict]:
    """Numbers about the world: biome levels, divine azurite, creatures that keep their health."""
    from .base_pages import _item_name
    from .formula_pages import EXPERIENCE_PAGE, LOOT_PAGE, CREATURES_PAGE
    from .gear_pages import _pct

    ui, loc, out = ctx.loc.ui, ctx.loc, {}

    def biome(b: str) -> str:
        return loc.vkey(f"biome_{b.lower()}", b)

    biomes = [b for b in loc.loot.get("biomes") or [] if b["id"] != "Ocean"]
    out["biome-levels"] = _entry(ui("patch.biome_levels"), [
        ui("patch.biome_level", biome=biome(b["id"]), level=b["level"],
           lo=b.get("recommended", b["level"]), hi=b.get("recommended", b["level"]) + b.get("recommendedBand", b.get("band", 0)))
        for b in biomes], EXPERIENCE_PAGE)
    veins = loc.data.rendered(loc.lang.mod).get("veins") or {}
    if veins.get("ores"):
        lines = [ui("patch.chisel_tier", ore=_item_name(ctx, o), tier=t) for o, t in zip(veins["ores"], veins.get("needTier") or [])]
        lines += [ui("patch.strike_chance", biome=biome(b), chance=_pct(c)) for b, c in (veins.get("strikeChance") or {}).items() if c]
        lines += [ui("patch.pity", biomes=", ".join(biome(b) for b in veins["pityBiomes"]),
                            misses=(veins.get("strike") or {}).get("pity", 1) - 1)] if veins.get("pityBiomes") else []
        out["azurite"] = _entry(ui("patch.azurite"), lines, "crafting/buildings.md")
    fixed = (loc.data.rendered(loc.lang.mod).get("difficulty") or {}).get("fixedHealth") or []
    out["fixed-health"] = _entry(ui("patch.fixed_health"), [loc.creature(c) for c in fixed], CREATURES_PAGE)
    if (chance := loc.gear.get("monolithUniqueChance")) is not None:
        out["monolith-unique"] = _entry(ui("patch.monolith_unique"), [_pct(chance)], LOOT_PAGE)
    return out


def _keywords(ctx: Ctx) -> dict[str, dict]:
    return {slug: _entry(t["title"], list(t["text"]) if isinstance(t["text"], list) else [t["text"]], glossary_path(slug))
            for slug, t in ctx.loc.wiki.items()}


SECTIONS = {  # id: (title key, entries); the passive and craft trees take their own context
    "passives": ("passives.title", None),
    "crafting": ("crafting.title", None),
    "mods": ("items.mods", _affixes),
    "bases": ("items.bases", _bases),
    "uniques": ("gear.uniques", _uniques),
    "currency": ("gear.currency", _currency),
    "drops": ("patch.boss_drops", _drops),
    "monster-mods": ("monsters.mods", _monster_mods),
    "world": ("patch.world", _world),
    "keywords": ("patch.keywords", _keywords),
}


def snapshot(ctxs: list[Ctx]) -> dict[str, dict[str, dict]]:
    return {"passives": _tree(ctxs[0]), "crafting": _tree(ctxs[1]),
            **{sid: make(ctxs[0]) for sid, (_, make) in SECTIONS.items() if make}}


def _same(a: dict, b: dict) -> bool:
    return a["name"] == b["name"] and a["lines"] == b["lines"]


def compare(old: dict, new: dict) -> dict:
    """Only what changed: {section: {id: {"old": entry or None, "new": entry or None}}}."""
    out = {}
    for sid in SECTIONS:
        a, b = old.get(sid, {}), new.get(sid, {})
        changed = {i: {"old": a.get(i), "new": b.get(i)} for i in sorted(set(a) | set(b))
                   if i not in a or i not in b or not _same(a[i], b[i])}
        if changed:
            out[sid] = changed
    return out


def previous(version: str) -> str | None:
    """The version before this one among those extracted (with rendered text)."""
    older = [p.name for p in EXTRACTED.glob("*") if (p / "rendered").exists() and _version_key(p.name) < _version_key(version)]
    return max(older, key=_version_key) if older else None


def update(ctxs: list[Ctx]) -> None:
    """Write down this version's comparison with the one before, when that one is extracted too."""
    from .pages import TREES

    data, loc = ctxs[0].data, ctxs[0].loc
    prev = previous(data.version)
    if prev is None or not (EXTRACTED / prev / "rendered" / f"{loc.lang.mod}.json").exists():
        return
    old_data = GameData(prev)

    def ctxs_of(d: GameData, lang) -> list[Ctx]:
        return [Ctx(data=d, loc=Localizer(lang, loc.default, d), spec=spec) for spec in TREES]

    changes = compare(snapshot(ctxs_of(old_data, loc.lang)), snapshot(ctxs))
    if loc.lang.code != loc.default.code:
        # What changed is decided in the default language: a translation reworded between two
        # versions is not a change to the game. The entries that did change keep this language's text.
        real = compare(snapshot(ctxs_of(old_data, loc.default)), snapshot(ctxs_of(data, loc.default)))
        changes = {sid: kept for sid, c in changes.items() if (kept := {i: e for i, e in c.items() if i in real.get(sid, {})})}
    out = PATCHES / data.version / f"{loc.lang.code}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"from": prev, "to": data.version, "date": data.meta["extracted"][:10], "changes": changes},
                      ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")


def write(version: str) -> None:
    """Write down a version's comparison for every enabled language (`povwiki patches`)."""
    from .i18n import load_languages
    from .pages import TREES

    default_code, langs = load_languages()
    data = GameData(version)
    for lang in (x for x in langs.values() if x.enabled):
        loc = Localizer(lang, langs[default_code], data)
        update([Ctx(data=data, loc=loc, spec=spec) for spec in TREES])
        print(f"{version} [{lang.code}]: compared with {previous(version) or 'nothing (no earlier version extracted)'}")


# ---- Pages --------------------------------------------------------------------------------------

_TOKEN = re.compile(r"[-+]?\d+(?:[.,]\d+)?%?|\w+|\s+|[^\w\s]")


def _words(old: str, new: str) -> str:
    """One line changed: the new line, with what went in marked and what went out struck."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    match = difflib.SequenceMatcher(None, a, b, autojunk=False)
    kept = sum(m.size for m in match.get_matching_blocks())
    if kept < 0.6 * min(len(a), len(b)) and len(old) + len(new) > 160:  # a paragraph rewritten rather than changed: both whole
        return f"<del>{html.escape(old)}</del><br><ins>{html.escape(new)}</ins>"
    out = []
    for op, i1, i2, j1, j2 in match.get_opcodes():
        gone, came = html.escape("".join(a[i1:i2])), html.escape("".join(b[j1:j2]))
        if op == "equal":
            out.append(came)
        else:
            arrow = " → " if gone.strip() and came.strip() else ""
            out += ([f"<del>{gone}</del>{arrow}"] if gone.strip() else []) + ([f"<ins>{came}</ins>"] if came.strip() else [came] if came else [])
    return "".join(out)


def _lines(old: list[str], new: list[str]) -> list[str]:
    """What changed between two lists of lines: changed lines word by word, the others whole."""
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        pairs = list(zip(old[i1:i2], new[j1:j2])) if op == "replace" else []
        out += [_words(a, b) for a, b in pairs]
        out += [f"<del>{html.escape(s)}</del>" for s in old[i1 + len(pairs):i2]]
        out += [f"<ins>{html.escape(s)}</ins>" for s in new[j1 + len(pairs):j2]]
    return out


def _link(entry: dict, page: str, count: int = 1) -> str:
    name = _cell(html.escape(entry["name"]))
    times = f" ×{count}" if count > 1 else ""
    if not entry.get("link"):
        return f"**{name}**{times}"
    target, _, anchor = entry["link"].partition("#")
    if target.endswith("/"):  # the tree viewer: its #node anchor only exists in its script (pages._tree_link)
        return f'<a href="{rel(target.rstrip("/"), page)}/#{anchor}"><b>{name}</b></a>{times}'
    return f"[**{name}**]({rel(target, page)}{'#' + anchor if anchor else ''}){times}"


def _which(c: dict) -> str:
    return "both" if c["old"] and c["new"] else "new" if c["new"] else "old"


def _change(c: dict) -> list[str]:
    """One entry's change as lines of HTML: what went out struck, what came in marked."""
    old, new = c["old"], c["new"]
    if old and new:
        renamed = [f"<del>{html.escape(old['name'])}</del> → <ins>{html.escape(new['name'])}</ins>"] if old["name"] != new["name"] else []
        return renamed + _lines(old["lines"], new["lines"])
    if new:
        return [f"<ins>{html.escape(s)}</ins>" for s in new["lines"]]
    return [f"<del>{html.escape(s)}</del>" for s in old["lines"]]


def _moved(changes: dict) -> dict:
    """Entries that went away and came back under a new id with the same name and type (a cluster
    of passives moved elsewhere in the tree) are paired up as one moved entry."""
    gone: dict[tuple, list[str]] = {}
    for i, c in changes.items():
        if c["new"] is None:
            gone.setdefault((c["old"]["name"], c["old"].get("kind") or ""), []).append(i)
    out = {}
    for i, c in changes.items():
        if c["old"] is None and (ids := gone.get((c["new"]["name"], c["new"].get("kind") or ""))):
            out[i] = {"old": changes[ids.pop(0)]["old"], "new": c["new"], "moved": True}
        elif c["new"] is not None:
            out[i] = c
    paired = {id(x["old"]) for x in out.values() if x.get("moved")}
    out.update({i: c for i, c in changes.items() if c["new"] is None and id(c["old"]) not in paired})
    return out


def _names(entries: list[dict], page: str, linked: bool) -> str:
    """The name cell of a row: each name once, with how many entries carry it, linked to the first."""
    by_name: dict[str, list[dict]] = {}
    for e in entries:
        by_name.setdefault(e["name"], []).append(e)
    if linked:
        return ", ".join(_link(es[0], page, len(es)) for es in by_name.values())
    return ", ".join(f"**{_cell(html.escape(n))}**" + (f" ×{len(es)}" if len(es) > 1 else "") for n, es in by_name.items())


def _section(ctx: Ctx, sid: str, changes: dict, page: str) -> list[str]:
    ui = ctx.loc.ui
    changes = _moved(changes)
    md = [f"## {ui(SECTIONS[sid][0])}", ""]
    for title, which in (("patch.changed", "both"), ("patch.added", "new"), ("patch.removed", "old")):
        # Entries of a type with the same change share a row: a dozen small passives made alike, or
        # every craft notable offering a changed mastery option.
        groups: dict[tuple, list[dict]] = {}
        for c in changes.values():
            if _which(c) != which:
                continue
            e = c["new"] or c["old"]
            lines = ([f"<i>{ui('patch.moved')}</i>"] if c.get("moved") else []) + _change(c)
            groups.setdefault((e.get("kind") or "", tuple(lines)), []).append(e)
        if not groups:
            continue
        kinds = any(k for k, _ in groups)
        md += [f"### {ui(title)} ({sum(len(es) for es in groups.values())})", ""]
        md += _rows([ui("col.name"), *([ui("patch.kind")] if kinds else []), ui("patch.change")],
                    [[_names(es, page, which != "old"), *([_cell(kind)] if kinds else []), "<br>".join(lines)]
                     for (kind, lines), es in sorted(groups.items(), key=lambda kv: kv[1][0]["name"].lower())])
    return md


def _rows(header: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header), *("| " + " | ".join(r) + " |" for r in rows), ""]


@functools.cache
def _load(version: str, lang: str) -> dict | None:
    path = PATCHES / version / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def history(ctx: Ctx, sid: str, ids: list[str], page: str) -> list[str]:
    """An entry's own page: what each patch changed in it (section `sid` of the patch pages; one
    page can show several entries, e.g. a boss's drop tables), newest first, linked to the patch."""
    ui, rows = ctx.loc.ui, []
    for v in versions():
        p = _load(v, ctx.loc.lang.code) or {}
        changes = _moved((p.get("changes") or {}).get(sid, {}))
        for i in ids:
            if c := changes.get(i):
                what = ui("patch.moved") if c.get("moved") else {"both": "", "new": ui("patch.added"), "old": ui("patch.removed")}[_which(c)]
                rows.append([f"[{ui('patch.title', version=v)}]({rel(patch_path(v), page)})" + (f" <small>({what})</small>" if what else ""),
                             "<br>".join(_change(c))])
    if not rows:
        return []
    return [f"## {ui('patch.history')}", ""] + _rows([ui("patch.version"), ui("patch.change")], rows)


def page_patches(ctx: Ctx) -> dict[str, str]:
    ui, lang = ctx.loc.ui, ctx.loc.lang.code
    pages, listed = {}, []
    for v in versions():
        p = _load(v, lang)
        if p is None:
            continue
        page = patch_path(v)
        changes = p["changes"]
        # Out of search: a node's name finds the node, not the patches that touched it (and a big
        # patch's tables are too long for one search entry).
        md = ["---", "search:", "  exclude: true", "---", "", f"# {ui('patch.title', version=v)}", "",
              ui("patch.intro", old=p["from"], new=v), ""]
        if not changes:
            md += [ui("patch.nothing"), ""]
        for sid in SECTIONS:
            if sid in changes:
                md += _section(ctx, sid, changes[sid], page)
        pages[page] = "\n".join(md + _footer(ctx))
        counts = ", ".join(f"{ui(SECTIONS[s][0])}: {len(changes[s])}" for s in SECTIONS if s in changes)
        listed.append(f"- [{ui('patch.title', version=v)}]({rel(page, INDEX)}) <small>({ui('patch.from', old=p['from'])}) {counts}</small>")
    if pages:
        pages[INDEX] = "\n".join([f"# {ui('patch.index')}", "", ui("patch.index_intro"), "", *listed] + _footer(ctx))
    return pages
