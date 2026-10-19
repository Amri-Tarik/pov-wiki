"""Which image the game shows for a node or option.

The tree window picks a node's icon with UiKit.MasteryIcon / NodeIcon and an option's with
UiKit.IconByKey: a chain of fallbacks (icon registry, painted v2 art, semantic mastery art, atlas
tiles by group / name / stat). Those functions build Unity sprites, which cannot exist outside the
engine (UnityEngine.Object's static constructor is native). So this module mirrors the chain and
resolves to the embedded resource that would have been loaded, asking the game's own lookups
(IconRegistry, IconSemantics, IconMap) for every decision.

Results are resource names ("PassiveTree.v2.icon.fire.png") or "atlas:<index>" for a tile of
PassiveTree.icons.png (128 px tiles, 16 per row). None: the game shows no icon either.
Keep in sync with UiKit.MasteryIcon, NodeIcon, IconByKey, Tile, V2Art and IconRegistry.Get.
"""

from System import AppDomain, Int32
from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


class IconResolver:
    def __init__(self):
        asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
        self.resources = {str(n) for n in asm.GetManifestResourceNames()}
        uikit = asm.GetType("PassiveTree.UI.UiKit")
        self._new_icon_name = uikit.GetMethod("NewIconName", _ANY)
        self._attribute_art = list(uikit.GetField("attributeArt", _ANY).GetValue(None))
        from PassiveTree import IconMap
        from PassiveTree.UI import IconRegistry

        self.map, self.registry = IconMap, IconRegistry
        # IconSemantics is internal: not importable, so call it through reflection.
        self._semantics = asm.GetType("PassiveTree.IconSemantics").GetMethod("Resolve", _ANY)
        self.unsupported: dict[str, int] = {}  # registry prefixes not mirrored yet

    def _resolve_semantic(self, n) -> str | None:
        return self._semantics.Invoke(None, [n])

    def _res(self, name: str) -> str | None:
        return name if name in self.resources else None

    # UiKit.V2Art / ThemeIcon / Tile / AttributeIcon
    def v2(self, kind: str, icon_id: str) -> str | None:
        return self._res(f"PassiveTree.v2.{kind}.{icon_id}.png") if icon_id else None

    def theme(self, icon_id: str) -> str | None:
        return self._res(f"PassiveTree.theme.{icon_id}.png") if icon_id else None

    def tile(self, index: int) -> str:
        name = self._new_icon_name.Invoke(None, [Int32(index)])
        if name is not None and (art := self._res(f"PassiveTree.art5.icon-{name}.png")):
            return art
        return f"atlas:{index}"

    def attribute(self, choice: int = -1) -> str | None:
        i = choice + 1 if 0 <= choice <= 2 else 0
        return self._res(f"PassiveTree.polish3.{self._attribute_art[i]}.png")

    # IconRegistry.Get
    def registered(self, key: str) -> str | None:
        prefix, _, rest = key.partition(":")
        if prefix == "tree":
            ok, index = self.map.ByGroup.TryGetValue(rest, 0)
            return self.tile(index) if ok else None
        simple = {
            "mastery": f"PassiveTree.mastery.{rest}.png",
            "craftbadge": f"PassiveTree.craftbadge.{rest}.png",
            "frame": f"PassiveTree.paintedframe.{rest}.png",
            "attribute": f"PassiveTree.polish3.attribute-{rest}.png",
            "theme": f"PassiveTree.theme.{rest}.png",
            "v2": f"PassiveTree.v2.icon.{rest}.png",
            "v2m": f"PassiveTree.v2.mastery.{rest}.png",
            "v2halo": f"PassiveTree.v2.halo.{rest}.png",
        }
        if prefix in simple:
            return self._res(simple[prefix])
        self.unsupported[prefix] = self.unsupported.get(prefix, 0) + 1
        return None

    def _has(self, key) -> bool:
        return bool(key) and self.registry.Has(key)

    # UiKit.ThemeArt
    def theme_art(self, n) -> str | None:
        icon = n.Icon or ""
        if icon.startswith("v2:"):
            return self.v2("icon", icon[3:])
        if icon.startswith("theme:"):
            return self.theme(icon[6:])
        return None

    # UiKit.NodeIcon
    def node_icon(self, n) -> str | None:
        if self._has(n.Icon):
            return self.registered(n.Icon)
        if art := self.theme_art(n):
            return art
        text = self._resolve_semantic(n)
        if text and text != n.Icon:
            ok, index = self.map.ByGroup.TryGetValue(text, 0)
            if ok:
                return self.tile(index)
        if n.Icon and ":" not in n.Icon:
            ok, index = self.map.ByGroup.TryGetValue(n.Icon, 0)
            if ok:
                return self.tile(index)
        if n.Name:
            ok, index = self.map.ByName.TryGetValue(n.Name, 0)
            if ok:
                return self.tile(index)
        for m in n.Mods:
            ok, index = self.map.ByStat.TryGetValue(m.Key, 0)
            if ok:
                return self.tile(index)
        return None  # UiKit.Icon(n.Icon): only reached for ids nothing above knows

    # UiKit.MasteryIcon
    def mastery_icon(self, n) -> str | None:
        if self._has(n.Icon):
            return self.registered(n.Icon)
        if art := self.theme_art(n):
            return art
        if not n.IsDiamond:
            return self.node_icon(n)
        text = self._resolve_semantic(n)
        if not text:
            return self.node_icon(n)
        return self._res(f"PassiveTree.mastery.{text}.png") or self.node_icon(n)

    def tree_node(self, n) -> str | None:
        """What TreeWindow.DressNode shows for a passive tree node."""
        from PassiveTree import NodeSize

        return self.attribute(-1) if n.Size == NodeSize.Travel else self.mastery_icon(n)

    # UiKit.IconByKey (options)
    def by_key(self, key: str | None) -> str | None:
        if not key:
            return None
        if key.startswith("v2:"):
            return self.v2("icon", key[3:])
        if key.startswith("v2m:"):
            return self.v2("mastery", key[4:])
        if key.startswith("theme:"):
            return self.theme(key[6:])
        if ":" in key:
            return self.registered(key) if self._has(key) else None
        ok, index = self.map.ByGroup.TryGetValue(key, 0)
        return self.tile(index) if ok else None
