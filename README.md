# pov-wiki

A datamined wiki for **[Path of Valheiman](https://valheim.hexium.gg/mods/treextr/PathOfValheiman)**,
the Path of Exile–style passive tree, crafting and loot overhaul for Valheim by **treextr**.
It works like [poedb.tw](https://poedb.tw) for Path of Exile: nobody types pages in by hand.
Every page is generated from the mod's own files, so the wiki matches each release exactly.

> Unofficial fan project. All game data and text belong to the mod author. This repo never
> contains or redistributes the mod itself (see [Licence](#licence)).

## How it works

```
mod zip ──fetch──▶ .cache/mod/<ver>/ ──extract──▶ .cache/extracted/<ver>/ ──build──▶ build/<lang>/ ──zensical──▶ site/<lang>/
                   (unpacked, ignored)            tree.json, crafttree.json,          docs + config        (GitHub Pages)
                                                  loot.catalog.json, loc/*.txt
```

`PathOfValheiman.dll` embeds its game data as .NET resources: the passive tree, the craft tree,
the loot/affix catalog and every translation. `povwiki extract` reads them with
[dnfile](https://github.com/malwarefrank/dnfile). No decompiler needed. See
[notes/datamining.md](notes/datamining.md) for the formats.

## Quick start

Needs [uv](https://docs.astral.sh/uv/). It installs Python and the dependencies.

```sh
uv sync
uv run povwiki fetch            # download the latest release from hexium + extract
uv run povwiki build            # all enabled languages -> site/
uv run povwiki serve --lang en  # live preview at http://localhost:8000
```

`povwiki extract <zip>` works on any local mod zip instead, e.g. an older version.

Deploys run on GitHub Actions on every push to `main` and once a day, so a new mod release is
picked up automatically. Site: https://amri-tarik.github.io/pov-wiki/

## Layout

| Path | What |
|---|---|
| `src/povwiki/` | Pipeline: `extract.py` (DLL → JSON), `data.py` (load a version), `i18n.py` (strings), `generate.py` (pages, nav, config) |
| `content/<lang>/` | Hand-written pages (home, about) |
| `i18n/languages.toml` | Wiki languages and their mod localization file |
| `i18n/ui/<lang>.toml` | The wiki's own strings (headings, table columns, nav) |
| `zensical.toml` | Base site config; copied per language at build time |
| `notes/` | Developer notes on the data formats |
| `.cache/`, `build/`, `site/` | Mod files, extracted data, build output (all git-ignored) |

## Translations

The site is English-only for now. Translation support is built in:

- **Game text** (node names, stat lines, wiki entries) always comes from the mod's own
  localization files, looked up by key. A new language gets every game string for free.
- **Wiki text** lives in `i18n/ui/<lang>.toml`. Missing keys fall back to English.
- **Hand-written pages** go in `content/<lang>/`. Missing pages fall back to English.
- Each language builds to its own path (`/en/`, `/fr/`, …), and the theme's language switcher
  appears once more than one language is enabled.

To add a language, set `enabled = true` in `i18n/languages.toml` and add `i18n/ui/<code>.toml`.

## Docs stack

[Zensical](https://zensical.org), the successor to Material for MkDocs from the same team
(Material is now in maintenance mode). Zensical builds static HTML, gives full-text search out of
the box, uses the same Markdown extensions, and deploys to GitHub Pages from
`.github/workflows/pages.yml`. Zensical is still 0.0.x, so its version is pinned in
`pyproject.toml`.

## Roadmap

- [x] Repo, pipeline skeleton, DLL data extraction, i18n design
- [ ] Stat line formatting (`@stat.<Id>.fmt` + value rules) so nodes read like in game
- [ ] Passive tree: keystones, notables, masteries, keyword/glossary pages (from `@wiki.*`)
- [ ] Craft tree and professions
- [ ] Items: affixes with tiers, weights, level ranges and tag rules; uniques; currency; loot tables
- [ ] Patch diffs between versions
- [x] `povwiki fetch` + scheduled CI to rebuild on each new mod release

## Licence

Code in this repo: TBD. The mod's [licence](https://valheim.hexium.gg/mods/treextr/PathOfValheiman)
allows reading it and reusing parts with credit. It forbids re-publishing the mod. That is why
mod archives, the DLL and extracted data are git-ignored and fetched at build time. Icons are
drawn for the mod. Ask the author before hosting them here.
