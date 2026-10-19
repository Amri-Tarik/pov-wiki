"""Node art: icons and the game's painted frames.

- A node or option's `icon` is "v2:<id>" (UiKit.V2Art("icon", id)) or "v2m:<id>" (mastery art):
  PNGs embedded in the DLL, extracted to .cache/extracted/<ver>/icons/{icon,mastery}/<id>.png.
- Frames are `paintedframe.<kind>-<locked|allocated>.png` (UiKit.NodeFrame), in icons/frame/.

Pages use framed icons composited here the way the tree window draws a node (TreeWindow node
setup): the painted icon cropped to a circle inside the node box, the frame drawn around it at
box / FrameRing (0.82). The tree viewer composes the same layers itself, from the raw icons and
frames, so it can switch between silver (locked) and gold (allocated) frames.
"""

import tomllib
from pathlib import Path

from PIL import Image, ImageDraw

from .data import GameData
from .paths import ROOT

DOCS_DIR = "assets/icons"
ICON_SIZE = 96  # raw icons for the viewer
FRAMED_SIZE = 112  # framed icons for pages; shown at 32-80 px
FRAME_RING = 0.82  # UiKit.FrameRing: node box / frame size
# Icon inset inside the node box, as a fraction of the box (TreeWindow node setup).
INSET = {"keystone": 0.06, "notable": 0.0, "mastery-notable": 0.0, "normal": 0.02, "mastery": 0.025, "socket": 0.0}
FRAME_KINDS = ("keystone", "notable", "mastery-notable", "normal", "mastery", "socket")
_PREFIX = {"v2": "icon", "v2m": "mastery"}


def enabled() -> bool:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return cfg.get("tool", {}).get("povwiki", {}).get("icons", False)


def frame_kind(size: str, has_options: bool = False) -> str:
    """UiKit.FrameKind, plus the mastery-notable frame for notables that offer a choice."""
    if size == "Notable" and has_options:
        return "mastery-notable"
    return {"Notable": "notable", "Starter": "notable", "Small": "normal", "Travel": "normal",
            "Socket": "socket", "Mastery": "mastery"}.get(size, "keystone")


class Icons:
    def __init__(self, data: GameData):
        self.src = data.dir / "icons"
        self.raw: set[str] = set()  # "icon/<id>"
        self.framed: set[tuple[str, str]] = set()  # ("icon/<id>", frame kind)

    def _source(self, key: str | None) -> str | None:
        if not key or ":" not in key:
            return None
        prefix, icon_id = key.split(":", 1)
        kind = _PREFIX.get(prefix)
        if not kind or not (self.src / kind / f"{icon_id}.png").exists():
            return None
        return f"{kind}/{icon_id}"

    def path(self, key: str | None) -> str | None:
        """Docs path of the raw icon (for the tree viewer), or None if the game has no such art."""
        src = self._source(key)
        if not src:
            return None
        self.raw.add(src)
        return f"{DOCS_DIR}/{src}.webp"

    def framed_path(self, key: str | None, kind: str) -> str | None:
        """Docs path of the icon in its gold in-game frame (for pages)."""
        src = self._source(key)
        if not src:
            return None
        self.framed.add((src, kind))
        return f"{DOCS_DIR}/framed/{kind}/{src}.webp"

    @staticmethod
    def frame_path(kind: str, state: str) -> str:
        return f"{DOCS_DIR}/frame/{kind}-{state}.webp"

    def write(self, docs: Path) -> None:
        out = docs / DOCS_DIR
        for src in sorted(self.raw):
            with Image.open(self.src / f"{src}.png") as im:
                _save(im.convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS), out / f"{src}.webp")
        for kind in FRAME_KINDS:
            for state in ("locked", "allocated"):
                with Image.open(self.src / "frame" / f"{kind}-{state}.png") as im:
                    _save(im.convert("RGBA").resize((FRAMED_SIZE * 2, FRAMED_SIZE * 2), Image.LANCZOS), out / "frame" / f"{kind}-{state}.webp")
        for src, kind in sorted(self.framed):
            _save(self._compose(src, kind), out / "framed" / kind / f"{src}.webp")

    def _compose(self, src: str, kind: str) -> Image.Image:
        size = FRAMED_SIZE * 4  # work large, scale down once
        box = size * FRAME_RING
        inset = box * INSET.get(kind, 0)
        icon_px = round(box - 2 * inset)
        canvas = Image.new("RGBA", (size, size))
        with Image.open(self.src / f"{src}.png") as im:
            icon = im.convert("RGBA").resize((icon_px, icon_px), Image.LANCZOS)
        mask = Image.new("L", (icon_px, icon_px))
        ImageDraw.Draw(mask).ellipse((0, 0, icon_px - 1, icon_px - 1), fill=255)
        offset = round((size - icon_px) / 2)
        canvas.paste(icon, (offset, offset), mask)
        with Image.open(self.src / "frame" / f"{kind}-allocated.png") as fr:
            canvas.alpha_composite(fr.convert("RGBA").resize((size, size), Image.LANCZOS))
        return canvas.resize((FRAMED_SIZE, FRAMED_SIZE), Image.LANCZOS)


def _save(im: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    im.save(target, "WEBP", quality=85, method=6)
