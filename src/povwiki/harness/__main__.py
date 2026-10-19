"""Render every tree node and option, per language, as the in-game tooltip shows it.

    python -m povwiki.harness --dll PathOfValheiman.dll --deps dir1;dir2 --out DIR --languages english,french

Writes DIR/<language>.json:
    {"language", "revision", "errors": [...], "nodes": {id: {title, category, topics, stats[], extra[], broken,
     unformatted[], icon, options: [{id, title, stats[], extra[], broken, reserved, unformatted[], icon}]}},
     "wiki": {key: {title, text[], forms[]}}}
icon: the embedded image the game shows ("PassiveTree.v2.icon.fire.png", "atlas:<tile>") or null.
Text keeps the game's rich-text markup (<link="slug">, <color=...>, <b>); the site generator converts it.
"""

import argparse
import json
from pathlib import Path

from . import clrhost


def _lines(s) -> list[str]:
    return str(s).split("\n") if s else []


def _formatted_stats() -> set[str]:
    """Stats the formatter has a text entry for (StatText's private table `I`). Any other stat
    is shown by the game as a generated fallback from its code name: unfinished content."""
    from System import AppDomain
    from System.Reflection import BindingFlags

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    table = asm.GetType("PassiveTree.StatText").GetField("I", BindingFlags.Static | BindingFlags.NonPublic)
    return {str(k) for k in table.GetValue(None).Keys}


def _unformatted(mods, formatted: set[str]) -> list[str]:
    from PassiveTree import Attrs

    return sorted({str(m.Key) for m in mods if str(m.Key) not in formatted and str(Attrs.Canon(m.Key)) not in formatted})


def render_option(o, formatted: set[str], icons) -> dict:
    """As the tree window's option row (TreeWindow.MainOptionRow) shows it: the body lists the
    non-flag stats (MasteryPresentation.Body); the description (the option's own text, or what
    its flag stats do) is the hover tooltip of the option title."""
    from PassiveTree import MasteryPresentation, StatText

    has_flag = any(StatText.IsFlag(m.Key) for m in o.Mods)
    description = (o.Told if o.Extra else StatText.DescribeAll(o.Mods)) if (o.Extra or has_flag) else ""
    return {
        "id": o.Id,
        "title": o.Title,
        "stats": _lines(MasteryPresentation.Body(o, None, None)),
        "extra": _lines(description),
        "broken": bool(o.Broken),
        "reserved": bool(o.Reserved),  # a placeholder slot in the mastery: no effect yet
        "unformatted": _unformatted(o.Mods, formatted),
        "icon": icons.by_key(o.Icon),
    }


def render_tree(data, language: str) -> dict:
    from PassiveTree import L, StatText

    from .icons import IconResolver

    nodes, errors = {}, []
    formatted = _formatted_stats()
    icons = IconResolver()
    for n in data.Nodes:
        try:
            # Same as Node.Description, with stat lines and extra kept apart.
            extra = L.Id(f"{n.Id}.extra" if n.Id else None, n.Extra) if n.Extra else ""
            nodes[n.Id] = {
                "title": n.Title,
                "category": n.DisplayCategory,
                "topics": list(n.Topics),
                "stats": _lines(StatText.DescribeAll(n.Mods)),
                "extra": _lines(extra),
                "broken": bool(n.Broken),
                "unformatted": _unformatted(n.Mods, formatted),
                "icon": icons.tree_node(n),
                "options": [render_option(o, formatted, icons) for o in (n.Options or [])],
            }
        except Exception as ex:  # one bad node must not lose the rest
            errors.append({"node": n.Id, "error": str(ex).split("\n")[0]})
    return {"language": language, "revision": data.Revision, "errors": errors, "nodes": nodes, "wiki": render_wiki(errors)}


def render_wiki(errors: list) -> dict:
    """The mod's in-game wiki: every term as its article shows it (values filled in, links marked)."""
    from PassiveTree import Wiki

    terms = {}
    for t in Wiki.Terms:
        try:
            terms[t.Key] = {"title": t.Shown, "text": _lines(Wiki.Article(t)), "forms": list(t.Said or [])}
        except Exception as ex:
            errors.append({"wiki": t.Key, "error": str(ex).split("\n")[0]})
    return terms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", required=True, type=Path)
    ap.add_argument("--deps", required=True, help="';'-separated DLL folders, in search order")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--languages", required=True, help="','-separated mod language names")
    args = ap.parse_args()

    clrhost.boot(args.dll, [Path(d) for d in args.deps.split(";")])
    from PassiveTree import L, TreeRemote

    ok, data, error = TreeRemote.Parse(TreeRemote.Shipped, None, None)
    if not ok:
        raise SystemExit(f"tree parse failed: {error}")
    L.FromTree(data.Loc)

    args.out.mkdir(parents=True, exist_ok=True)
    for language in args.languages.split(","):
        clrhost.set_language(language)
        result = render_tree(data, language)
        (args.out / f"{language}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"rendered {language}: {len(result['nodes'])} nodes, {len(result['wiki'])} wiki terms, {len(result['errors'])} errors")
        for e in result["errors"][:5]:
            print("  ", e)


if __name__ == "__main__":
    main()
