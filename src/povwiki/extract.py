"""Pull the data files embedded in PathOfValheiman.dll into .cache/extracted/<version>/.

The DLL carries its game data as .NET manifest resources named `PassiveTree.*`:
tree.json.gz, crafttree.json.gz, loot.catalog.json, published.cfg and loc.<language>.txt, plus the
node and mastery icons (v2.icon.<id>.png, v2.mastery.<id>.png). Other images, sounds and asset
bundles are skipped for now.
"""

import gzip
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import dnfile

from .paths import EXTRACTED, MODS

RESOURCE_PREFIX = "PassiveTree."
ICON_KINDS = ("v2.icon.", "v2.mastery.")  # what a node's "v2:<id>" / "v2m:<id>" icon refers to
DLL_PATH = Path("plugins/PathOfValheiman/PathOfValheiman.dll")


def unpack(archive: Path) -> Path:
    """Unpack a mod zip into .cache/mod/<version>/ and return that folder."""
    with zipfile.ZipFile(archive) as zf:
        version = json.loads(zf.read("manifest.json"))["version_number"]
        dest = MODS / version
        if not (dest / DLL_PATH).exists():
            dest.mkdir(parents=True, exist_ok=True)
            zf.extractall(dest)
    return dest


def extract(source: Path) -> Path:
    """Extract data from a mod zip or an unpacked mod folder. Returns the output folder."""
    mod_dir = unpack(source) if source.is_file() else source
    manifest = json.loads((mod_dir / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version_number"]
    dll = mod_dir / DLL_PATH

    out = EXTRACTED / version
    if out.exists():
        shutil.rmtree(out)
    (out / "loc").mkdir(parents=True)

    written = []
    pe = dnfile.dnPE(str(dll), fast_load=False)
    for res in pe.net.resources:
        name = str(res.name).removeprefix(RESOURCE_PREFIX)
        data = res.data
        if name.startswith("loc.") and name.endswith(".txt"):
            target = out / "loc" / name.removeprefix("loc.")
        elif name.startswith(ICON_KINDS) and name.endswith(".png"):
            kind, icon_id = name.removeprefix("v2.").removesuffix(".png").split(".", 1)
            target = out / "icons" / kind / f"{icon_id}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
        elif name.endswith(".json.gz"):
            target, data = out / name.removesuffix(".gz"), gzip.decompress(data)
        elif name.endswith((".json", ".cfg")):
            target = out / name
        else:
            continue
        target.write_bytes(data)
        written.append(target.relative_to(out).as_posix())

    shutil.copy2(mod_dir / "manifest.json", out / "manifest.json")
    meta = {
        "version": version,
        "extracted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dll": str(dll.resolve()),
        "dll_sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
        "files": sorted(written),
    }
    (out / "extract.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out
