"""Host PathOfValheiman.dll in .NET 8 (CoreCLR) outside the game.

The mod targets .NET Framework 4.8 under Unity's Mono. CoreCLR runs its managed code fine (it also
has the Span types the formatter uses, which .NET Framework lacks); what cannot run is Unity's
native engine code. The few engine calls the text code touches are shimmed here.
"""

from pathlib import Path

from pythonnet import load

load("coreclr")

import clr  # noqa: E402
from System import AppDomain, Func, Object, String  # noqa: E402
from System.IO import File  # noqa: E402
from System.IO import Path as NetPath  # noqa: E402
from System.Reflection import Assembly, AssemblyName, BindingFlags  # noqa: E402
from System.Runtime.CompilerServices import RuntimeHelpers  # noqa: E402

_dirs: list[str] = []
_hooks: list = []  # keep detours alive
_language = ["English"]


def _resolve(sender, args):
    name = AssemblyName(args.Name).Name
    # Unity ships its own copies of the base class library; the runtime's own must win.
    if name in ("mscorlib", "netstandard") or name.startswith(("System", "Microsoft.")):
        return None
    for d in _dirs:
        path = NetPath.Combine(d, name + ".dll")
        if File.Exists(path):
            return Assembly.LoadFrom(path)
    return None


def boot(mod_dll: Path, dep_dirs: list[Path]) -> None:
    """Load the mod. dep_dirs are searched in order, so newer copies (e.g. MonoMod) go first."""
    _dirs.extend(str(d) for d in dep_dirs)
    AppDomain.CurrentDomain.AssemblyResolve += _resolve
    Assembly.LoadFrom(str(mod_dll))
    _shim_valheim_localization()


def _load(name: str):
    for a in AppDomain.CurrentDomain.GetAssemblies():
        if a.GetName().Name == name:
            return a
    return Assembly.Load(name)  # goes through _resolve


def _shim_valheim_localization() -> None:
    """The mod asks `Localization.instance.GetSelectedLanguage()` in a few places. In game that is
    Valheim's localization singleton; here its getter would boot Valheim's localization from
    Unity assets (native code). Give it an empty instance and answer the language ourselves."""
    loc = _load("assembly_guiutils").GetType("Localization")
    field = loc.GetField("m_instance", BindingFlags.Static | BindingFlags.NonPublic)
    field.SetValue(None, RuntimeHelpers.GetUninitializedObject(loc))

    _load("MonoMod.RuntimeDetour")
    clr.AddReference("MonoMod.RuntimeDetour")
    from MonoMod.RuntimeDetour import Hook

    _hooks.append(Hook(loc.GetMethod("GetSelectedLanguage"), Func[Object, String](lambda self: _language[0])))


def set_language(mod_language: str) -> None:
    """Select a language by the mod's file name (english, portuguese_brazilian, ...)."""
    from PassiveTree import L

    # Valheim's own name for it; the mod only compares it with "English".
    _language[0] = "_".join(p.capitalize() for p in mod_language.split("_"))
    L.Force = mod_language
    L.EnsureLoaded()
