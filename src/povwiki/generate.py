"""Turn extracted game data into a Zensical site, one build per language.

build/<code>/docs/          hand-written content/ pages + generated pages
build/<code>/zensical.toml  base config + per-language overrides
build/<code>/site/          rendered site, then copied to site/<code>/
"""

import shutil
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass

import tomli_w

from .data import GameData
from .i18n import Language, Localizer, load_languages
from .paths import BASE_CONFIG, BUILD, CONTENT, SITE


@dataclass
class Ctx:
    data: GameData
    loc: Localizer


# ---- Pages -------------------------------------------------------------------------------------


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def _raw_mod(m: dict) -> str:
    flags = [k for k in ("form", "subject") if m.get(k)]
    flags = [f"{k}={m[k]}" for k in flags] + [k for k in ("more", "own") if m.get(k)]
    return f"`{m['stat']}` {m.get('value', '')}" + (f" ({', '.join(flags)})" if flags else "")


def _is_live(node: dict) -> bool:
    """Placeholder nodes in the tree have no effect and their id as name."""
    return bool(node.get("mods") or node.get("options")) or node["name"] != node["id"]


def page_keystones(ctx: Ctx) -> str:
    tree, loc = ctx.data.tree, ctx.loc
    nodes = sorted(
        (n for n in tree["nodes"] if n["size"] == "Keystone" and _is_live(n)),
        key=lambda n: loc.node_name(n, tree),
    )
    lines = [
        f"# {loc.ui('nav.keystones')}",
        "",
        f"!!! warning\n    {loc.ui('page.wip')}",
        "",
        f"| {loc.ui('col.name')} | {loc.ui('col.branch')} | {loc.ui('col.category')} "
        f"| {loc.ui('col.stats')} |",
        "|---|---|---|---|",
    ]
    for n in nodes:
        stats = "<br>".join(_raw_mod(m) for m in n.get("mods") or [])
        lines.append(
            f"| {_cell(loc.node_name(n, tree))} | {_cell(loc.text(f'@branch.{n['branch']}', n['branch']))} "
            f"| {_cell(loc.text(n.get('cat') or '', n.get('cat') or ''))} | {stats} |"
        )
    lines += ["", _version_footer(ctx)]
    return "\n".join(lines) + "\n"


def _version_footer(ctx: Ctx) -> str:
    meta = ctx.data.meta
    return f"<small>{ctx.loc.ui('page.data_version', version=meta['version'], date=meta['extracted'][:10])}</small>"


# Generated page path -> generator.
PAGES: dict[str, Callable[[Ctx], str]] = {
    "passives/keystones.md": page_keystones,
}

# Navigation: (ui title key, page path | children). Titles are translated per language.
NAV = [
    ("nav.home", "index.md"),
    ("nav.passives", [("nav.keystones", "passives/keystones.md")]),
    ("nav.about", "about.md"),
]


# ---- Build -------------------------------------------------------------------------------------


def _nav(items, loc: Localizer) -> list:
    return [{loc.ui(key): _nav(target, loc) if isinstance(target, list) else target} for key, target in items]


def _write_config(lang: Language, enabled: list[Language], loc: Localizer, out) -> None:
    cfg = tomllib.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    p = cfg["project"]
    p["docs_dir"] = "docs"
    p["site_dir"] = "site"  # Zensical requires it inside the config folder; copied to SITE after
    if p.get("site_url"):
        p["site_url"] = p["site_url"].rstrip("/") + f"/{lang.code}/"
    p["theme"]["language"] = lang.code
    p["nav"] = _nav(NAV, loc)
    if len(enabled) > 1:
        p.setdefault("extra", {})["alternate"] = [
            {"name": o.name, "link": f"../{o.code}/", "lang": o.code} for o in enabled
        ]
    (out / "zensical.toml").write_text(tomli_w.dumps(cfg), encoding="utf-8")


def build_language(lang: Language, default: Language, enabled: list[Language], data: GameData, render: bool) -> None:
    loc = Localizer(lang, default, data)
    out = BUILD / lang.code
    docs = out / "docs"
    shutil.rmtree(out, ignore_errors=True)

    # Hand-written pages: default language first, then the translated ones on top.
    shutil.copytree(CONTENT / default.code, docs)
    if lang.code != default.code and (CONTENT / lang.code).exists():
        shutil.copytree(CONTENT / lang.code, docs, dirs_exist_ok=True)

    ctx = Ctx(data=data, loc=loc)
    for rel, gen in PAGES.items():
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(gen(ctx), encoding="utf-8")

    _write_config(lang, enabled, loc, out)
    if render:
        subprocess.run(["zensical", "build", "--clean", "-f", str(out / "zensical.toml")], check=True)
        shutil.rmtree(SITE / lang.code, ignore_errors=True)
        shutil.copytree(out / "site", SITE / lang.code)


def build(version: str, only: list[str] | None = None, render: bool = True) -> None:
    default_code, langs = load_languages()
    default = langs[default_code]
    enabled = [x for x in langs.values() if x.enabled]
    targets = [langs[c] for c in only] if only else enabled
    data = GameData(version)
    for lang in targets:
        print(f"[{lang.code}] building from data {version}")
        build_language(lang, default, enabled, data, render)

    # Site root redirects to the default language.
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={default.code}/">'
        f'<link rel="canonical" href="{default.code}/"><title>Path of Valheiman DB</title>',
        encoding="utf-8",
    )
