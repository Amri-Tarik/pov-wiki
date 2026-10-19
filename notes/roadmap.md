# Roadmap and working notes

Status (2026-10-19): live at https://povdb.wiki/ (English and Russian), data from Path of
Valheiman 5.1.0.

Built so far:

- **Passive tree:** viewer, keystones, notables, masteries and node pages.
- **Crafting:** craft tree viewer, professions with areas and stages, craft quests, craft
  notables and masteries.
- **Items:** mods, item bases (with mod pools and implicits), currency, jewels and uniques.
- **Keywords:** the mod's in-game wiki. Each page links to the tree nodes, item mods and uniques
  that mention it.

## How we work

- **Every change is checked locally before it goes live.** Build, open the local preview (serve
  `site/`, e.g. `uv run python -m http.server 8000 --directory site`), and get the maintainer's
  go-ahead first. Only then `git push` to `main` or `uv run povwiki deploy`. Local commits are
  fine.
- **Repository rules** (GitHub rulesets):
  - `main` takes changes through pull requests reviewed by the code owner
    (`.github/CODEOWNERS`).
  - `gh-pages` only changes through `povwiki deploy`.
  - Repository admins bypass both rules.
- **Domain:** `povdb.wiki` is registered at Porkbun and paid with PayPal. PayPal can't
  auto-renew, so **renew it by hand before it expires** (about $26/year after the first year).
  DNS uses GitHub Pages' A/AAAA records plus `www` → `amri-tarik.github.io`. The domain is
  verified in the GitHub account settings. `zensical.toml` `site_url` drives the `CNAME` file
  that every deploy writes.
- **Build speed:**
  - `povwiki render` only renders the published languages, in parallel (`--lang all` for every
    language the mod ships).
  - `povwiki build` writes docs incrementally and lets the site generator rebuild incrementally.
  - Every step prints its time; keep an eye on them.

## Next ideas

In rough order of value for effort.

### Small, high value

1. **Patch history on each page.** At the bottom of each page, a collapsed "History" listing what
   changed in each mod version (e.g. "5.1.0: Seidr Chant — new line: 12.5% increased maximum
   eitr"), plus "Added in 5.1.0" for new content. Optionally a "Patch 5.1.0" page listing every
   changed page by section.
   - How:
     1. Generate every page for the previous and the new version (each extracted version stays in
        `.cache/extracted/<ver>/`).
     2. Compare the pages without the footer.
     3. Store the differences in a committed `changelog/` file, so history survives cache cleanups
        and each patch is computed once.
   - Re-render 5.0.10 with the current harness first, so the first comparison shows game changes,
     not pipeline changes.
2. **Faster deploy.** `povwiki deploy` takes about 3 minutes. It probably rebuilds from scratch
   and pushes thousands of files from a fresh repository each time. Profile it, reuse the last
   build, and push only what changed.
3. **"What can roll at my level" filter.** On mod and item base pages, pick a biome or item level
   and hide the mods and tiers that can't roll there yet. A small script on data already in the
   pages.

### Medium

4. **Drop pages by biome and creature.** What each boss and biome can drop: essences, jewels,
   uniques, currency. Sources: `LootCatalog.Tables`, `Uniques`, `Currency`, `Sources`; boss names
   already come from `creatures.json` and the mod's own names (`gear.creatures`).
5. **Boss sigils.** Their powers and how they work (`BossSigils.Describe`/`Row`,
   `BossSigilPowers`). Their currency pages only show the basics today.
6. **Translation gaps report.** A page or file listing the mod's untranslated strings, by
   language, to pass on to the mod author. For example, the Russian file has no craft node or
   craft mastery text, and no ring text at all in 5.1.0.

### Big

7. **Build planner.** Allocate nodes in the tree viewer, see the summed stats, share a link. This
   is what makes poedb-style sites sticky; a real project.

## Known data quirks (reported as the game has them)

- **Upgrade items in item levels.** `CraftLevel` counts upgrade items (`Upgrader*`, `Mold*`) as
  Deep North material, so most crafted gear gets item level 246. The wiki shows the computed
  level without comment, and lists bases in the order of their other materials.
  `CraftEquipmentRules` ignores those items, so this may be unintended; the code alone can't
  confirm it.
- **Unfinished jewels.** Five jewel kinds (Ember Heart, Frost Fang, Ashen Crown, Runic
  Saturation, Crown of the Imagined Sovereign) have no type and no lines. They're marked
  unimplemented.

## Handoff for a designer

The look lives in a few files. None of them touch the data pipeline.

- `content/en/stylesheets/pov.css`: the site's own styles:
  - keyword underline and hover;
  - "Unimplemented" badges;
  - icon frames and sizes (`.pov-art`);
  - tables;
  - the tree viewer frame;
  - light-mode colours: page `--md-default-bg-color`, code `--md-code-bg-color`, tree canvas
    `--pov-tree-bg`.
- `zensical.toml`: theme settings: colour palettes (light and dark), fonts, icons, logo, features.
  The build copies it per language; don't put `nav` here (it is generated).
- `content/en/javascripts/tree.js`: how the tree viewers draw. Colours come from CSS variables
  (`--pov-tree-bg`, the theme's foreground and accent); branch colours come from the game data.
- Hand-written pages: `content/<lang>/index.md` and `about.md`.
- Images: node art and in-game frames are generated from the game files into
  `assets/icons/` (`src/povwiki/icons.py`). Don't edit the generated files; change the settings
  there instead.

Preview loop: `uv run povwiki build` (about 30 s), then serve `site/` and refresh. Wiki text
(headings, labels) is in `i18n/ui/<lang>.toml`; game text comes from the mod itself and must not
be edited by hand.
