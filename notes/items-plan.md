# Items: plan

Status: plan (2026-10-19), nothing built yet. Goal: a poedb-style Items section. It covers mods
(affixes), item classes and their mod pools, a page per item base, then uniques, currency, jewels
and loot tables.

## What the data looks like

### From the mod (DLL), no game needed

- `loot.catalog.json` (embedded): 1,239 affixes. Each has an id, prefix/suffix, display text,
  target (character, local or activation), families, a group (only one affix per group on an
  item), weight, stat templates (`mods`), and 1–6 tiers. Each tier has a value range, step, item
  level range and weight. Tag rules: `allowAll`, `allowAny`, `denyAny`. 32 affixes are not used
  for generation; there are also `legacyAffixes`. The catalog also has `uniques` and
  `uniqueItems` (unique lines), `currency` (runes, essences), boss `tables`, `sources`,
  `rarityByLevel`, `affixCount` and `lootExclude` (Valheim prefabs never rolled as loot).
- Code (`PassiveTree.Loot`):
  - `ItemTags.Build(ItemData)`: an item's tags, computed from Valheim's item data. Item type gives
    `weapon`, `armour`, `slot.*`, `shield`, `tool`, `trinket`. Weapon profile gives `kind.<Skill>`,
    `one_handed`, `two_handed`, `paired`, `ranged`, `spell`, `melee`. Damage types give
    `damage.*`; attack costs give `uses.*`; block and parry give `can_*`. Armour values give the
    defence types `def.armour`, `def.evasion`, `def.rune_shield`. Shield kind (`tower`, `buckler`,
    `round`) comes partly from the prefab name. Mod items: `jewel.<attr>`, `belt`, `quiver`,
    `jewellery`.
  - `AffixDef.Fits(tags, itemLevel)`: eligibility. It needs the generation flag, the affix level
    range, all `allowAll` tags, at least one `allowAny` tag, no `denyAny` tag, and one tier that
    allows the level.
  - `LootRoller.MultFor` / `SlotMult`: value multiplier by slot. Chest and tower shield ×1.5,
    legs ×0.7, two-handed ×1.5, one-handed ×0.7, buckler ×0.8. Not applied to local or unscaled
    affixes.
  - `CraftLevel.Of`: a crafted item's level, from the biome of its recipe materials (copper and
    bronze → Black Forest, iron → Swamp…).
  - Affix text: `AffixDef.Shown` = `loot.affix.<id>` with `{0}`. Auto-text affixes go through
    `StatText.DescribeMod` (same formatter as the trees).

### From Valheim (the local install), via UnityPy

- `valheim_Data/StreamingAssets/SoftRef/Bundles` (asset bundles; they keep type trees, so no Unity
  needed). Scanning all 802 bundles takes about 26 s and gives:
  - 1,081 item prefabs (`ItemDrop.m_itemData.m_shared`, 134 fields: type, skill, damages per
    quality, armour, block power, parry bonus, weight, durability, max quality, attack costs,
    icons…);
  - 481 recipes (station, level, materials);
  - icons as sprites.
- `resources.assets` → TextAsset `localization`: Valheim's own string table for every language
  (`$item_axe_bronze` → "Bronze axe"…). That makes item names translation-ready the same way as
  the mod's text.
- This is Iron Gate's data: keep it in `.cache/` like the mod files. Same open question as the mod
  art for Valheim's item icons (see below).

## Approach (same as the trees: let the game decide)

1. **`povwiki valheim`**: UnityPy extraction of items, recipes and localization into
   `.cache/valheim/<build id>/` (cached; Valheim updates rarely). Add `UnityPy` as a dependency.
2. **Harness**:
   - Build real `ItemData` / `SharedData` objects from the extracted fields (they are plain
     serializable classes) and call the mod's own `ItemTags.Of(item)`. That gives exact tags per
     base.
   - Unity objects inside (`m_dropPrefab`) can't exist outside the engine, so the two places that
     read the prefab name (tower shields, `CraftLevel`) get mirrored. That's the same pattern as
     the icon chain.
   - Then, per base and item level: eligible affixes (`AffixDef.Fits`), slot multiplier
     (`MultFor`), affix text through the game's own text code.
3. **Pages** are generated from that, with the same rules as now: game text from the game,
   unfinished content badged instead of hidden.

## Site structure: a new "Items" tab

- **Mods** (start here; needs only the mod):
  - Index of all generating affixes, grouped by what they roll on (weapons, armour, shields,
    jewels, trinkets, belts…) and by family. Columns: text, prefix/suffix, tiers, weight.
  - A page per affix:
    - tier table: tier, value range, item levels, weight (and share of the affix's weight);
    - slot multipliers applied, e.g. "on a chest: ×1.5";
    - rules in words ("weapons that are swords or axes, not spells");
    - group (exclusive with), families;
    - the item classes and bases it can roll on.
  - Not generated (`generation: false`) and legacy affixes listed under Unimplemented.
- **Item classes**:
  - weapons by kind (Axes, Swords, Bows, Crossbows, Staffs…);
  - armour by slot × defence type (helmet, chest, legs, cape × armour, evasion, rune shield);
  - shields (round, tower, buckler);
  - tools, trinkets, belts, quivers, jewels (str, dex, int and hybrids), utility.

  Each class page lists its bases and its **mod pool**: prefixes and suffixes that can roll, each
  with its share of the pool's weight at a chosen item level. That's poedb's "mod weights" view.
- **Bases** (a page per Valheim item that can roll mods):
  - icon, name and description (Valheim localization);
  - stats per quality level;
  - recipe, its station and the resulting crafted item level;
  - tags;
  - full mod pool with tier ranges scaled by the slot multiplier;
  - "never dropped as loot" for `lootExclude` items.
- **Uniques**: unique items and their lines (`uniqueItems`), drop sources, min level, weight.
- **Currency**: runes and essences, their effects (`RuneActions`, mod text), drop weights.
- **Loot**: rarity by level, affix count weights, drop sources, boss tables.

## Phases

1. **Mods**: affix index and affix pages. Mod data only, small. Tags shown as readable item
   classes via the wiki's UI strings.
2. **Valheim extraction** + item classes + base pages with stats and recipes.
3. **Mod pools** per class and base, with weights and level-dependent tiers (needs 1 and 2, and
   the harness item-tag step).
4. Uniques, currency, jewels, loot tables.

## Open questions

- Valheim's item icons are Iron Gate's art. Show them (as we do with the mod's art, behind the
  same switch), or text-only bases?
- Which Valheim items count as bases: default to items whose tags make them rollable (weapon,
  armour, shield, tool, trinket, belt, jewel, quiver, utility) and not `lootExclude`; consumables
  and materials only appear inside recipes.
- Item level: tiers depend on it, and it comes from the drop source (creature level, biome) or
  the recipe. Show mod pools at a few reference levels, or by biome?
