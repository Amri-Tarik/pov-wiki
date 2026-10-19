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

- Node `name`, `tags`, `topics` are in the author's **Russian** source. Don't resolve names by
  hand: `render` gets them from the game's own `Node.Title`. For the record, the game's `L.Id`
  checks the player's override file, then the tree file's `loc` map, then the loc file. So in
  5.0.10 the fist keystone `own13707` shows "Giant's Punch" (from `tree.loc`), even though the loc
  file says `@own13707 Barbed Arrows`.
- Placeholder nodes: `name == id` and no mods/options (e.g. `own9390`, `own13713`). Skip them.
- `size`: Root, Starter, Small, Notable, Keystone, Travel, Socket, Portal.
- `branch`: Flesh, Toil, Steel, Eitr, War, Wind, Core.
- `mods[]`: `{stat, value, form?, subject(s)?, cond?, kind?, per?, threshold?, after?, more?, own?, …}`.
  Values are fractions (0.1 = 10%). Turning them into text takes ~2,000 lines of
  `PassiveTree/StatText.cs`, which is why we run that code instead of porting it.

## Rendering with the mod's code (`povwiki render`)

`src/povwiki/harness/` loads `PathOfValheiman.dll` into **.NET 8 (CoreCLR) via pythonnet** and
calls the same members the in-game tooltip uses: `TreeRemote.Parse(TreeRemote.Shipped)`,
`L.FromTree`, then per language `L.Force = <language>; L.EnsureLoaded()`, and per node
`Node.Title`, `Node.DisplayCategory`, `Node.Topics`, `StatText.DescribeAll(mods)`, plus the
`<id>.extra` text, and `NodeOption.Title` / `Told` for options.

Things learnt getting there:

- The mod targets .NET Framework 4.8, but **Windows PowerShell / .NET Framework can't run it**.
  The formatter uses `System.ReadOnlySpan` (present in Unity's Mono, missing in netfx). CoreCLR
  has it and runs the netfx-targeted code fine.
- Unity's **native** engine code (`ECall` methods) can't run outside the engine. The text code
  only reaches it through Valheim's `Localization.instance` (getter boots from Unity
  `Resources`) and `GetSelectedLanguage()` (→ `PlayerPrefs`). Shims: an uninitialized
  `Localization` put into `m_instance`, and a **MonoMod.RuntimeDetour** hook returning our
  language. pythonnet can't override default interface members, so faking Splatform's
  platform/preferences provider instead doesn't work.
- Assembly resolution: never load Unity's copies of `mscorlib`/`netstandard`/`System.*`.
  Search NuGet's MonoMod first, because BepInEx ships an older MonoMod with the same names.
- Dependencies: Valheim's `valheim_Data/Managed` (Unity + `assembly_*`), BepInExPack and the
  mod's Thunderstore dependencies (Jotunn), and MonoMod from NuGet. All are found or downloaded
  by `povwiki/render.py`.
- Output keeps TextMeshPro markup: `<link="slug">` (slug = `@wiki.<slug>.*` entry) and
  `<color=#hex>`. `markup.py` converts it.

## Unfinished content

The wiki shows it with a badge instead of hiding it. The signals:

- **Placeholder nodes**: no stat lines, no extra text and no options (in 5.0.10: 8 keystones,
  247 notables, often titled "In development" or blank).
- **`Broken`** on a node or option: disabled by the game (none in 5.0.10).
- **Reserved mastery options** (`NodeOption.Reserved`: every stat is `MasterySlot`): the game
  shows "A reserved place in this mastery: it has no effect yet and cannot be chosen" (23 in 5.0.10).
- **Fallback stat text**: a stat with no entry in `StatText`'s private table `I` (nor its
  `Attrs.Canon` form) is printed from its code name, e.g. `+1 reload while moving` for
  `ReloadWhileMoving` on the keystone "On the Move". The harness lists these per node as
  `unformatted`.

## Mastery options as the game shows them

`TreeWindow.MainOptionRow`: the row body is `MasteryPresentation.Body(option)`, which lists the
non-flag stats with their numbers. The option's description is a hover tooltip on its title:
`Told` when the option has extra text, or the flag stats described otherwise. The harness
exports body as `stats` and description as `extra`. Don't show `DescribeAll(mods)` plus `Told`
together: that repeats the same effect twice.

## In-game wiki

`Wiki.Terms` (402 in 5.0.10) is a flat list: `Term.Shown` is the title, `Wiki.Article(term)` the
text, which has placeholder values filled in (e.g. fortification numbers) and `<link>` marks
(self-links removed). `Term.Said` gives the inflected forms the game auto-links.
`pt.scale:*` links in stat text are in-game scaling tooltips, not wiki terms.

## Reading the mod's code

Decompile with ILSpy's command-line tool. No .NET SDK is needed: download the `ilspycmd` NuGet
package (9.x targets net8.0), unzip it, and run
`dotnet tools/net8.0/any/ilspycmd.dll -p -o .cache/decompiled/<ver> PathOfValheiman.dll`.
Keep the output in `.cache/` (it is the author's code). Useful entry points: `PassiveTree/StatText.cs`
(stat lines), `L.cs` (localization), `TreeRemote.cs` (tree loading), `Node.cs`, `NodeOption.cs`,
`LootAffixes.cs`, `CraftTree.cs`. `SelfTest.cs` is the author's in-game test suite and shows
many expected outputs.
