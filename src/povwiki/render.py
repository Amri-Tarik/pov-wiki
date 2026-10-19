"""Render game text by running the mod's own formatter (see povwiki.harness).

Needs the .NET 8 runtime and, as DLL dependencies of the mod:
- Valheim's managed DLLs (Unity + assembly_*): found in the Steam library, or set VALHEIM_MANAGED
  to a valheim_Data/Managed folder;
- BepInEx and Jotunn: downloaded from Thunderstore into .cache/deps/;
- MonoMod.RuntimeDetour (to shim engine calls): downloaded from NuGet into .cache/deps/nuget/.
"""

import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from .paths import CACHE, EXTRACTED

DEPS = CACHE / "deps"
BEPINEX_PACK = "denikson-BepInExPack_Valheim-5.4.2351"
# MonoMod.RuntimeDetour and HarmonyX with their dependency closure, for .NET 8.
NUGET = {
    "MonoMod.RuntimeDetour": "25.3.6",
    "MonoMod.Core": "1.3.6",
    "MonoMod.Utils": "25.0.14",
    "MonoMod.Backports": "1.1.2",
    "MonoMod.ILHelpers": "1.1.0",
    "Mono.Cecil": "0.11.6",
    # The mod uses Harmony (AccessTools) outside of patching too; BepInEx's copy can't start on .NET 8.
    "HarmonyX": "2.16.1",
}
NUGET_FRAMEWORKS = ("net8.0", "net7.0", "net6.0", "netstandard2.1", "netstandard2.0")
USER_AGENT = "pov-wiki (+https://github.com/Amri-Tarik/pov-wiki)"


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _steam_libraries() -> list[Path]:
    if os.name != "nt":
        return []
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
        steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
    vdf = (steam / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
    paths = [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', vdf)]
    return [steam, *paths]


def valheim_managed() -> Path:
    if env := os.environ.get("VALHEIM_MANAGED"):
        return Path(env)
    for lib in _steam_libraries():
        for app in ("Valheim", "Valheim dedicated server"):
            managed = lib / "steamapps" / "common" / app / "valheim_Data" / "Managed"
            if (managed / "assembly_valheim.dll").exists():
                return managed
    raise SystemExit("Valheim not found in any Steam library. Set VALHEIM_MANAGED to valheim_Data/Managed.")


def thunderstore(package: str) -> list[Path]:
    """Download a Thunderstore package ("Namespace-Name-Version") once; return its DLL folders."""
    dest = DEPS / package
    if not dest.exists():
        ns, name, ver = package.rsplit("-", 2)
        print(f"downloading {package}")
        zipfile.ZipFile(io.BytesIO(_download(f"https://thunderstore.io/package/download/{ns}/{name}/{ver}/"))).extractall(dest)
    return sorted({p.parent for p in dest.rglob("*.dll")})


def nuget() -> Path:
    """Download the NUGET packages once; return the folder with their DLLs."""
    lib = DEPS / "nuget" / "lib"
    stamp = lib / "packages.json"
    if stamp.exists() and json.loads(stamp.read_text()) == NUGET:
        return lib
    lib.mkdir(parents=True, exist_ok=True)
    for pkg, ver in NUGET.items():
        print(f"downloading {pkg} {ver}")
        p = pkg.lower()
        zf = zipfile.ZipFile(io.BytesIO(_download(f"https://api.nuget.org/v3-flatcontainer/{p}/{ver}/{p}.{ver}.nupkg")))
        names = zf.namelist()
        fw = next(f for f in NUGET_FRAMEWORKS if any(n.startswith(f"lib/{f}/") for n in names))
        for n in names:
            if n.startswith(f"lib/{fw}/") and n.endswith(".dll"):
                (lib / Path(n).name).write_bytes(zf.read(n))
    stamp.write_text(json.dumps(NUGET))
    return lib


def dependency_dirs(version: str) -> list[Path]:
    """DLL folders in search order. NuGet first: BepInEx ships older MonoMod copies."""
    manifest = json.loads((EXTRACTED / version / "manifest.json").read_text(encoding="utf-8"))
    dirs = [nuget(), valheim_managed(), *thunderstore(BEPINEX_PACK)]
    for dep in manifest.get("dependencies", []):
        dirs += thunderstore(dep)
    return dirs


def mod_languages(version: str) -> list[str]:
    return sorted(p.stem for p in (EXTRACTED / version / "loc").glob("*.txt"))


def render(version: str, languages: list[str] | None = None) -> Path:
    out = EXTRACTED / version / "rendered"
    meta = json.loads((EXTRACTED / version / "extract.json").read_text(encoding="utf-8"))
    cmd = [
        sys.executable, "-m", "povwiki.harness",
        "--dll", meta["dll"],
        "--deps", ";".join(str(d) for d in dependency_dirs(version)),
        "--out", str(out),
        "--languages", ",".join(languages or mod_languages(version)),
    ]
    subprocess.run(cmd, check=True)
    return out
