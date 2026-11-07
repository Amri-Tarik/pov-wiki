"""Ascendancy classes (6.0): each class tree as the game shows it, and the paths they belong to.

- Classes (ClassTrees: the embedded classes.json, parsed into tree Nodes with ids "cls:<class>:<node>";
  Subclasses: their title, subtitle and goal as the game words them; TreePaths: the path a class
  belongs to). Each node is rendered like a passive node (title, stat lines, extra text, icon).
- Paths (TreePaths.All): key, name, attribute, and the gate node in the main tree whose sector is
  the path's (TreePaths.GateOf), which the tree viewer uses to place the class circles.
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


def _lines(s) -> list[str]:
    return str(s).split("\n") if s else []


def _no_config_override() -> None:
    """ClassTrees.Load first looks for a classes.json in BepInEx's config folder (a player's own
    override); outside the game Paths.ConfigPath is unset and the lookup throws, so the embedded
    file is never read. Point it at an empty folder."""
    import tempfile

    from System import AppDomain

    paths = next((a.GetType("BepInEx.Paths") for a in AppDomain.CurrentDomain.GetAssemblies()
                  if a.GetType("BepInEx.Paths") is not None), None)
    prop = paths.GetProperty("ConfigPath", _ANY) if paths is not None else None
    if prop is not None and not prop.GetValue(None):
        prop.GetSetMethod(True).Invoke(None, [tempfile.mkdtemp(prefix="povwiki-config-")])


def render_classes(icons, formatted, unformatted, errors: list) -> dict:
    try:
        from PassiveTree import ClassTrees, L, StatText, Subclasses, TreePaths
    except ImportError:  # before 6.0
        return {}
    try:
        _no_config_override()
        ClassTrees.Load()
        subs = {str(d.Key): d for d in Subclasses.All}
        paths = []
        for p in TreePaths.All:
            # The gate (TreePaths.GateOf: the root's neighbour in the path's sector) is found by the
            # site from tree.json: the harness has no live tree.
            paths.append({"key": str(p.Key), "name": str(p.Shown), "attr": str(p.AttrShown), "branch": str(p.Sector)})
        classes = []
        for d in ClassTrees.All:
            s = subs.get(str(d.Key))
            nodes = []
            for cn in d.Nodes:
                n = cn.Node
                try:
                    extra = L.Id(f"{n.Id}.extra", n.Extra) if n.Extra else ""
                    nodes.append({
                        "id": str(n.Id), "local": str(cn.Local), "role": str(cn.Role), "size": str(n.Size),
                        "x": float(n.Pos.x), "y": float(n.Pos.y),
                        "title": str(n.Title), "stats": _lines(StatText.DescribeAll(n.Mods)), "extra": _lines(extra),
                        "unformatted": unformatted(n.Mods, formatted), "icon": icons.tree_node(n),
                    })
                except Exception as ex:  # one bad node must not lose the class
                    errors.append({"class-node": str(n.Id), "error": str(ex).split("\n")[0]})
            classes.append({
                "key": str(d.Key),
                "name": str(s.Shown) if s is not None else str(d.Name),
                "sub": str(s.Said) if s is not None else str(d.Sub),
                "goal": str(s.Asked) if s is not None else "",
                "path": str((s.Path if s is not None else None) or d.Path or ""),
                "access": str(d.Access),  # "common" or "subscription" (early access through PoV Link)
                "public": bool(Subclasses.Public(s)) if s is not None else str(d.Access) == "common",
                "art": str(d.Art),
                "nodes": nodes,
                "links": [[str(kv.Key), str(kv.Value)] for kv in d.Links],
            })
        return {"classes": classes, "paths": paths, "points": int(ClassTrees.Of(classes[0]["key"]).Points) if classes else 0}
    except Exception as ex:
        errors.append({"classes": str(ex).split("\n")[0]})
        return {}
