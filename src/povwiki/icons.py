"""Node art: icons and the game's painted frames.

Which image a node or option shows is decided by `povwiki render` (harness/icons.py mirrors the
game's icon chain): an embedded resource name ("PassiveTree.v2.icon.fire.png", extracted to
.cache/extracted/<ver>/images/v2.icon.fire.png), "atlas:<index>", a 128 px tile of the icon atlas
(PassiveTree.icons.png, 16 tiles per row), or "craftatlas:<index>", a 256 px tile of the craft node
atlas (PassiveTree.craftnodes.atlas.png, 13 per row on a 260 px grid). Frames are `paintedframe.<kind>-<locked|allocated>.png`
(UiKit.NodeFrame).

Pages use framed icons composited here the way the tree window draws a node (TreeWindow node
setup): the painted icon cropped to a circle inside the node box, the frame drawn around it at
box / FrameRing (0.82). The tree viewer composes the same layers itself, from the raw icons and
frames, so it can switch between silver (locked) and gold (allocated) frames.
"""

import hashlib
import shutil
import tomllib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw

from .data import GameData
from .paths import ROOT

DOCS_DIR = "assets/icons"
ICON_SIZE = 96  # raw icons for the viewer
FRAMED_SIZE = 160  # framed icons for pages; shown at 56-128 px
FRAME_RING = 0.82  # UiKit.FrameRing: node box / frame size
# Icon inset inside the node box, as a fraction of the box (TreeWindow node setup).
INSET = {"keystone": 0.06, "notable": 0.0, "mastery-notable": 0.0, "normal": 0.02, "mastery": 0.025, "socket": 0.0}
FRAME_KINDS = ("keystone", "notable", "mastery-notable", "normal", "mastery", "socket")
# Atlas id prefix -> (file, tile size, grid step, columns, padding): UiKit.Tile, CraftNodeArt.Get.
ATLASES = {
    "atlas": ("icons.png", 128, 128, 16, 0),
    "craftatlas": ("craftnodes.atlas.png", 256, 260, 13, 2),
}


def enabled() -> bool:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return cfg.get("tool", {}).get("povwiki", {}).get("icons", False)


def frame_kind(size: str, has_options: bool = False) -> str:
    """UiKit.FrameKind, plus the mastery-notable frame for notables that offer a choice."""
    if size == "Notable" and has_options:
        return "mastery-notable"
    return {"Notable": "notable", "Starter": "notable", "Small": "normal", "Travel": "normal",
            "Socket": "socket", "Mastery": "mastery"}.get(size, "keystone")


def _slug(image: str) -> str:
    """Image id -> file stem: "PassiveTree.v2.icon.fire.png" -> "v2.icon.fire", "atlas:29" -> "atlas.29"."""
    prefix, _, index = image.partition(":")
    if prefix in ATLASES or prefix == "vh":
        return f"{prefix}.{index}"
    return image.removeprefix("PassiveTree.").removesuffix(".png")


class Icons:
    def __init__(self, data: GameData, valheim: Path | None = None):
        self.src = data.dir / "images"
        self.valheim = valheim / "icons" if valheim else None  # Valheim item icons: "vh:<prefab>"
        self.raw: set[str] = set()  # image ids
        self.framed: set[tuple[str, str]] = set()  # (image id, frame kind)

    def _exists(self, image: str | None) -> bool:
        if not image:
            return False
        prefix, _, rest = image.partition(":")
        if prefix == "vh":
            return bool(self.valheim) and (self.valheim / f"{rest}.png").exists()
        if prefix in ATLASES:
            return (self.src / ATLASES[prefix][0]).exists()
        return (self.src / image.removeprefix("PassiveTree.")).exists()

    def path(self, image: str | None) -> str | None:
        """Docs path of the raw icon (for the tree viewer), or None when the game shows none."""
        if not self._exists(image):
            return None
        self.raw.add(image)
        return f"{DOCS_DIR}/{_slug(image)}.webp"

    def framed_path(self, image: str | None, kind: str) -> str | None:
        """Docs path of the icon in its gold in-game frame (for pages)."""
        if not self._exists(image):
            return None
        self.framed.add((image, kind))
        return f"{DOCS_DIR}/framed/{kind}/{_slug(image)}.webp"

    @staticmethod
    def frame_path(kind: str, state: str) -> str:
        return f"{DOCS_DIR}/frame/{kind}-{state}.webp"

    def write(self, docs: Path) -> None:
        """Copy the used images into the docs. Images are generated once into a cache next to the
        extracted data (keyed by the settings above) and reused by later builds."""
        cache_dir = self.src.parent / "web" / _settings_key()
        jobs: list[tuple[str, Callable[[], Image.Image]]] = []
        for image in sorted(self.raw):
            jobs.append((f"{_slug(image)}.webp", lambda image=image: self._load(image).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)))
        for kind in FRAME_KINDS:
            for state in ("locked", "allocated"):
                jobs.append((f"frame/{kind}-{state}.webp", lambda kind=kind, state=state: self._frame(kind, state, FRAMED_SIZE * 2)))
        for image, kind in sorted(self.framed):
            jobs.append((f"framed/{kind}/{_slug(image)}.webp", lambda image=image, kind=kind: self._compose(image, kind)))

        def generate(rel: str, make: Callable[[], Image.Image]) -> None:
            cached = cache_dir / rel
            cached.parent.mkdir(parents=True, exist_ok=True)
            make().save(cached, "WEBP", quality=85, method=4)

        # Missing images are made in parallel (Pillow releases the GIL while resizing/encoding).
        missing = [(rel, make) for rel, make in jobs if not (cache_dir / rel).exists()]
        if missing:
            for name in ATLASES:  # load shared images once, before threads race for them
                self._atlas(name)
            for kind in FRAME_KINDS:
                self._frame(kind, "allocated", FRAMED_SIZE * 2)
            with ThreadPoolExecutor() as pool:
                list(pool.map(lambda job: generate(*job), missing))

        out = docs / DOCS_DIR
        for rel, _ in jobs:
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cache_dir / rel, out / rel)

    @cache
    def _atlas(self, name: str) -> Image.Image | None:
        path = self.src / ATLASES[name][0]
        return Image.open(path).convert("RGBA") if path.exists() else None

    def _load(self, image: str) -> Image.Image:
        prefix, _, index = image.partition(":")
        if prefix == "vh":
            with Image.open(self.valheim / f"{index}.png") as im:
                return im.convert("RGBA")
        if prefix in ATLASES:
            _, tile, step, columns, pad = ATLASES[prefix]
            i = int(index)
            x, y = (i % columns) * step + pad, (i // columns) * step + pad  # rows from the top
            return self._atlas(prefix).crop((x, y, x + tile, y + tile))
        with Image.open(self.src / image.removeprefix("PassiveTree.")) as im:
            return im.convert("RGBA")

    @cache
    def _frame(self, kind: str, state: str, size: int) -> Image.Image:
        with Image.open(self.src / f"paintedframe.{kind}-{state}.png") as im:
            return im.convert("RGBA").resize((size, size), Image.LANCZOS)

    def _compose(self, image: str, kind: str) -> Image.Image:
        size = FRAMED_SIZE * 2  # work at 2x, scale down once
        box = size * FRAME_RING
        inset = box * INSET.get(kind, 0)
        icon_px = round(box - 2 * inset)
        canvas = Image.new("RGBA", (size, size))
        icon = self._load(image).resize((icon_px, icon_px), Image.LANCZOS)
        mask = Image.new("L", (icon_px, icon_px))
        ImageDraw.Draw(mask).ellipse((0, 0, icon_px - 1, icon_px - 1), fill=255)
        offset = round((size - icon_px) / 2)
        canvas.paste(icon, (offset, offset), mask)
        canvas.alpha_composite(self._frame(kind, "allocated", size))
        return canvas.resize((FRAMED_SIZE, FRAMED_SIZE), Image.LANCZOS)


def _settings_key() -> str:
    """Changes whenever the way images are made changes, so stale cached images are not reused."""
    settings = repr((3, ICON_SIZE, FRAMED_SIZE, FRAME_RING, sorted(INSET.items()), sorted(ATLASES.items())))
    return hashlib.sha1(settings.encode()).hexdigest()[:10]
