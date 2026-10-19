# Datamining notes

Findings from mod version 5.0.10. Re-check after big releases.

## Where the data is

`plugins/PathOfValheiman/PathOfValheiman.dll` (~175 MB, .NET, ~4.1k types) embeds everything as
manifest resources named `PassiveTree.*`:

| Resource | Content |
|---|---|
| `tree.json.gz` | Passive tree (~4k nodes, ~4.6k links, coordinates, mods, options) |
| `tree-prev.json.gz` | Previous tree revision (used for refunds). Could also serve patch diffs |
| `crafttree.json.gz` | Craft tree (~1k nodes) with sectors, chunks, areas, professions |
| `loot.catalog.json` | Loot generation: rarity by level, ~1.2k affixes with tiers/weights/tags, uniques, currency, drop tables |
| `published.cfg` | Server config defaults (XP curve, etc.) |
| `loc.<language>.txt` | Same as the shipped `Localization/*.txt` |
| `*.png`, `*.jpg`, `*.pcm`, `bundle.*` | Icons, textures, sounds, Unity asset bundles (not extracted yet) |

The `Localization/` folder also ships `template.txt` and `english-for-translators.txt`. Those
two are only in the zip, not in the DLL.

## Localization files

`key<TAB>text`, `#` comments, `\n` for newlines, an empty right column means "show the key".
Duplicate keys exist, and the last one wins. Key namespaces:

- `@<nodeId>` (e.g. `@own13661`): passive node name
- `@name.<slug>`, `@opt.<id>[.extra]`: node names / choice options
- `@stat.<StatId>.fmt|.ability`: stat line template (`{0}` = value) / ability name
- `@attr.<Id>.name|.gen`, `@cond.*`, `@trigger.*`, `@subject.*`, `@tag.*`: building blocks of stat lines
- `@wiki.<slug>.title|.text`: the mod's in-game wiki, with `<link="slug">` cross-links. This
  makes a good glossary/keyword source.
- `@cat.*`, `@branch.*`: categories and branches
- `@craft.*`: craft tree nodes and areas
- `@mod.*`, `@modknob.*`: monster modifiers
- `@class.*`, `@oil.*`, `@rune.*`, `@status.*`, `@power.*`, …: other systems
- plain English or Russian phrases as keys: older interface lines

## Tree data quirks

- Node `name`, `tags`, `topics` are in the author's **Russian** source. Resolve display names by
  `@<id>` first, then the source text as key, then `tree.loc[<language>][<source name>]`.
- The sources can disagree. In 5.0.10, `@own13707` = "Barbed Arrows", but its source name
  `Удар великана` = "Giant's Punch" (it is the fist keystone). `@own11151` = "Featherlight" vs
  "Feather". We use `@<id>` first, since the template documents it as the stable node key. Still
  to confirm in game.
- Placeholder nodes: `name == id` and no mods/options (e.g. `own9390`, `own13713`). Skip them.
- `size`: Root, Starter, Small, Notable, Keystone, Travel, Socket, Portal.
- `branch`: Flesh, Toil, Steel, Eitr, War, Wind, Core.
- `mods[]`: `{stat, value, form?(inc|flat|…), subject?, more?, own?}`. Values are fractions
  (0.1 = 10%). The exact display rules still need to be worked out against in-game tooltips.
