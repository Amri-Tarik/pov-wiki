"""Decompile the mod's DLL to C# (ILSpy's command-line tool), for reading its code and for the
formula check (povwiki.formulas).

The decompiler version is pinned: formula fingerprints hash the decompiled text, so a different
ILSpy would change them without the mod changing. Output: .cache/decompiled/<version>/ (the
author's code: it stays in .cache, never in the repo).
"""

import io
import subprocess
import zipfile
from pathlib import Path

from .paths import CACHE, MODS

ILSPY = "9.1.0.7988"  # ilspycmd NuGet package; targets .NET 8
DECOMPILED = CACHE / "decompiled"
_TOOL = CACHE / "deps" / f"ilspycmd-{ILSPY}"


def _ilspy() -> Path:
    dll = _TOOL / "ilspycmd.dll"
    if not dll.exists():
        from .render import _download

        print(f"downloading ilspycmd {ILSPY}")
        zf = zipfile.ZipFile(io.BytesIO(_download(f"https://api.nuget.org/v3-flatcontainer/ilspycmd/{ILSPY}/ilspycmd.{ILSPY}.nupkg")))
        prefix = "tools/net8.0/any/"
        _TOOL.mkdir(parents=True, exist_ok=True)
        for name in zf.namelist():
            if name.startswith(prefix) and not name.endswith("/"):
                target = _TOOL / name.removeprefix(prefix)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))
    return dll


def decompile(version: str, force: bool = False) -> Path:
    """The decompiled C# of a mod version (decompiling it the first time)."""
    out = DECOMPILED / version
    stamp = out / ".ilspy"
    if not force and stamp.exists() and stamp.read_text() == ILSPY:
        return out
    dll = next((MODS / version).rglob("PathOfValheiman.dll"), None)
    if dll is None:
        raise SystemExit(f"no PathOfValheiman.dll for {version} under {MODS / version}")
    print(f"decompiling {version} with ilspycmd {ILSPY}")
    subprocess.run(["dotnet", str(_ilspy()), "-p", "-o", str(out), str(dll)], check=True,
                   stdout=subprocess.DEVNULL)
    stamp.write_text(ILSPY)
    return out
