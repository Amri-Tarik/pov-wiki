# pov-wiki

**Live site: https://amri-tarik.github.io/pov-wiki/**

A datamined wiki for **[Path of Valheiman](https://valheim.hexium.gg/mods/treextr/PathOfValheiman)**,
the Path of Exile–style passive tree, crafting and loot overhaul for Valheim by **treextr**.
It works like [poedb.tw](https://poedb.tw) for Path of Exile: nobody types pages in by hand.
Every page is generated from the mod's own files, so the wiki matches each release exactly.

> Unofficial fan project. All game data and text belong to the mod author. This repo never
> contains or redistributes the mod itself (see [Licence](#licence)).

## How it works

```
fetch    hexium ──▶ .cache/downloads/*.zip
extract  zip ──▶ .cache/extracted/<ver>/   tree.json, crafttree.json, loot.catalog.json, loc/*.txt
render   mod's own code ──▶ .cache/extracted/<ver>/rendered/<language>.json   node titles + stat lines, as in game
build    ──▶ build/<lang>/ (markdown + config) ──zensical──▶ site/<lang>/
deploy   site/ ──▶ gh-pages branch ──▶ GitHub Pages
```

- **extract**: `PathOfValheiman.dll` embeds its game data as .NET resources (passive tree,
  craft tree, loot/affix catalog, every translation), read with
  [dnfile](https://github.com/malwarefrank/dnfile).
- **render**: stat lines are composed by ~2,000 lines of game code (conditions, subjects,
  conversions…). Instead of re-implementing that, `povwiki render` loads the mod into .NET 8 via
  [pythonnet](https://pythonnet.github.io/) and calls its own tooltip code, in every language.
  The wiki shows exactly what the game shows, and formatter changes in a patch come through by
  themselves.

Details in [notes/datamining.md](notes/datamining.md).

## Quick start

Needs:

- [uv](https://docs.astral.sh/uv/) (installs Python and the dependencies);
- the [.NET 8 runtime](https://dotnet.microsoft.com/download/dotnet/8.0) (for `render`);
- **Valheim** installed through Steam (`render` uses its Unity DLLs; it is found automatically,
  or set `VALHEIM_MANAGED` to `.../Valheim/valheim_Data/Managed`). BepInEx, Jotunn and MonoMod
  are downloaded automatically into `.cache/deps/`.

```sh
uv sync
uv run povwiki fetch            # download the latest release from hexium, extract, render
uv run povwiki build            # all enabled languages -> site/
uv run povwiki serve --lang en  # live preview at http://localhost:8000
uv run povwiki deploy           # build + publish to https://amri-tarik.github.io/pov-wiki/
```

`povwiki extract <zip>` works on any local mod zip instead, e.g. an older version.

Everything runs locally; `deploy` force-pushes the built site to the `gh-pages` branch, which
GitHub Pages serves directly (no Actions). Automated rebuilds on new mod releases would need
Valheim's DLLs in CI (e.g. the free dedicated server via SteamCMD) and come later.

## Layout

| Path | What |
|---|---|
| `src/povwiki/` | Pipeline: `fetch.py`, `extract.py` (DLL → JSON), `render.py` + `harness/` (game text via the mod's code), `data.py`, `i18n.py`, `markup.py` (game rich text → HTML), `generate.py` (pages, nav, config), `deploy.py` |
| `content/<lang>/` | Hand-written pages (home, about) |
| `i18n/languages.toml` | Wiki languages and their mod localization file |
| `i18n/ui/<lang>.toml` | The wiki's own strings (headings, table columns, nav) |
| `zensical.toml` | Base site config; copied per language at build time |
| `notes/` | Developer notes on the data formats |
| `.cache/`, `build/`, `site/` | Mod files, extracted data, build output (all git-ignored) |

## Translations

The site is English-only for now. Translation support is built in:

- **Game text** (node names, stat lines, wiki entries) comes from the mod itself: rendered by
  its own code in each language, or looked up by key in its localization files. A new language
  gets every game string for free (`render` already produces all 8 the mod ships).
- **Wiki text** lives in `i18n/ui/<lang>.toml`. Missing keys fall back to English.
- **Hand-written pages** go in `content/<lang>/`. Missing pages fall back to English.
- Each language builds to its own path (`/en/`, `/fr/`, …), and the theme's language switcher
  appears once more than one language is enabled.

To add a language, set `enabled = true` in `i18n/languages.toml` and add `i18n/ui/<code>.toml`.

## Docs stack

[Zensical](https://zensical.org), the successor to Material for MkDocs from the same team
(Material is now in maintenance mode). Zensical builds static HTML, gives full-text search out of
the box, and uses the same Markdown extensions. Zensical is still 0.0.x, so its version is pinned in
`pyproject.toml`.

## Roadmap

- [x] Repo, pipeline skeleton, DLL data extraction, i18n design
- [x] Stat lines exactly as in game (rendered by the mod's own code)
- [ ] Passive tree: keystones, notables, masteries, keyword/glossary pages (from `@wiki.*`)
- [ ] Craft tree and professions
- [ ] Items: affixes with tiers, weights, level ranges and tag rules; uniques; currency; loot tables
- [ ] Patch diffs between versions
- [x] `povwiki fetch` (latest release from hexium) and local `povwiki deploy`
- [ ] Automated rebuilds on new mod releases (needs Valheim DLLs in CI)

## Licence

Code in this repo: TBD. The mod's [licence](https://valheim.hexium.gg/mods/treextr/PathOfValheiman)
allows reading it and reusing parts with credit. It forbids re-publishing the mod. That is why
mod archives, the DLL and extracted data are git-ignored and fetched at build time. Icons are
drawn for the mod. Ask the author before hosting them here.
