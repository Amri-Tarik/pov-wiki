"""Turn extracted game data into a Zensical site, one build per language.

build/<code>/docs/          hand-written content/ pages + generated pages
build/<code>/zensical.toml  base config + per-language overrides
build/<code>/site/          rendered site, then copied to site/<code>/
"""

import hashlib
import shutil
import subprocess
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import tomllib
import tomli_w

from .data import GameData
from . import icons, seo
from .i18n import Language, Localizer, load_languages
from .pages import GLOBAL, LIST_PAGES, PER_TREE, TREES, Ctx, nav
from .paths import BASE_CONFIG, BUILD, CONTENT, ROOT, SITE


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


def _site_root() -> str:
    return tomllib.loads(BASE_CONFIG.read_text(encoding="utf-8"))["project"]["site_url"].rstrip("/")


def _site_url(lang: Language) -> str:
    return f"{_site_root()}/{lang.code}/"


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
    p["theme"]["custom_dir"] = str(ROOT / "overrides")  # search and link preview tags
    extra = p.setdefault("extra", {})
    extra["pov_root"] = _site_root()
    extra["pov_locale"] = {"ru": "ru_RU"}.get(lang.code, "en_US")
    extra["pov_social_image"] = f"{_site_url(lang)}assets/images/social.png"
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
    print(f"  [{getattr(_current, 'lang', '')}] {time.perf_counter() - start:6.2f}s  {label}")


_current = threading.local()  # the language a build thread works on, for the timings


def build_language(lang: Language, default: Language, enabled: list[Language], data: GameData, render: bool) -> None:
    _current.lang = lang.code
    loc = Localizer(lang, default, data)
    out = BUILD / lang.code
    docs = out / "docs"
    written: set[Path] = set()  # every file this build puts in docs/; the rest is stale

    def put(path: Path, data: bytes) -> None:
        """Write a docs file only when it changed: rewriting thousands of unchanged files (and
        deleting them first) is most of a build's time on Windows."""
        written.add(path)
        if path.suffix == ".md":  # every page gets its own search description
            data = seo.with_description(data.decode("utf-8"), loc.ui("page.seo_fallback"),
                                        path.relative_to(docs).as_posix(), _site_url(lang)).encode("utf-8")
        if path.exists() and path.stat().st_size == len(data) and path.read_bytes() == data:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    with _timed("copy hand-written pages"):
        # Hand-written pages: default language first, then the translated ones on top.
        for source in [CONTENT / default.code] + ([CONTENT / lang.code] if lang.code != default.code else []):
            for f in (f for f in source.rglob("*") if f.is_file()) if source.exists() else []:
                put(docs / f.relative_to(source), f.read_bytes())

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
    from .gear_pages import page_currency, page_jewels, page_uniques
    from .item_pages import page_mods

    jobs += [(gen.__name__, gen, ctxs[0]) for gen in (page_mods, page_bases, page_currency, page_jewels, page_uniques)]
    for label, gen, ctx in jobs:
        with _timed(label):
            for rel, text in gen(ctx).items():
                put(docs / rel, text.encode("utf-8"))
    if art:
        with _timed(f"icons ({len(art.raw)} raw, {len(art.framed)} framed)"):
            written.update(art.write(docs))
    with _timed("remove stale pages"):
        # The site generator builds incrementally (no --clean), so a page that is gone from the
        # docs also has its output removed: <page>.md is <page>/index.html (index.md: index.html).
        for f in [f for f in docs.rglob("*") if f.is_file() and f not in written]:
            rel = f.relative_to(docs)
            built = out / "site" / (rel.with_suffix("") if rel.suffix == ".md" and rel.stem != "index" else rel.parent if rel.suffix == ".md" else rel)
            if rel.suffix == ".md":
                (built / "index.html").unlink(missing_ok=True)
            else:
                built.unlink(missing_ok=True)
            f.unlink()

    _write_config(lang, enabled, loc, out)
    if render:
        with _timed("zensical build"):
            subprocess.run(["zensical", "build", "-f", str(out / "zensical.toml")], check=True)  # incremental
        with _timed("copy to site/"):
            shutil.rmtree(SITE / lang.code, ignore_errors=True)
            shutil.copytree(out / "site", SITE / lang.code)


def build(version: str, only: list[str] | None = None, render: bool = True) -> None:
    default_code, langs = load_languages()
    default = langs[default_code]
    enabled = [x for x in langs.values() if x.enabled]
    targets = [langs[c] for c in only] if only else enabled
    data = GameData(version)
    # Languages build side by side: most of the time is the site generator, a separate process.
    print(f"building {', '.join(lang.code for lang in targets)} from data {version}")
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        for job in [pool.submit(build_language, lang, default, enabled, data, render) for lang in targets]:
            job.result()

    # Site root redirects to the default language.
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={default.code}/">'
        f'<link rel="canonical" href="{default.code}/"><title>Path of Valheiman DB</title>',
        encoding="utf-8",
    )
    site_url = tomllib.loads(BASE_CONFIG.read_text(encoding="utf-8"))["project"]["site_url"]
    seo.write_root(SITE, [x.code for x in enabled], site_url)
