"""Translation layer.

Two string sources, both chosen per language:
- game text: rendered by the mod's own code (`povwiki render`) for anything the game composes
  (node titles, stat lines), and the mod's localization file (key<TAB>text) for plain keyed
  strings. Generators always look game text up by key or node, never hard-code it.
- wiki text: i18n/ui/<code>.toml (headings, table columns, nav). Missing keys fall back to the
  default language.
"""

import json
import re
import tomllib
from dataclasses import dataclass
from functools import cached_property

from .data import GameData
from .paths import I18N


# Mod language -> Valheim's localization column (Valheim has no Vietnamese: English then).
VALHEIM_LANGUAGES = {
    "english": "English", "french": "French", "spanish": "Spanish", "russian": "Russian", "turkish": "Turkish",
    "portuguese_brazilian": "Portuguese_Brazilian", "portuguese_european": "Portuguese_European",
}
_TOKEN = re.compile(r"\$([A-Za-z0-9_]+)")


@dataclass(frozen=True)
class Language:
    code: str
    mod: str
    name: str
    enabled: bool


def load_languages() -> tuple[str, dict[str, Language]]:
    cfg = tomllib.loads((I18N / "languages.toml").read_text(encoding="utf-8"))
    langs = {code: Language(code=code, **v) for code, v in cfg["languages"].items()}
    return cfg["default"], langs


def parse_mod_strings(text: str) -> dict[str, str]:
    """Parse a mod localization file. An empty right column means "show the key as is"."""
    strings = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        # Later lines win, matching how player override files layer over shipped ones.
        strings[key] = value.replace("\\n", "\n") if value else key
    return strings


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out |= _flatten(v, f"{prefix}{k}.")
        else:
            out[f"{prefix}{k}"] = v
    return out


def _load_ui(code: str) -> dict[str, str]:
    path = I18N / "ui" / f"{code}.toml"
    return _flatten(tomllib.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


class Localizer:
    def __init__(self, lang: Language, default: Language, data: GameData):
        self.lang, self.default, self.data = lang, default, data

    @cached_property
    def game(self) -> dict[str, str]:
        return parse_mod_strings(self.data.loc_file(self.lang.mod).read_text(encoding="utf-8"))

    @cached_property
    def _ui(self) -> dict[str, str]:
        return _load_ui(self.default.code) | _load_ui(self.lang.code)

    def ui(self, key: str, **fmt) -> str:
        """Wiki text, e.g. ui("col.name") or ui("page.data_version", version="5.0.10")."""
        text = self._ui.get(key, key)
        return text.format(**fmt) if fmt else text

    def text(self, key: str, default: str | None = None) -> str:
        """Game text by mod localization key, e.g. text("@stat.ArmorPct.fmt")."""
        return self.game.get(key, key if default is None else default)

    @cached_property
    def nodes(self) -> dict[str, dict]:
        """Tree nodes as the game shows them (title, category, stats, extra, options), by id."""
        return self.data.rendered(self.lang.mod)["nodes"]

    @cached_property
    def craft(self) -> dict:
        """The craft tree as the game shows it: {"nodes": {id: ...}, "sectors": [...]}. Nodes get
        the same shape as passive nodes: their profession line is their category."""
        craft = self.data.rendered(self.lang.mod)["craft"]
        for r in craft["nodes"].values():
            r.setdefault("category", r.get("shelf"))
            r.setdefault("topics", [])
        return craft

    @cached_property
    def loot(self) -> dict:
        """Item mods, essences and the mod's own items (harness/loot.py)."""
        return self.data.rendered(self.lang.mod)["loot"]

    @cached_property
    def gear(self) -> dict:
        """Jewels, unique lines, currency details and the mod's boss names (harness/gear.py)."""
        return self.data.rendered(self.lang.mod).get("gear") or {}

    @cached_property
    def monsters(self) -> dict:
        """Monster modifiers and rarity (harness/monsters.py)."""
        return self.data.rendered(self.lang.mod).get("monsters") or {}

    @cached_property
    def buildings(self) -> list:
        """The mod's buildable pieces (harness/buildings.py)."""
        return self.data.rendered(self.lang.mod).get("buildings") or []

    def creature(self, prefab: str) -> str:
        """A creature's name: the mod's own bosses, else Valheim's (creatures.json)."""
        if prefab in self.gear.get("creatures", {}):
            return self.gear["creatures"][prefab]
        token = (self.valheim or {}).get("creatures", {}).get(prefab, {}).get("name")
        return self.vtext(token) if token else prefab

    @cached_property
    def items(self) -> dict:
        """Valheim items as the mod sees them: tags, defences, crafted item level (harness/items.py)."""
        return self.data.rendered(self.lang.mod).get("items") or {}

    @cached_property
    def valheim(self) -> dict | None:
        """Valheim's own data (`povwiki valheim`): items, recipes, icons folder and its strings in
        this language. None when Valheim isn't installed: item pages are skipped then."""
        from .valheim import latest

        try:
            folder = latest()
        except SystemExit:
            return None
        table = json.loads((folder / "localization.json").read_text(encoding="utf-8"))
        strings = {**table.get("English", {}), **table.get(VALHEIM_LANGUAGES.get(self.lang.mod, "English"), {})}
        return {
            "dir": folder,
            "items": json.loads((folder / "items.json").read_text(encoding="utf-8")),
            "recipes": json.loads((folder / "recipes.json").read_text(encoding="utf-8")),
            "creatures": json.loads((folder / "creatures.json").read_text(encoding="utf-8")),
            **{name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
               for name in ("pieces", "smelters", "pickables")},
            "strings": strings,
        }

    def vtext(self, text: str | None) -> str:
        """A Valheim string with its $tokens translated ("$item_axe_bronze" -> "Bronze Axe")."""
        if not text or self.valheim is None:
            return text or ""
        strings = self.valheim["strings"]
        return _TOKEN.sub(lambda m: strings.get(m.group(1), m.group(0)), text).strip()

    def vkey(self, key: str, default: str | None = None) -> str:
        """A Valheim UI string by key (no "$"), e.g. vkey("item_weight") -> "Weight"."""
        strings = self.valheim["strings"] if self.valheim else {}
        return strings.get(key, default if default is not None else key)

    @cached_property
    def wiki(self) -> dict[str, dict]:
        """The mod's in-game wiki terms (title, text, forms), by slug."""
        return self.data.rendered(self.lang.mod)["wiki"]
