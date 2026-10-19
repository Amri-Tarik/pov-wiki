"""Node and mastery icons: resolve a game icon id, and write the ones the site uses as small WebP.

A node or option's `icon` is "v2:<id>" (UiKit.V2Art("icon", id)) or "v2m:<id>" (mastery art);
both are PNGs embedded in the DLL, extracted to .cache/extracted/<ver>/icons/<kind>/<id>.png.
"""

import tomllib
from pathlib import Path

from PIL import Image

from .data import GameData
from .paths import ROOT

DOCS_DIR = "assets/icons"
SIZE = 96  # px; shown at 24-64 px, with headroom for high-DPI screens
_KINDS = {"v2": "icon", "v2m": "mastery"}


def enabled() -> bool:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return cfg.get("tool", {}).get("povwiki", {}).get("icons", False)


class Icons:
    def __init__(self, data: GameData):
        self.src = data.dir / "icons"
        self.used: set[str] = set()

    def path(self, key: str | None) -> str | None:
        """Docs-relative path of the icon for a game icon id, or None if the game has no such art."""
        if not key or ":" not in key:
            return None
        prefix, icon_id = key.split(":", 1)
        kind = _KINDS.get(prefix)
        if not kind or not (self.src / kind / f"{icon_id}.png").exists():
            return None
        rel = f"{kind}/{icon_id}.webp"
        self.used.add(rel)
        return f"{DOCS_DIR}/{rel}"

    def write(self, docs: Path) -> None:
        for rel in sorted(self.used):
            target = docs / DOCS_DIR / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(self.src / rel.replace(".webp", ".png")) as im:
                im.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS).save(target, "WEBP", quality=85, method=6)
