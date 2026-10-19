"""Valheim's own item data, read from the local install with UnityPy (no game running).

Valheim keeps its prefabs in asset bundles (valheim_Data/StreamingAssets/SoftRef/Bundles) that
still carry their type trees, so UnityPy can read component data directly:
- items: every prefab with an ItemDrop component -> its ItemData.m_shared (type, skill, damages,
  armour, block, weight, durability, quality, attack, icons...), keyed by prefab name;
- recipes: Recipe objects (item, station, station level, materials);
- localization: the "localization" TextAsset in resources.assets (Valheim's own string table,
  every language);
- status effects items apply (equip, set, attack...): class and fields;
- icons: each item's first icon sprite, as PNG.

This is Iron Gate's data: it stays in .cache/valheim/<build>/, like the mod files.
"""

import csv
import hashlib
import io
import json
import time
from pathlib import Path

from .paths import CACHE

VALHEIM = CACHE / "valheim"


def data_dir() -> Path:
    from .render import valheim_managed

    return valheim_managed().parent  # valheim_Data


def build_key(data: Path) -> str:
    """Changes with every Valheim update: the bundle manifest and the main resources file."""
    h = hashlib.sha1()
    for f in (data / "StreamingAssets/SoftRef/manifest", data / "resources.assets"):
        st = f.stat()
        h.update(f"{f.name}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()[:12]


def latest() -> Path:
    """The extracted data for the installed Valheim (extracting it if needed)."""
    data = data_dir()
    out = VALHEIM / build_key(data)
    if not (out / "items.json").exists():
        extract(data, out)
    return out


def extract(data: Path, out: Path) -> Path:
    import UnityPy
    from UnityPy.classes import PPtr

    t0 = time.time()
    bundles = sorted(p for p in (data / "StreamingAssets/SoftRef/Bundles").iterdir() if p.is_file())
    env = UnityPy.load(*map(str, bundles))
    print(f"valheim: loaded {len(bundles)} bundles in {time.time() - t0:.0f}s")

    names: dict[tuple, str | None] = {}

    def name_of(owner, pptr: dict) -> str | None:
        """Name of what a reference points at: a component's GameObject name, else the object's."""
        if not pptr or not pptr.get("m_PathID"):
            return None
        key = (id(owner.assets_file), pptr["m_FileID"], pptr["m_PathID"])
        if key not in names:
            try:
                target = PPtr(m_FileID=pptr["m_FileID"], m_PathID=pptr["m_PathID"], assetsfile=owner.assets_file).deref()
                obj = target.read()
                go = getattr(obj, "m_GameObject", None)
                names[key] = go.read().m_Name if go is not None and go.m_PathID else getattr(obj, "m_Name", None)
            except Exception:
                names[key] = None
        return names[key]

    def resolve(owner, value):
        """Replace references inside a type tree with the names they point at."""
        if isinstance(value, dict):
            if set(value) == {"m_FileID", "m_PathID"}:
                return name_of(owner, value)
            return {k: resolve(owner, v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(owner, v) for v in value]
        return value

    items, recipes, icon_refs, effects = {}, [], {}, {}

    def keep_effects(owner, shared: dict) -> None:
        """Status effects an item applies (equip, set, attack...): their class and fields."""
        for key, ref in shared.items():
            if not key.endswith("StatusEffect") or not isinstance(ref, dict) or not ref.get("m_PathID"):
                continue
            try:
                target = PPtr(m_FileID=ref["m_FileID"], m_PathID=ref["m_PathID"], assetsfile=owner.assets_file).deref()
                se = target.read()
                if se.m_Name in effects:
                    continue
                script = se.m_Script.read().m_ClassName if se.m_Script and se.m_Script.m_PathID else None
                effects[se.m_Name] = {"class": script, "fields": resolve(target, target.read_typetree())}
            except Exception:
                pass

    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if "m_itemData" in tree:
            prefab = obj.read().m_GameObject.read().m_Name
            if prefab in items:
                continue
            shared = tree["m_itemData"]["m_shared"]
            icon_refs[prefab] = (obj, (shared.get("m_icons") or [None])[0])
            keep_effects(obj, shared)
            items[prefab] = resolve(obj, shared)
        elif "m_item" in tree and "m_resources" in tree and "m_craftingStation" in tree:
            item = name_of(obj, tree["m_item"])
            if item is None:
                continue
            recipes.append({
                "item": item,
                "amount": tree.get("m_amount", 1),
                "enabled": bool(tree.get("m_enabled", True)),
                "station": name_of(obj, tree.get("m_craftingStation")),
                "repairStation": name_of(obj, tree.get("m_repairStation")),
                "stationLevel": tree.get("m_minStationLevel", 1),
                "resources": [
                    {"item": name_of(obj, r["m_resItem"]), "amount": r["m_amount"], "perLevel": r["m_amountPerLevel"],
                     "recover": bool(r.get("m_recover", True))}
                    for r in tree["m_resources"] if r["m_resItem"].get("m_PathID")
                ],
            })
    print(f"valheim: {len(items)} items, {len(recipes)} recipes in {time.time() - t0:.0f}s")

    out.mkdir(parents=True, exist_ok=True)
    icons = out / "icons"
    icons.mkdir(exist_ok=True)
    for prefab, (obj, ref) in icon_refs.items():
        if not ref or not ref.get("m_PathID"):
            continue
        try:
            sprite = PPtr(m_FileID=ref["m_FileID"], m_PathID=ref["m_PathID"], assetsfile=obj.assets_file).deref().read()
            sprite.image.save(icons / f"{prefab}.png")
            items[prefab]["icon"] = f"{prefab}.png"
        except Exception:
            pass

    stations = sorted({r["station"] for r in recipes if r["station"]})
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    (out / "effects.json").write_text(json.dumps(effects, ensure_ascii=False), encoding="utf-8")
    (out / "recipes.json").write_text(json.dumps(recipes, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "localization.json").write_text(json.dumps(_localization(data), ensure_ascii=False), encoding="utf-8")
    (out / "build.json").write_text(json.dumps({"key": out.name, "stations": stations, "items": len(items),
                                                "recipes": len(recipes)}, indent=1), encoding="utf-8")
    print(f"valheim: done in {time.time() - t0:.0f}s -> {out}")
    return out


def _localization(data: Path) -> dict[str, dict[str, str]]:
    """Valheim's string table: {language: {key: text}} (keys without the leading "$")."""
    import UnityPy

    env = UnityPy.load(str(data / "resources.assets"))
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        ta = obj.read()
        if ta.m_Name != "localization":
            continue
        raw = ta.m_Script
        text = raw if isinstance(raw, str) else bytes(raw).decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        languages = rows[0][1:]
        table = {lang: {} for lang in languages if lang}
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            for lang, value in zip(languages, row[1:]):
                if lang and value:
                    table[lang][row[0]] = value
        return table
    return {}
