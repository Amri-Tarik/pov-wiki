"""Translation layer.

Two string sources, both chosen per language:
- game text: the mod's own localization file (key<TAB>text), plus the `loc` map inside each tree
  file. Generators always look game text up by key or node, never hard-code it.
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

    def node_name(self, node: dict, tree: dict) -> str:
        """Display name of a tree node. Node names in the tree data are in the author's source
        language; resolve by node id first, then the source text, then the tree's own loc map."""
        if (s := self.game.get(f"@{node['id']}")) is not None:
            return s
        if (s := self.game.get(node["name"])) is not None:
            return s
        return tree.get("loc", {}).get(self.lang.mod, {}).get(node["name"], node["name"])
