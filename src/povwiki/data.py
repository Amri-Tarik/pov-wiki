"""Load one extracted game version."""

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .paths import EXTRACTED


def _version_key(v: str):
    return tuple(int(p) if p.isdigit() else p for p in v.split("."))


def latest_version() -> str:
    versions = [p.name for p in EXTRACTED.glob("*") if (p / "extract.json").exists()]
    if not versions:
        raise SystemExit("No extracted data. Run `povwiki extract <mod.zip>` first.")
    return max(versions, key=_version_key)


@dataclass
class GameData:
    version: str

    @property
    def dir(self) -> Path:
        return EXTRACTED / self.version

    def _json(self, name: str):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    @cached_property
    def meta(self) -> dict:
        return self._json("extract.json")

    @cached_property
    def tree(self) -> dict:
        return self._json("tree.json")

    @cached_property
    def craft_tree(self) -> dict:
        return self._json("crafttree.json")

    @cached_property
    def loot(self) -> dict:
        return self._json("loot.catalog.json")

    def loc_file(self, mod_language: str) -> Path:
        return self.dir / "loc" / f"{mod_language}.txt"

    def rendered(self, mod_language: str) -> dict:
        """Game text rendered by the mod's own code (`povwiki render`)."""
        path = self.dir / "rendered" / f"{mod_language}.json"
        if not path.exists():
            raise SystemExit(f"No rendered text for {mod_language}. Run `povwiki render` first.")
        return json.loads(path.read_text(encoding="utf-8"))
