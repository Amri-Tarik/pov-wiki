"""Just enough of Unity for the mod's item code to run outside the engine.

UnityEngine.Object's static constructor is native, so no Unity object can be compared, named or
created normally here. With these hooks, stand-ins work:
- Object ==, != and bool -> reference checks; Object.name -> a name we registered;
- Valheim's Utils.GetPrefabName(GameObject) -> that name (Utils' static constructor is native too);
- the mod's colour helpers (Rarity.Hex) -> parsed in Python (ColorUtility is native).
Stand-ins are uninitialized instances (no constructor runs) carrying only managed fields.
"""

import clr
from System import AppDomain, Boolean, Func, String
from System.Reflection import BindingFlags
from System.Runtime.CompilerServices import RuntimeHelpers

_ALL = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
_hooks: list = []
_names: dict[int, str] = {}


def _asm(name: str):
    return next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == name)


def install() -> None:
    if _hooks:
        return
    from MonoMod.RuntimeDetour import Hook

    clr.AddReference("UnityEngine.CoreModule")
    import UnityEngine

    obj = clr.GetClrType(UnityEngine.Object)

    def same(a, b) -> bool:
        return (a is None and b is None) or (a is not None and b is not None and RuntimeHelpers.GetHashCode(a) == RuntimeHelpers.GetHashCode(b))

    _hooks.append(Hook(obj.GetMethod("op_Equality", _ALL), Func[UnityEngine.Object, UnityEngine.Object, Boolean](same)))
    _hooks.append(Hook(obj.GetMethod("op_Inequality", _ALL), Func[UnityEngine.Object, UnityEngine.Object, Boolean](lambda a, b: not same(a, b))))
    _hooks.append(Hook(obj.GetMethod("op_Implicit", _ALL), Func[UnityEngine.Object, Boolean](lambda a: a is not None)))
    _hooks.append(Hook(obj.GetProperty("name").GetGetMethod(), Func[UnityEngine.Object, String](name_of)))

    go = clr.GetClrType(UnityEngine.GameObject)
    prefab_name = _asm("assembly_utils").GetType("Utils").GetMethod("GetPrefabName", _ALL, None, [go], None)
    _hooks.append(Hook(prefab_name, Func[UnityEngine.GameObject, String](name_of)))

    def hex_color(h):
        h = (h or "").lstrip("#")
        h = h + "ff" if len(h) == 6 else h
        r, g, b, a = (int(h[i:i + 2], 16) / 255 if len(h) >= i + 2 else 1.0 for i in (0, 2, 4, 6))
        return UnityEngine.Color(r, g, b, a)

    rarity = _asm("PathOfValheiman").GetType("PassiveTree.Rarity")
    _hooks.append(Hook(rarity.GetMethod("Hex", _ALL), Func[String, UnityEngine.Color](hex_color)))


def name_of(o) -> str:
    return _names.get(RuntimeHelpers.GetHashCode(o), "") if o is not None else ""


def stand_in(clr_type, name: str = ""):
    """An uninitialized instance of a Unity type, answering to `name`."""
    o = RuntimeHelpers.GetUninitializedObject(clr_type)
    _names[RuntimeHelpers.GetHashCode(o)] = name
    return o
