"""Render every tree node and option, per language, as the in-game tooltip shows it.

    python -m povwiki.harness --dll PathOfValheiman.dll --deps dir1;dir2 --out DIR --languages english,french

Writes DIR/<language>.json:
    {"language", "revision", "errors": [...], "nodes": {id: {title, category, topics, stats[], extra[],
     options: [{id, title, stats[], extra[]}]}}}
Text keeps the game's rich-text markup (<link="slug">, <color=...>, <b>); the site generator converts it.
"""

import argparse
import json
from pathlib import Path

from . import clrhost


def _lines(s) -> list[str]:
    return str(s).split("\n") if s else []


def render_tree(data, language: str) -> dict:
    from PassiveTree import L, StatText

    nodes, errors = {}, []
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
                "options": [
                    {
                        "id": o.Id,
                        "title": o.Title,
                        "stats": _lines(StatText.DescribeAll(o.Mods)),
                        "extra": _lines(o.Told),
                    }
                    for o in (n.Options or [])
                ],
            }
        except Exception as ex:  # one bad node must not lose the rest
            errors.append({"node": n.Id, "error": str(ex).split("\n")[0]})
    return {"language": language, "revision": data.Revision, "errors": errors, "nodes": nodes}


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
        print(f"rendered {language}: {len(result['nodes'])} nodes, {len(result['errors'])} errors")


if __name__ == "__main__":
    main()
