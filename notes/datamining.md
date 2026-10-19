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
| `v2.icon.<id>.png`, `v2.mastery.<id>.png` | Node / option icons, 256 px (extracted to `icons/`) |
| `paintedframe.<kind>-<locked\|allocated>.png` | Node frames (`UiKit.NodeFrame`): keystone, notable, mastery-notable, normal, mastery, socket; silver = locked, gold = allocated (extracted to `icons/frame/`) |
| `v2.halo.*`, `v2.crafthalo.*` | Decorative rings drawn around nodes (not extracted) |
| other `*.png`, `*.jpg`, `*.pcm`, `bundle.*` | Jewel/slot art, textures, sounds, Unity asset bundles (not extracted yet) |

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

## Gated nodes

- **`JewelReveal`** (36 in 5.0.10, subject `ThreeFacesOfDelusion`): an empty slot that a
  socketed unique jewel fills (`JewelReveal.cs` swaps in content). Their only text is "Hidden
  until the linked socket holds the chosen jewel…". The wiki leaves them out entirely; the
  content belongs on the jewel's page.
- **`SubclassReveal`** (3 Portal nodes, subject `PathRunereader`): shown only while that
  initiation path is active (`JewelReveal.PathHidden`). Initiation paths (`Subclasses.cs`,
  `@class.<key>.*`) unlock from deeds, e.g. Runereader (`runemaster`): read 50 runestones. Each
  path is also gated by `EarlyAccess.Open("class.<key>")` → `Link.Allowed`, decided at
  runtime. When closed, the game says "{0} will be available in a future version."

## Mastery options as the game shows them

`TreeWindow.MainOptionRow`: the row body is `MasteryPresentation.Body(option)`, which lists the
non-flag stats with their numbers. The option's description is a hover tooltip on its title:
`Told` when the option has extra text, or the flag stats described otherwise. The harness
exports body as `stats` and description as `extra`. Don't show `DescribeAll(mods)` plus `Told`
together: that repeats the same effect twice.

## Tree layout and icons

- Positions are the node `x`, `y` in Unity UI space (**y up**). The viewer flips y.
- Links are quadratic Béziers. The control point is the midpoint plus `linkCurve["a|b"]`, keyed
  by `Tree.LinkKey` (the two ids in ordinal order). Links in `hiddenLinks` are not drawn.
- Node diameters by size (`TreeStyle.Size`): Keystone 58, Notable/Starter 43.8, Socket/Mastery 50,
  Portal 76, Small/Travel 30. Branch colours come from `Tree.cs`.
- Icons: a node/option `icon` of `v2:<id>` is `PassiveTree.v2.icon.<id>.png`, and `v2m:<id>` is
  `PassiveTree.v2.mastery.<id>.png` (`UiKit.V2Art`). About 100 nodes reference an id with no art.
- How the tree window draws a node: a dark backing, then the painted icon cropped to a circle
  (`RoundIconGraphic`; diamond for diamond nodes), inset by 6% of the box for keystones, 2% for
  small passives and 0 for notables. The frame goes on top at box / `FrameRing` (0.82).
  Notables offering a choice use the `mastery-notable` frame.
- Category names come in two cases for the same category ("Armour" / "armour"). Group them
  case-insensitively.
- The node tooltip shows the stat lines and then `Told` in italics, even when they repeat each
  other (e.g. Eternal Pyre). That's the author's text, so we keep it.

## In-game wiki

`Wiki.Terms` (402 in 5.0.10) is a flat list: `Term.Shown` is the title, `Wiki.Article(term)` the
text, which has placeholder values filled in (e.g. fortification numbers) and `<link>` marks
(self-links removed). `Term.Said` gives the inflected forms the game auto-links.
`pt.scale:*` links in stat text are in-game scaling tooltips, not wiki terms.

## Icons: which image the game shows

`TreeWindow` gets a passive node's icon from `UiKit.MasteryIcon` (travel nodes:
`AttributeIcon(-1)`), and an option's from `UiKit.IconByKey`. That's a chain of fallbacks:
`IconRegistry` (keyed art: `v2:`, `v2m:`, `mastery:`, `tree:`…), `ThemeArt` (`v2:`), then
`IconSemantics.Resolve` (semantic mastery art), then `IconMap` atlas tiles by group, name or
stat (`PassiveTree.icons.png`, 128 px, 16 per row; `art5.icon-*` replaces a few tiles).
E.g. "Fists for Tools" has `v2m:newtry-keystone-own13705`, which has no art, so it ends on
atlas tile 29.

These functions build Unity sprites, and no sprite (not even a stand-in) can exist outside the
engine: `UnityEngine.Object`'s static constructor is native. So `harness/icons.py` mirrors the
chain and asks the game's own lookups (`IconRegistry.Has`, `IconSemantics.Resolve`, `IconMap`)
at every step, ending on a resource name. `Env.Headless` can't even be JIT-compiled outside
Unity, so the loaders that check it are mirrored rather than called.

## Craft tree

- Parsed like the passive tree (`CraftTree.SearchNodes` = `TreeRemote.Parse` + `NameKey =
  "craft.<id>"`; nodes named `own123` with nothing in them are `Broken`). It is shown through
  `TreeWindow.CraftTreeModel`: titles `craft.node.<id>.name` ("Path" for travel nodes), a
  profession "shelf" line (`CraftShelf`: the node's or its chunk's profession, else its sector),
  options from `CraftOptionRow` (description = `Told` or what the flag stat does; body = knob
  line + non-flag stats + `CraftMasteries.TryLines`). Options `!CraftMasteries.Works(o)` are
  shown as broken (11 in 5.0.10).
- Loading outside the game: `CraftTree.Load()` first looks for an override under BepInEx's
  `Paths.ConfigPath` (null here → throws). The harness sets `hostText`/`hostHash` (what
  `UseHostText` sets for a server's tree) to the shipped tree instead. `UseHostText` itself
  touches the local player.
- `TreeWindow`'s statics can't be touched at all (its static constructor parses colours with
  native code), so `ProfNames`, `ChunkProf`, `HasKnob` and `KnobIn` are mirrored.
- Art (`TreeWindow.CraftArt`, `CraftNodeArt`): `craftart.*`, `craftmastery.*`,
  `crafttravel.<sector>` images, or tiles of `PassiveTree.craftnodes.atlas.png` (256 px on a
  260 px grid, 13 per row, 2 px padding).
- Craft branches (forge, wood, beast, table, mead, road) aren't `Branch` enum values, so the
  game tints the whole craft tree alike. The viewer's sector colours are the wiki's own choice.

## Reading the mod's code

Decompile with ILSpy's command-line tool. No .NET SDK is needed: download the `ilspycmd` NuGet
package (9.x targets net8.0), unzip it, and run
`dotnet tools/net8.0/any/ilspycmd.dll -p -o .cache/decompiled/<ver> PathOfValheiman.dll`.
Keep the output in `.cache/` (it is the author's code). Useful entry points: `PassiveTree/StatText.cs`
(stat lines), `L.cs` (localization), `TreeRemote.cs` (tree loading), `Node.cs`, `NodeOption.cs`,
`LootAffixes.cs`, `CraftTree.cs`. `SelfTest.cs` is the author's in-game test suite and shows
many expected outputs.
