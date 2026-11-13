"""Decompile the mod's DLL to C# (ILSpy's command-line tool), for reading its code and for the
formula check (povwiki.formulas).

The decompiler version is pinned: formula fingerprints hash the decompiled text, so a different
ILSpy would change them without the mod changing. Output: .cache/decompiled/<version>/ (the
author's code: it stays in .cache, never in the repo).
"""

import io
import subprocess
import tempfile
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
    from .archive import ensure

    if not force and not out.exists() and ensure(version, "decompiled") and stamp.exists() and stamp.read_text() == ILSPY:
        return out  # an old version's code, back from the archive store
    ensure(version, "mod")
    dll = next((MODS / version).rglob("PathOfValheiman.dll"), None)
    if dll is None:
        raise SystemExit(f"no PathOfValheiman.dll for {version} under {MODS / version}")
    print(f"decompiling {version} with ilspycmd {ILSPY}")
    run = ["dotnet", str(_ilspy()), "-p", "-o", str(out)]
    if subprocess.run([*run, str(dll)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        # ILSpy stops the whole project on one method it can't decompile (6.0.9: a method of the
        # mod's in-game self test). Decompile a copy whose self-test methods are emptied instead:
        # nothing the wiki reads lives there, and every other type comes out as it is.
        print(f"ilspycmd failed on {version}; decompiling again without the self test")
        with tempfile.TemporaryDirectory() as tmp:
            stripped = Path(tmp) / dll.name
            _without_self_test(dll, stripped)
            subprocess.run([*run, str(stripped)], check=True, stdout=subprocess.DEVNULL)
    stamp.write_text(ILSPY)
    return out


_STRIP = r"""
import sys
from pythonnet import load
load("coreclr")
import clr
clr.AddReference(sys.argv[1])
from Mono.Cecil import DefaultAssemblyResolver, ModuleDefinition, ReaderParameters
from Mono.Cecil.Cil import OpCodes

resolver = DefaultAssemblyResolver()
for d in sys.argv[4:]:
    resolver.AddSearchDirectory(d)
params = ReaderParameters()
params.AssemblyResolver = resolver
module = ModuleDefinition.ReadModule(sys.argv[2], params)
def walk(types):
    for t in types:
        yield t
        yield from walk(t.NestedTypes)
emptied = 0
for t in walk(module.Types):
    if t.FullName == "PassiveTree.SelfTest" or t.FullName.startswith("PassiveTree.SelfTest/"):
        for m in t.Methods:
            if m.HasBody:
                body = m.Body
                body.Instructions.Clear(); body.ExceptionHandlers.Clear(); body.Variables.Clear()
                il = body.GetILProcessor()
                il.Append(il.Create(OpCodes.Ldnull)); il.Append(il.Create(OpCodes.Throw))
                emptied += 1
module.Write(sys.argv[3])
print(f"emptied {emptied} self-test methods")
"""


def _without_self_test(dll: Path, out: Path) -> None:
    """A copy of the mod's DLL with the bodies of PassiveTree.SelfTest (and its nested types)
    replaced by `throw null` (Mono.Cecil, the copy shipped with ilspycmd)."""
    import sys

    from .render import valheim_managed

    # Where the types it refers to live (writing resolves enum constants): Valheim and Unity, the
    # mod's own folder, and its dependencies (BepInEx, Jotunn, MonoMod).
    dirs = {str(dll.parent), str(valheim_managed())}
    dirs |= {str(f.parent) for f in (CACHE / "deps").rglob("*.dll") if not f.is_relative_to(_TOOL)}
    subprocess.run([sys.executable, "-I", "-c", _STRIP, str(_TOOL / "Mono.Cecil.dll"), str(dll), str(out), *sorted(dirs)],
                   check=True)


def valheim_type(type_name: str) -> Path:
    """One type of Valheim's own code (assembly_valheim.dll of the installed game), decompiled to
    .cache/decompiled/valheim-<build>/<Type>.cs: for formulas that run through Valheim's code
    (armour). Keyed by the Valheim build, so an update decompiles it again."""
    from .render import valheim_managed
    from .valheim import build_key

    managed = valheim_managed()
    out = DECOMPILED / f"valheim-{build_key(managed.parent)}" / f"{type_name}.cs"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["dotnet", str(_ilspy()), "-t", type_name, str(managed / "assembly_valheim.dll")],
                                check=True, capture_output=True, text=True, encoding="utf-8")
        out.write_text(result.stdout, encoding="utf-8")
    return out
