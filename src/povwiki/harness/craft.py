"""Render the craft tree as the tree window shows it (TreeWindow.CraftTreeModel).

Like the passive tree, the craft tree is parsed by TreeRemote.Parse (CraftTree.SearchNodes), but it
is shown through its own model: titles from craft.node.<id>.name ("Path" for travel nodes), a
profession "shelf" line, option rows from TreeWindow.CraftOptionRow, and art from
TreeWindow.CraftArt / CraftNodeArt. Keep in sync with those.

Craft art ids: "PassiveTree.<resource>.png", or "craftatlas:<index>" for a tile of
PassiveTree.craftnodes.atlas.png (256 px tiles on a 260 px grid, 13 per row, 2 px padding).
"""

import math
import re

from System import AppDomain
from System.IO import StreamReader
from System.IO.Compression import CompressionMode, GZipStream
from System.Reflection import BindingFlags
from System.Text import Encoding

from .icons import IconResolver

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic
# TreeWindow.KnobIn: a "{tunable.name}" placeholder (not a "{key.*}" keybinding).
_KNOB = re.compile(r"\{(?!key\.)[a-z][\w.-]*\}")


def _lines(s) -> list[str]:
    return str(s).split("\n") if s else []


class CraftRenderer:
    def __init__(self, icons: IconResolver, formatted: set[str], unformatted):
        from PassiveTree import CraftTree

        asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
        # Load the shipped craft tree the way a server hands it to clients (what UseHostText sets;
        # UseHostText itself also refreshes the local player). The normal path first looks for an
        # override file under BepInEx's config folder, which does not exist outside a game install.
        with asm.GetManifestResourceStream("PassiveTree.crafttree.json.gz") as raw:
            with GZipStream(raw, CompressionMode.Decompress) as gz, StreamReader(gz, Encoding.UTF8) as reader:
                text = reader.ReadToEnd()
        craft_type = asm.GetType("PassiveTree.CraftTree")
        craft_type.GetField("hostText", _ANY).SetValue(None, text)
        craft_type.GetField("hostHash", _ANY).SetValue(None, asm.GetType("PassiveTree.WebConfig").GetMethod("Hash", _ANY).Invoke(None, [text]))
        if not CraftTree.Load():
            raise RuntimeError("craft tree did not load")
        self.tree = CraftTree
        self.icons, self.formatted, self.unformatted = icons, formatted, unformatted
        # TreeWindow's own helpers (ProfNames, ChunkProf, HasKnob, KnobIn) cannot be called: its
        # static constructor parses colours with native Unity code. They are mirrored below.
        art = asm.GetType("PassiveTree.UI.CraftNodeArt")
        self._tiles = art.GetField("Tiles", _ANY).GetValue(None)
        self._travel_sectors = {str(s) for s in art.GetField("TravelSectors", _ANY).GetValue(None)}
        from PassiveTree.UI import CraftNodeArt, IconRegistry

        self.art, self.registry = CraftNodeArt, IconRegistry
        self._own_art = asm.GetType("PassiveTree.UI.IconRegistry").GetField("CraftOwnArt", _ANY).GetValue(None)

    # ---- Art (CraftNodeArt.Get / Travel / TravelOf, TreeWindow.CraftArt / IconOf) ----

    def art_get(self, key) -> str | None:
        if not key:
            return None
        key = str(key)
        if key.startswith("art:"):
            return self.icons._res(f"PassiveTree.craftart.{key[4:]}.png")
        if self._own_art.Contains(key) and (res := self.icons._res(f"PassiveTree.craftmastery.{key}.png")):
            return res
        ok, index = self._tiles.TryGetValue(key, 0)
        return f"craftatlas:{index}" if ok else None

    def travel_of(self, sector) -> str | None:
        if sector not in self._travel_sectors:
            return None
        return self.icons._res(f"PassiveTree.crafttravel.{sector}.png")

    def travel(self, cn) -> str | None:
        sector = cn.Sector
        if sector not in self._travel_sectors:
            # Nearest travel sector by angle (Mathf.Atan2(x, -y), Mathf.DeltaAngle).
            angle = math.degrees(math.atan2(cn.Pos.x, -cn.Pos.y))
            best = math.inf
            for s in self.tree.Sectors:
                if s.Id in self._travel_sectors and not math.isnan(s.Angle):
                    d = abs((s.Angle - angle + 180) % 360 - 180)
                    if d < best:
                        best, sector = d, s.Id
        return self.travel_of(sector)

    def icon_of(self, group, name) -> str | None:
        """TreeWindow.IconOf: NodeIcon of a probe notable with that icon group and name."""
        from PassiveTree import Node, NodeSize

        probe = Node()
        probe.Id, probe.Name, probe.Icon, probe.Size = "craft-probe", name or "", group, NodeSize.Notable
        return self.icons.node_icon(probe)

    def craft_art(self, cn, node) -> str | None:
        from PassiveTree import NodeSize

        if cn.Size == NodeSize.Travel:
            group = self.art.TravelGroup(cn)
            if group and (found := self.icon_of(group, cn.Name)):
                return found
        found = self.art_get(self.art.ArtKey(node, -1) if node is not None else self.art.ArtOfNode(cn.Id))
        if found:
            return found
        if cn.Size == NodeSize.Travel:
            return self.travel(cn)
        if node is None:
            return self.art_get(cn.Icon)
        name = cn.Name or ""
        if node.IsMastery and (cn.Prof == "armorer" or name.startswith(("Tanner ", "Armorer "))):
            return self.art_get("craft-mastery-armorer-tanner-s-rack")
        return self.art_get(self.art.NodeKey(node, -1))

    def node_icon(self, cn, node) -> str | None:
        """What TreeWindow shows for a craft node: CraftArt ?? IconOf(icon, name) ?? AttributeIcon(-1)."""
        return self.craft_art(cn, node) or self.icon_of(cn.Icon, cn.Name) or self.icons.attribute(-1)

    # ---- Text (CraftTreeModel) ----

    def shelf(self, cn) -> str | None:
        """TreeWindow.CraftShelf: the profession (or sector) line above a node's title."""
        from PassiveTree import L

        prof = cn.Prof
        if not prof and cn.Chunk is not None:
            chunk = next((c for c in self.tree.Chunks if c.Id == cn.Chunk), None)
            if chunk is not None:
                prof = self._chunk_prof(chunk)
        if prof:
            return L.Id(f"craft.prof.{prof}", prof)
        sector = next((s for s in self.tree.Sectors if s.Id == cn.Sector), None) if cn.Sector else None
        return L.Id(f"craft.sector.{sector.Id}.name", sector.Name) if sector is not None else None

    def _chunk_prof(self, chunk) -> str | None:
        """TreeWindow.ChunkProf: the chunk's profession, else the most common among its nodes."""
        if chunk.Prof:
            return chunk.Prof
        counts, best, top = {}, None, 0
        for node_id in chunk.Nodes:
            prof = self.tree.Nodes[node_id].Prof
            if prof:
                counts[prof] = counts.get(prof, 0) + 1
                if counts[prof] > top:
                    top, best = counts[prof], prof
        return best

    def option(self, node, o, index: int) -> dict:
        """TreeWindow.CraftOptionRow: description (hover) and body lines."""
        from PassiveTree import CraftMasteries, Stat, StatText, Wiki

        description = o.Told
        has_flag, flag = CraftMasteries.TryFlag(o, Stat.DamagePct)  # out param: any Stat as placeholder
        if not description and has_flag:
            description = StatText.Describe(flag, 1.0)
        if not description:
            description = "\n".join(StatText.Describe(m.Key, m.Value) for m in o.Mods if StatText.IsFlag(m.Key))
        body = []
        has_knob = has_flag and _KNOB.search(StatText.FormatInfo(flag).Item1 or "")  # TreeWindow.HasKnob
        if has_knob and not _KNOB.search(description or ""):
            body.append(Wiki.Live(StatText.Describe(flag, 1.0)))
        body += [StatText.DescribeMod(m) for m in o.Mods if not StatText.IsFlag(m.Key)]
        ok, lines = CraftMasteries.TryLines(o, None)
        if ok and lines is not None:
            body += [StatText.DescribeMod(m) for m in lines]
        return {
            "id": o.Id,
            "title": o.Title,
            "stats": [line for b in body for line in _lines(b)],
            "extra": _lines(description),
            "broken": bool(o.Broken) or not CraftMasteries.Works(o),
            "reserved": False,
            "unformatted": self.unformatted(o.Mods, self.formatted),
            "icon": self.art_get(self.art.ArtKey(node, index)),
        }

    def render(self, errors: list) -> dict:
        from PassiveTree import L, NodeSize, StatText

        search = self.tree.SearchNodes
        nodes = {}
        for cn in self.tree.Nodes.Values:
            try:
                ok, node = search.TryGetValue(cn.Id, None)
                node = node if ok else None
                travel = cn.Size == NodeSize.Travel
                title = L.Id("ui.crafttree.path", "Path") if travel else L.Id(f"craft.node.{cn.Id}.name", cn.Name)
                mods = node.Mods if node is not None else []
                extra = node.Told if node is not None and node.Extra else ""
                nodes[cn.Id] = {
                    "title": title,
                    "shelf": self.shelf(cn),
                    "sector": cn.Sector,
                    "prof": cn.Prof,
                    "entry": bool(cn.Entry),
                    "stats": _lines(StatText.DescribeAll(mods)) if node is not None else [],
                    "extra": _lines(extra),
                    "broken": bool(node.Broken) if node is not None else True,
                    "unformatted": self.unformatted(mods, self.formatted) if node is not None else [],
                    "icon": self.node_icon(cn, node),
                    "options": [self.option(node, o, i) for i, o in enumerate(node.Options or [])] if node is not None else [],
                }
            except Exception as ex:  # one bad node must not lose the rest
                errors.append({"craft": cn.Id, "error": str(ex).split("\n")[0]})
        sectors = [
            {
                "id": s.Id,
                "name": L.Id(f"craft.sector.{s.Id}.name", s.Name),
                "profs": [{"id": p, "name": L.Id(f"craft.prof.{p}", p)} for p in s.Profs],
            }
            for s in self.tree.Sectors
        ]
        return {"nodes": nodes, "sectors": sectors}
