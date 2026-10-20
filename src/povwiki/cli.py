import argparse
import subprocess
from pathlib import Path

from .paths import BUILD


def _extract(source: Path, render: bool) -> None:
    from .extract import extract

    out = extract(source)
    print(f"extracted to {out}")
    from .decompile import decompile

    print(f"decompiled to {decompile(out.name)}")  # for the formula check
    if render:
        from .render import render as render_text

        print(f"rendered to {render_text(out.name)}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="povwiki", description="Path of Valheiman wiki pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="download the latest mod release from hexium, extract and render it")
    p.add_argument("--no-extract", action="store_true", help="download only")
    p.add_argument("--no-render", action="store_true", help="skip rendering game text")

    p = sub.add_parser("extract", help="extract game data from a mod zip or unpacked folder, then render it")
    p.add_argument("source", type=Path)
    p.add_argument("--no-render", action="store_true", help="skip rendering game text")

    p = sub.add_parser("render", help="render game text with the mod's own code (Windows)")
    p.add_argument("--version", help="game data version (default: latest extracted)")
    p.add_argument("--lang", action="append", help="mod language name, e.g. english, or all; repeatable (default: the published languages)")

    sub.add_parser("valheim", help="extract Valheim's item data, recipes, localization and icons from the install")

    p = sub.add_parser("build", help="generate pages and render the site")
    p.add_argument("--version", help="game data version (default: latest extracted)")
    p.add_argument("--lang", action="append", help="language code; repeatable (default: all enabled)")
    p.add_argument("--no-render", action="store_true", help="generate markdown only")

    p = sub.add_parser("formulas", help="check the written-down formulas against the mod's code (formulas/registry.toml)")
    p.add_argument("--version", help="game data version (default: latest extracted)")
    p.add_argument("--accept", nargs="+", metavar="ID", help="record these formulas (or all) as re-checked against this version")

    p = sub.add_parser("patches", help="write down what a version changed since the one before (patches/<version>/); "
                                       "the build does it for the version it builds")
    p.add_argument("--version", help="game data version (default: latest extracted)")

    sub.add_parser("deploy", help="build the site and publish it to GitHub Pages (gh-pages branch)")

    p = sub.add_parser("serve", help="generate pages and live-preview one language (fastest dev loop)")
    p.add_argument("--lang", default="en")

    args = ap.parse_args()

    if args.cmd == "fetch":
        from .fetch import fetch

        archive = fetch()
        if not args.no_extract:
            _extract(archive, render=not args.no_render)
    elif args.cmd == "extract":
        _extract(args.source, render=not args.no_render)
    elif args.cmd == "render":
        from .data import latest_version
        from .render import render

        print(f"rendered to {render(args.version or latest_version(), args.lang)}")
    elif args.cmd == "valheim":
        from .valheim import latest

        print(f"valheim data in {latest()}")
    elif args.cmd == "build":
        from .data import latest_version
        from .generate import build

        build(args.version or latest_version(), args.lang, render=not args.no_render)
    elif args.cmd == "formulas":
        from .data import latest_version
        from .formulas import accept, report

        version = args.version or latest_version()
        if args.accept:
            accept(version, args.accept)
        report(version)
    elif args.cmd == "patches":
        from .data import latest_version
        from .patch_pages import write

        write(args.version or latest_version())
    elif args.cmd == "deploy":
        from .data import latest_version
        from .deploy import deploy
        from .generate import build

        version = latest_version()
        build(version)
        deploy(f"Deploy wiki for Path of Valheiman {version}")
    elif args.cmd == "serve":
        from .data import latest_version
        from .generate import build

        # Markdown only (a couple of seconds); the preview server renders pages itself.
        build(latest_version(), [args.lang], render=False)
        subprocess.run(["zensical", "serve", "-f", str(BUILD / args.lang / "zensical.toml")], check=True)
