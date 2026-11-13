"""Skill gems and the skill board, as the game defines and shows them (PassiveTree.Gems).

- Gems (GemCatalog.All): name, role (a curse is an effect with a curse), tags, the tooltip text
  at every rank (GemCatalog.Describe), the item properties of the bag tooltip (GemText.Properties:
  tags or supported tags, capacity, a trigger's stamina cost per effect, an aura's eitr reserve),
  every number with whether it grows with rank (its value at each rank), and the boss whose defeat
  allows cutting it (GemCatalog.Gate, GemText.BossWord; the boss's prefab from CreatureLevels.Bosses).
- How each number ranks (6.0.7 on): drawbacks (GemDef.Drawbacks), overflowing chances with their
  stat line at each rank (GemDef.Counts, GemCatalog.Row, StatText.DescribeHead/DescribeTail) and
  numbers that grow although such numbers usually do not (GemDef.Grows); a support's aura form,
  what the Circle of Gifts grants from it at each rank (GemAuras.Projection at strength 1).
- What works with what: each trigger and effect pair (GemBoard.WhyNotFeed: null when the trigger
  starts the effect, else the game's reason), and each support on each effect or aura
  (GemBoard.Supports).
- The board (GemBoard.Cells: id, axial q/r, open from the start) and its tunables (gem.board.*,
  gem.curse.limit, gem.rank.drop-step, gem.staff.*), the uncut gems and the Awakening Chisel
  (GemItems: names, flavors, tooltip lines, which roles each uncut gem cuts into).
- Board terms of the in-game wiki (GemText.EnsureTerms: "gem:board", "gem:capacity"...), with
  their text; read after the wiki itself is rendered, so they stay out of the glossary (their
  keys hold a ":").
- The staves' curse (StaffCurse.Kinds: the tree subject of each curse) and the sigils whose
  carriers receive board items once (SigilMigration.Compensation, rank SigilMigration.Rank).
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


def _private(type_, name: str):
    return type_.GetField(name, _ANY).GetValue(None)


def _role(r) -> str:
    return str(r)  # Trigger, Effect, Support, Aura


def render_gems(errors: list) -> dict:
    from PassiveTree import CreatureLevels, L, StatText, Tunables, Wiki
    from PassiveTree.Gems import GemAuras, GemBoard, GemCatalog, GemInstance, GemItems, GemText, Role, SigilMigration, StaffCurse, Tag
    from System import String

    out: dict = {}
    try:
        bosses = {str(b.Item2): str(b.Item1) for b in CreatureLevels.Bosses}
        gems = []
        for g in GemCatalog.All:
            params = []
            for kv in g.Params:
                name = str(kv.Key)
                # Whether it grows with rank, from its value at each rank (GemCatalog.Value): the
                # rule behind it changed (Ranks(name), Ranks(g, name) in 6.0.7, gone in 6.0.9).
                by_rank = [float(GemCatalog.Value(g, name, r)) for r in range(1, GemCatalog.MaxRank + 1)]
                params.append({"name": name, "value": float(Tunables.Of(f"gem.{g.Id}.{name}")),
                               "pct": bool(g.PctParam[name]), "ranks": len(set(by_rank)) > 1, "byRank": by_rank})
            # GemText.Properties, without an item.
            props = []
            if g.Role == Role.Support:
                tags = (GemCatalog.TagWords(Tag.BuffAura) + " (" + GemCatalog.RoleName(Role.Aura) + ")"
                        if g.Id == "aura-self" else GemCatalog.TagWords(g.Accepts))
                props.append([L.Id("gem.supports-tags", "Supports gems with"), tags])
            else:
                props.append([L.Id("gem.tags", "Tags"), GemCatalog.TagWords(g.Tags)])
            props.append([L.Id("gem.prop.capacity", "Capacity"), GemText.CapacityWord(g)])
            block = str(g.Event) in ("Block", "Parry")
            if g.Role == Role.Trigger:
                label = L.Id("gem.prop.block-cost", "Block stamina cost") if block else L.Id("gem.prop.attack-cost", "Attack stamina cost")
                props.append([label, String.Format(L.Id("gem.prop.per-effect", "+{0}% per effect"), round(float(g.P("cost")) * 100))])
            names = {str(kv.Key) for kv in g.Params}
            share = "reserve-share" in names  # 6.0.7 on: a share of maximum eitr, before a flat "reserve"
            if g.IsAura:
                props.append([L.Id("gem.prop.reserve", "Eitr reserve"),
                              f"{round(float(g.P('reserve-share')) * 100)}%" if share else str(round(float(g.P("reserve"))))])
            ranking = {}
            if hasattr(g, "Drawbacks"):
                ranking["drawbacks"] = [str(x) for x in g.Drawbacks]
            if hasattr(g, "Counts"):
                ranking["counts"] = {str(kv.Key): {"stat": str(kv.Value), "text": [_row_text(StatText, GemCatalog.Row(g, str(kv.Key), r))
                                                                              for r in range(1, GemCatalog.MaxRank + 1)]}
                                     for kv in g.Counts}
            if hasattr(g, "Grows"):
                ranking["grows"] = [str(x) for x in g.Grows]
            if g.Role == Role.Support:
                forms = []
                for r in range(1, GemCatalog.MaxRank + 1):
                    inst = GemInstance()
                    inst.Def, inst.Rank = g, r
                    mods = GemAuras.Projection(inst, 1.0)
                    forms.append([line for line in str(StatText.DescribeAll(mods)).splitlines() if line] if len(mods) else [])
                if any(forms):
                    ranking["auraForm"] = forms
            gems.append({
                "id": str(g.Id), "prefab": str(g.PrefabId), "name": GemCatalog.Name(g),
                "role": _role(g.Role), "roleLabel": GemCatalog.RoleLabel(g), "curse": bool(g.IsCurse),
                "type": String.Format(L.Id("ui.item.type.gem", "Skill gem - {0}"), GemCatalog.RoleLabel(g)),
                "event": str(g.Event) if g.Role == Role.Trigger else None,
                "tags": [str(t) for t in GemCatalog.TagsOf(g.Tags)],
                "accepts": [str(t) for t in GemCatalog.TagsOf(g.Accepts)],
                "text": [GemCatalog.Describe(g, r, False) for r in range(1, GemCatalog.MaxRank + 1)],
                "properties": props,
                "capacity": float(g.P("capacity")),
                "cost": float(g.P("cost")) if g.Role == Role.Trigger else None,
                "costText": GemText.TriggerCost(g) if g.Role == Role.Trigger else None,
                "reserve": float(g.P("reserve")) if g.IsAura and not share else None,
                "reserveShare": float(g.P("reserve-share")) if g.IsAura and share else None,
                "gifts": bool(g.Gifts), "malice": bool(g.Malice),
                "bossKey": str(g.BossKey) if g.BossKey else None,
                "boss": GemText.BossWord(g) if g.BossKey else None,
                "bossPrefab": bosses.get(str(g.BossKey)) if g.BossKey else None,
                "notInDrops": bool(g.NotInDrops),
                "params": params,
                **ranking,
            })
        out["gems"] = gems
        by_role = {r: [g for g in GemCatalog.All if g.Role == getattr(Role, r)] for r in ("Trigger", "Effect", "Support", "Aura")}
        out["feeds"] = {str(t.Id): {str(e.Id): GemBoard.WhyNotFeed(t, e) for e in by_role["Effect"]} for t in by_role["Trigger"]}
        out["supports"] = {str(s.Id): [str(x.Id) for x in by_role["Effect"] + by_role["Aura"] if GemBoard.Supports(s, x)]
                           for s in by_role["Support"]}
        out["cells"] = [{"id": str(c.Id), "q": int(c.Q), "r": int(c.R), "open": bool(c.StartOpen)} for c in GemBoard.Cells]
        out["tunables"] = {str(k.Id): float(Tunables.Of(k.Id)) for k in Tunables.All
                           if str(k.Id).startswith(("gem.board.", "gem.curse.", "gem.rank.", "gem.staff."))}
        out["rankStep"] = float(GemCatalog.RankStep)
        for key, const in (("countStep", "CountStep"), ("drawbackStep", "DrawbackStep"), ("cooldownStep", "CooldownStep")):
            if hasattr(GemCatalog, const):  # 6.0.9 on
                out[key] = float(getattr(GemCatalog, const))
        out["maxRank"] = int(GemCatalog.MaxRank)
        items = {}
        for prefab, role in ((GemItems.UncutTrigger, "Trigger"), (GemItems.UncutEffect, "Effect"), (GemItems.UncutSupport, "Support")):
            items[prefab] = {
                "name": L.Id(f"item.{prefab}.name", ""), "flavor": L.Id(f"item.{prefab}.flavor", ""),
                "type": L.Id("ui.item.type.gem-uncut", "Uncut skill gem"),
                "use": L.Id(f"gem.uncut.{role.lower()}", ""), "lines": [L.Id("gem.uncut.rank", "")],
                "cuts": [str(g.Id) for g in GemCatalog.All if GemItems.Opens(prefab, g)],
            }
        chisel = GemItems.Chisel
        items[chisel] = {
            "name": L.Id(f"item.{chisel}.name", ""), "flavor": L.Id(f"item.{chisel}.flavor", ""),
            "type": L.Id("ui.item.type.gem-chisel", "Skill board consumable"),
            "use": L.Id("gem.chisel.how", ""), "lines": [L.Id("gem.chisel.capacity", "")], "cuts": [],
        }
        out["items"] = items
        out["text"] = {k: L.Id(f"gem.{k}", "") for k in (
            "how", "use", "boss-line", "cut.boss", "ui.help", "ui.over", "ui.locked-how", "refuse.combat", "refuse.capacity",
            "staff.name", "tab", "state.working", "state.idle", "state.off", "state.suspended", "state.incompatible",
            "state.capacity")}
        out["roles"] = {r: GemCatalog.RoleName(getattr(Role, r)) for r in ("Trigger", "Effect", "Support", "Aura")}
        out["roles"]["Curse"] = L.Id("gem.role.curse", "Curse")
        GemText.EnsureTerms()
        out["terms"] = {str(t.Key): {"title": t.Shown, "text": str(Wiki.Article(t)).split("\n")}
                        for t in Wiki.Terms if str(t.Key).startswith("gem:")}
        out["staffCurses"] = {str(kind.Item2): str(kind.Item1) for kind in StaffCurse.Kinds}
        out["sigils"] = {str(kv.Key): [str(x) for x in kv.Value] for kv in SigilMigration.Compensation}
        out["sigilRank"] = int(_private(_type("PassiveTree.Gems.SigilMigration"), "Rank"))
    except Exception as ex:
        errors.append({"gems": "board", "error": str(ex).split("\n")[0]})
    return out


def _row_text(StatText, mod) -> str:
    """An overflowing chance as GemCatalog.Describe writes it: the stat line of GemCatalog.Row."""
    return "" if mod is None else str(StatText.DescribeHead(mod, None)) + str(StatText.DescribeTail(mod))


def _type(name: str):
    from System import AppDomain

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    return asm.GetType(name)
