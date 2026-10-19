import argparse
import subprocess
from pathlib import Path

from .paths import BUILD


def main() -> None:
    ap = argparse.ArgumentParser(prog="povwiki", description="Path of Valheiman wiki pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="download the latest mod release (not implemented yet)")

    p = sub.add_parser("extract", help="extract game data from a mod zip or unpacked folder")
    p.add_argument("source", type=Path)

    p = sub.add_parser("build", help="generate pages and render the site")
    p.add_argument("--version", help="game data version (default: latest extracted)")
    p.add_argument("--lang", action="append", help="language code; repeatable (default: all enabled)")
    p.add_argument("--no-render", action="store_true", help="generate markdown only")

    p = sub.add_parser("serve", help="live-preview one language (run build first)")
    p.add_argument("--lang", default="en")

    args = ap.parse_args()

    if args.cmd == "fetch":
        # TODO: read the latest version from https://valheim.hexium.gg/mods/treextr/PathOfValheiman
        # and download https://cdn.hexium.gg/upload/1330/<version>.zip into .cache/.
        raise SystemExit("fetch is not implemented yet: download the zip and run `povwiki extract <zip>`.")
    if args.cmd == "extract":
        from .extract import extract

        print(f"extracted to {extract(args.source)}")
    elif args.cmd == "build":
        from .data import latest_version
        from .generate import build

        build(args.version or latest_version(), args.lang, render=not args.no_render)
    elif args.cmd == "serve":
        subprocess.run(["zensical", "serve", "-f", str(BUILD / args.lang / "zensical.toml")], check=True)
