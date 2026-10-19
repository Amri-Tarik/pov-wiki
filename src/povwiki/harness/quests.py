"""Craft quests and profession areas, from the game's own catalogs and formulas.

- Profession areas (CraftProgressionCatalog.Areas, rebuilt by CraftTree.Load from the tree's own
  area polygons: number = order within the profession, tier and XP from the compiled entry of the
  same id, eased once more): revealed as the profession's craft XP grows; lore from the area
  chunks (craft.area.<chunk>.lore). The profession stage is the highest tier reached.
- Quests scale with the number of the profession's areas revealed (CraftProgress.ProfessionLevel),
  0 .. all of them.
- Quests (CraftTaskCatalog.All joined with CraftProgressionCatalog.Quests): what a task asks, its
  base count, reward, boss gate and offer weight. CraftQuestJournal.IssueSlot turns those into an
  offered quest at a profession stage: target = RoundQuota(count x CountScale(stage) x
  multiplier), reward = Math.Round(reward x 1.8 x Hardness(stage, profession)). Condition
  variants of a family are offered only at stages where a quest slot asks for that many
  conditions (CraftQuestComposer.ConditionsFor / MaxConditions).
- Never offered: tasks in CraftQuestJournal.Removed, tasks without a quest entry, tasks the
  composer cannot issue (CanIssue) or with no condition weight. Reserved areas, and professions
  the tree window calls "not available in the game yet" (TreeWindow.FutureProfession), are
  unfinished as well.
"""

from System import Math

SLOTS = 4  # quest slots per profession (CraftQuestJournal.IssueSlot)
FUTURE_PROFESSIONS = {"road3"}  # TreeWindow.FutureProfession
_hooks: list = []


def _no_game_names() -> None:
    """Quest targets are named through Valheim's own localization first (CraftQuestComposer.
    GameName -> Localization.Localize("$item_...")), whose tables only exist in a running game.
    Answer "no name" there, so TargetLabel uses its fallback: the mod's own target name
    (craft.composer.target.<template>.<index>)."""
    if _hooks:
        return
    from MonoMod.RuntimeDetour import Hook
    from System import AppDomain, Func, Object, String
    from System.Reflection import BindingFlags

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    game_name = asm.GetType("PassiveTree.CraftQuestComposer").GetMethod(
        "GameName", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public
    )
    _hooks.append(Hook(game_name, Func[Object, String](lambda target: None)))


def render_quests(craft_tree) -> dict:
    from PassiveTree import CraftProgressionCatalog, CraftQuestComposer, CraftQuestJournal, CraftTaskCatalog, L

    CraftQuestComposer.Ensure()
    _no_game_names()
    chunks = {c.Id: c for c in craft_tree.Chunks}

    professions: dict[str, dict] = {}
    for area in CraftProgressionCatalog.Areas.Values:
        p = professions.setdefault(area.Profession, {"areas": [], "unavailable": area.Profession in FUTURE_PROFESSIONS})
        chunk = chunks.get(f"area.{area.Id}")
        p["areas"].append({
            "id": area.Id,
            "number": area.Number,
            "tier": area.Tier,
            "xp": area.XP,
            "reserved": bool(area.Reserved),
            "lore": L.Id(f"craft.area.area.{area.Id}.lore", chunk.Hint) if chunk is not None and chunk.Hint else "",
        })
    for p in professions.values():
        p["areas"].sort(key=lambda a: a["number"])

    quests = CraftProgressionCatalog.Quests
    removed = {str(x) for x in CraftQuestJournal.Removed}
    tasks = []
    for spec in CraftTaskCatalog.All.Values:
        ok, quest = quests.TryGetValue(spec.Id, None)
        quest = quest if ok else None
        issuable = (
            quest is not None and spec.Id not in removed and CraftQuestComposer.CanIssue(spec) and spec.ConditionWeight > 0
        )
        levels = len(professions.get(spec.Profession, {}).get("areas", [])) + 1  # 0 .. all areas revealed
        per_stage = []
        for level in range(levels):
            wanted = {CraftQuestComposer.ConditionsFor(level, slot) for slot in range(SLOTS)}
            per_stage.append({
                "offered": issuable and any(spec.ConditionCount == CraftQuestComposer.MaxConditions(spec, w) for w in wanted),
                "count": CraftQuestComposer.RoundQuota(spec.Count * CraftQuestJournal.CountScale(level) * spec.Multiplier),
                "reward": max(1, int(Math.Round(quest.Reward * 1.8 * CraftQuestJournal.Hardness(level, spec.Profession))))
                if quest is not None else 0,
            })
        template = CraftQuestComposer.TemplateOf(spec)
        first = next((i for i, s in enumerate(per_stage) if s["offered"]), 0)
        shown = CraftQuestJournal.Active()  # what the quest journal shows, at the first stage offered
        shown.Task, shown.Count = spec.Id, per_stage[first]["count"]
        tasks.append({
            "id": spec.Id,
            "profession": spec.Profession,
            "family": quest.Family if quest is not None else spec.Id,
            # Composed quests (CraftQuestComposer templates) are the ones the game offers.
            "template": template.Id if template is not None else None,
            "action": L.Id(f"craft.composer.{template.Id}.action", template.English) if template is not None else "",
            "target": CraftQuestComposer.TargetLabel(spec) or "",
            "facts": [L.Id(f"craft.composer.condition.{f}", f) for f in spec.Facts],
            "shown": CraftQuestComposer.Text(spec, shown, False),
            "text": L.Id(f"craft.quest.{spec.Id}.text", spec.English),
            "hud": L.Id(f"craft.quest.{spec.Id}.hud", spec.HudText),
            "unit": L.Id(f"craft.quest.{spec.Id}.unit", spec.ProgressUnit) if spec.ProgressUnit else "",
            "count": spec.Count,
            "multiplier": spec.Multiplier,
            "conditions": max(0, spec.ConditionCount),
            "once": bool(spec.Once),
            "unique": bool(spec.Unique),
            "resets": [str(x) for x in spec.Reset],
            "gate_item": spec.GateItem or "",
            "reward": quest.Reward if quest is not None else 0,
            "boss": quest.Boss if quest is not None else 0,
            "weight": quest.Weight if quest is not None else 0.0,
            "issuable": issuable,
            "removed": spec.Id in removed,
            "stages": per_stage,
        })
    return {"professions": professions, "tasks": tasks}
