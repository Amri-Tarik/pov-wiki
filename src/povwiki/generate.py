"""Turn extracted game data into a Zensical site, one build per language.

build/<code>/docs/          hand-written content/ pages + generated pages
build/<code>/zensical.toml  base config + per-language overrides
build/<code>/site/          rendered site, then copied to site/<code>/
"""

import hashlib
import shutil
import subprocess
import time
from contextlib import contextmanager
import tomllib
import tomli_w

from .data import GameData
from . import icons
from .i18n import Language, Localizer, load_languages
from .pages import GLOBAL, LIST_PAGES, PER_TREE, TREES, Ctx, nav
from .paths import BASE_CONFIG, BUILD, CONTENT, SITE


# ---- Build -------------------------------------------------------------------------------------


def _nav(items, loc: Localizer) -> list:
    return [{loc.ui(key): _nav(target, loc) if isinstance(target, list) else target} for key, target in items]


def _versioned(paths: list[str], docs) -> list[str]:
    """Append a content hash to our own CSS/JS URLs, so browsers never run a stale copy after a
    deploy (GitHub Pages lets them cache files for 10 minutes)."""
    out = []
    for path in paths:
        f = docs / path
        out.append(f"{path}?v={hashlib.sha256(f.read_bytes()).hexdigest()[:10]}" if f.exists() else path)
    return out


def _write_config(lang: Language, enabled: list[Language], loc: Localizer, out) -> None:
    cfg = tomllib.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    p = cfg["project"]
    for key in ("extra_css", "extra_javascript"):
        if key in p:
            p[key] = _versioned(p[key], out / "docs")
    p["docs_dir"] = "docs"
    p["site_dir"] = "site"  # Zensical requires it inside the config folder; copied to SITE after
    if p.get("site_url"):
        p["site_url"] = p["site_url"].rstrip("/") + f"/{lang.code}/"
    p["theme"]["language"] = lang.code
    p["nav"] = _nav(nav(), loc)
    if len(enabled) > 1:
        p.setdefault("extra", {})["alternate"] = [
            {"name": o.name, "link": f"../{o.code}/", "lang": o.code} for o in enabled
        ]
    (out / "zensical.toml").write_text(tomli_w.dumps(cfg), encoding="utf-8")


@contextmanager
def _timed(label: str):
    """Print how long a build step took, to see where build time goes."""
    start = time.perf_counter()
    yield
    print(f"  {time.perf_counter() - start:6.2f}s  {label}")


def build_language(lang: Language, default: Language, enabled: list[Language], data: GameData, render: bool) -> None:
    loc = Localizer(lang, default, data)
    out = BUILD / lang.code
    docs = out / "docs"
    with _timed("clean + copy hand-written pages"):
        shutil.rmtree(out, ignore_errors=True)
        # Hand-written pages: default language first, then the translated ones on top.
        shutil.copytree(CONTENT / default.code, docs)
        if lang.code != default.code and (CONTENT / lang.code).exists():
            shutil.copytree(CONTENT / lang.code, docs, dirs_exist_ok=True)

    art = icons.Icons(data, loc.valheim["dir"] if loc.valheim else None) if icons.enabled() else None
    ctxs = [Ctx(data=data, loc=loc, spec=spec, icons=art) for spec in TREES]
    ctxs[0].others = ctxs[1:]
    with _timed("load rendered game text"):
        for ctx in ctxs:  # warm the caches, so generator timings are their own
            ctx.tree_nodes  # noqa: B018
            ctx.option_groups  # noqa: B018
    jobs = [(f"{gen.__name__} [{ctx.spec.key}]", gen, ctx)
            for ctx in ctxs for gen in [LIST_PAGES[p] for p in ctx.spec.pages] + PER_TREE]
    jobs += [(gen.__name__, gen, ctxs[0]) for gen in GLOBAL]
    from .base_pages import page_bases
    from .item_pages import page_mods

    jobs += [("page_mods", page_mods, ctxs[0]), ("page_bases", page_bases, ctxs[0])]
    for label, gen, ctx in jobs:
        with _timed(label):
            for rel, text in gen(ctx).items():
                path = docs / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if art:
        with _timed(f"icons ({len(art.raw)} raw, {len(art.framed)} framed)"):
            art.write(docs)

    _write_config(lang, enabled, loc, out)
    if render:
        with _timed("zensical build"):
            subprocess.run(["zensical", "build", "--clean", "-f", str(out / "zensical.toml")], check=True)
        with _timed("copy to site/"):
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
