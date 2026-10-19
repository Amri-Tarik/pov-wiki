"""Translation layer.

Two string sources, both chosen per language:
- game text: rendered by the mod's own code (`povwiki render`) for anything the game composes
  (node titles, stat lines), and the mod's localization file (key<TAB>text) for plain keyed
  strings. Generators always look game text up by key or node, never hard-code it.
- wiki text: i18n/ui/<code>.toml (headings, table columns, nav). Missing keys fall back to the
  default language.
"""

import tomllib
from dataclasses import dataclass
from functools import cached_property

from .data import GameData
from .paths import I18N


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
    def wiki(self) -> dict[str, dict]:
        """The mod's in-game wiki terms (title, text, forms), by slug."""
        return self.data.rendered(self.lang.mod)["wiki"]
