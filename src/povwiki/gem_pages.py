"""Skill gems and the skill board (PassiveTree.Gems, rendered by harness/gems.py).

- The gem index: every gem by role (triggers, effects, curses, supports, auras) with its icon,
  the game's tooltip text (numbers over ranks 1-5), capacity, price (a trigger's stamina cost per
  effect, an aura's eitr reserve) and where it comes from (the uncut gem it is cut from; boss gems
  only after the boss is defeated, GemCut.WhyNot).
- A page per gem: its bag tooltip (GemText.Properties), its text at every rank, what it works with
  on the board (GemBoard.WhyNotFeed, GemBoard.Supports; the Circle of Malice takes curses, the
  Circle of Gifts every support), the Hexcraft option that casts a curse with staves
  (StaffCurse.Kinds) and the sigils that give it (SigilMigration.Compensation).
- Pages for the uncut gems and the Awakening Chisel: what they cut into or open, their rank by
  creature level (GemItems.RankForLevel) and how they drop (LootCatalog.Currency, family
  "skill-gems").
- The board page: the 19 cells (GemBoard.Cells), adjacency (GemBoard.Resolve), capacity
  (GemBoard.CapacityOf), stamina cost and eitr reserve (GemBoard.Resolve, GemBoard.ReserveOf),
  auras at work (GemAuras.Strength, Pulse, Retort, Projection; GemCast.With), curses (Curses.Limit,
  Curses.Store), ranks and cutting (GemCatalog.Value: growing numbers, drawbacks, overflowing
  chances, trigger chances and cooldowns; GemCut).
- On each support, its aura form under the Circle of Gifts (GemAuras.Projection), and on the
  circle every support's.
"""

import re
from collections import defaultdict

from .markup import plain, rel, to_md
from .pages import Ctx, _footer, _img, _table

INDEX_PAGE = "items/gems.md"
BOARD_PAGE = "items/gems/board.md"
_GROUPS = ("Trigger", "Effect", "Curse", "Support", "Aura")  # index order; a curse is an effect
_UNCUT = {"Trigger": "PT_GemUncutTrigger", "Effect": "PT_GemUncutEffect", "Support": "PT_GemUncutSupport", "Aura": "PT_GemUncutEffect"}
CHISEL = "PT_GemPatternChisel"
_PERIODIC = ("poison-aura", "effect-retort")  # auras dealing damage over time, not hits (GemHits.DealPeriodic)


def gem_path(gid: str) -> str:
    return f"items/gems/{gid}.md"


def item_path(prefab: str) -> str:
    """An uncut gem's or the chisel's page."""
    return f"items/gems/{prefab}.md"


def _data(ctx: Ctx) -> dict:
    return ctx.loc.gems


def _by_id(ctx: Ctx) -> dict[str, dict]:
    return {g["id"]: g for g in _data(ctx).get("gems", [])}


def _group(g: dict) -> str:
    return "Curse" if g["curse"] else g["role"]


def _icon(ctx: Ctx, g: dict, page: str, px: int) -> str:
    """The gem's bag icon (GemArt.Cut, extracted as item.<prefab>.png)."""
    return _img(ctx.icons.path(f"PassiveTree.item.{g['prefab']}.png"), page, px) if ctx.icons else ""


def _hex(ctx: Ctx, g: dict, page: str, px: int) -> str:
    """The gem in its board hexagon (GemArt, extracted as gemhex.<id>.png)."""
    return _img(ctx.icons.path(f"PassiveTree.gemhex.{g['id']}.png"), page, px) if ctx.icons else ""


def _item_icon(ctx: Ctx, prefab: str, page: str, px: int) -> str:
    return _img(ctx.icons.path(f"PassiveTree.item.{prefab}.png"), page, px) if ctx.icons else ""


def gem_link(ctx: Ctx, gid: str, page: str, icon: bool = False) -> str:
    g = _by_id(ctx).get(gid)
    if g is None:
        return gid
    art = f'<span class="pov-inline">{_icon(ctx, g, page, 24)}' if icon and ctx.icons else ""
    return f"{art}[{g['name']}]({rel(gem_path(gid), page)}){'</span>' if art else ''}"


def item_link(ctx: Ctx, prefab: str, page: str) -> str:
    it = _data(ctx)["items"][prefab]
    return f"[{it['name']}]({rel(item_path(prefab), page)})"


# ---- The game's numbers -------------------------------------------------------------------------


def _code_ranks(g: dict, p: dict) -> bool:
    """Whether a number changes with rank in what the game does. From 6.0.7 (the gem lists its
    drawbacks) the game reads every number at the gem's rank (GemCatalog.Value), as the tooltip
    does. Before, GemCatalog.Ranks said which numbers the tooltip ranks, while supports read their
    drawbacks ("less", "self", "shorter") with GemDef.P, rank 1 (GemBoard.SupportOn), and Plague
    Breath its own share ("self", GemAuras.Pulse)."""
    if not p["ranks"] or "drawbacks" in g:
        return p["ranks"]
    if g["role"] == "Support" and p["name"] in ("less", "self", "shorter"):
        return False
    return not (g["id"] == "poison-aura" and p["name"] == "self")


def _num(v: float) -> str:
    """GemCatalog.Num: whole numbers without decimals, else up to two."""
    return f"{round(v, 2):g}"


def _value(g: dict, p: dict, rank: int) -> float:
    return p["byRank"][rank - 1] if _code_ranks(g, p) else p["byRank"][0]


_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")


def _merge(lo: str, hi: str) -> str:
    """Two renderings of one line at rank 1 and the top rank as one line, each number that differs
    written as its range ("+200–340% overflowing chance")."""
    a, b = _NUMBER.split(lo), _NUMBER.split(hi)
    if len(a) != len(b) or a[::2] != b[::2]:
        return lo
    return "".join(x if i % 2 == 0 or x == y else f"{x}–{y}" for i, (x, y) in enumerate(zip(a, b)))


def _count_text(g: dict, name: str, rank: int | None) -> str | None:
    """An overflowing chance (GemDef.Counts) as the game writes it: a stat line (GemCatalog.Row)."""
    c = (g.get("counts") or {}).get(name)
    if not c:
        return None
    return c["text"][rank - 1] if rank else _merge(c["text"][0], c["text"][-1])


def _shown(g: dict, p: dict, lo: float, hi: float) -> str:
    """A number as GemCatalog.Describe writes it, or its range over the ranks."""
    if p["pct"]:
        a, b = _num(abs(lo) * 100), _num(abs(hi) * 100)
        sign = "-" if lo < 0 and p["name"] == "resist" else ""
        return f"{sign}{a}%" if a == b else (f"-({a}–{b})%" if sign else f"{a}–{b}%")
    a, b = _num(lo), _num(hi)
    return a if a == b else f"{a}–{b}"


def _template(ctx: Ctx, g: dict) -> str:
    return ctx.loc.text(f"@gem.{g['id']}.text", "")


def gem_text(ctx: Ctx, g: dict, rank: int | None = None, page: str | None = None) -> str:
    """The tooltip text (GemCatalog.Describe) at one rank, or with each number over ranks 1-5;
    as Markdown for `page` (an overflowing chance's line has keyword links), else plain."""
    params = {p["name"]: p for p in g["params"]}
    template = _template(ctx, g)
    top = _data(ctx).get("maxRank", 5)

    def fill(m: re.Match) -> str:
        if (line := _count_text(g, m.group(1), rank)) is not None:
            return line
        p = params.get(m.group(1))
        if p is None:
            return m.group(0)
        lo, hi = (_value(g, p, rank), _value(g, p, rank)) if rank else (_value(g, p, 1), _value(g, p, top))
        return _shown(g, p, lo, hi)

    # No localised template: the rendered text at that rank (rank 1 for the range).
    text = re.sub(r"\{([a-z\-]+)\}", fill, template) if template else g["text"][(rank or 1) - 1]
    return to_md(text, ctx.loc, page) if page else plain(text)


def _ranked(g: dict) -> bool:
    return any(_code_ranks(g, p) for p in g["params"])


def _price(ctx: Ctx, g: dict) -> str:
    """A trigger's stamina cost per effect, an aura's eitr reserve: the bag tooltip's own line."""
    rows = [f"{label}: {value}" for label, value in g["properties"][2:]]
    return "<br>".join(rows) or "—"


def _source(ctx: Ctx, g: dict, page: str) -> str:
    """The uncut gem it is cut from, and the boss to defeat first (GemCut.WhyNot)."""
    parts = [item_link(ctx, _UNCUT[g["role"]], page)]
    if g.get("boss"):
        parts.append(_after_boss(ctx, g, page))
    return "<br>".join(parts)


def _boss_link(ctx: Ctx, g: dict, page: str) -> str:
    from .monster_pages import creature_link

    return creature_link(ctx, g["bossPrefab"], page) if g.get("bossPrefab") else g["boss"]


def _after_boss(ctx: Ctx, g: dict, page: str) -> str:
    """The game's own line: "After {boss} is defeated"."""
    return _data(ctx)["text"]["cut.boss"].replace("{0}", _boss_link(ctx, g, page))


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:]


# ---- Index --------------------------------------------------------------------------------------


def page_gems(ctx: Ctx) -> dict[str, str]:
    data = _data(ctx)
    if not data.get("gems"):
        return {}
    ui, page = ctx.loc.ui, INDEX_PAGE
    md = [f"# {ui('gems.title')}", "", ui("gems.intro", board=rel(BOARD_PAGE, page)), ""]
    groups: dict[str, list[dict]] = defaultdict(list)
    for g in data["gems"]:
        groups[_group(g)].append(g)
    for role in _GROUPS:
        gs = groups.get(role, [])
        if not gs:
            continue
        md += [f"## {ui(f'gems.group.{role}')} ({len(gs)}) {{ #{role.lower()} }}", "", ui(f"gems.group_intro.{role}"), ""]
        rows = [[_icon(ctx, g, page, 40), f"[**{g['name']}**]({rel(gem_path(g['id']), page)})", gem_text(ctx, g, page=page),
                 _capacity(ctx, g), _price(ctx, g), _source(ctx, g, page)] for g in gs]
        md += _table(["", ui("col.name"), ui("col.effect"), ui("gems.capacity"), ui("gems.price"), ui("gems.source")], rows)
    md += [f"## {ui('gems.materials')} {{ #materials }}", "", ui("gems.materials_intro", chisel=item_link(ctx, CHISEL, page)), ""]
    rows = []
    for prefab, it in data["items"].items():
        rows.append([_item_icon(ctx, prefab, page, 40), f"[**{it['name']}**]({rel(item_path(prefab), page)})",
                     it["use"], _obtained(ctx, prefab)])
    md += _table(["", ui("col.name"), ui("col.effect"), ui("gear.obtained")], rows)
    md += [ui("gems.ranges", board=rel(BOARD_PAGE, page) + "#ranks"), ""]
    pages = {page: "\n".join(md + _footer(ctx)), BOARD_PAGE: _board_page(ctx)}
    for g in data["gems"]:
        pages[gem_path(g["id"])] = _gem_page(ctx, g)
    for prefab in data["items"]:
        pages[item_path(prefab)] = _item_page(ctx, prefab)
    return pages


def _capacity(ctx: Ctx, g: dict) -> str:
    return g["properties"][1][1]  # GemText.Properties: tags, then capacity


def _obtained(ctx: Ctx, prefab: str) -> str:
    from .item_pages import biome

    c = _catalog(ctx).get(prefab)
    if c and c.get("weight", 0) > 0:
        return ctx.loc.ui("gear.drops_from", biome=biome(ctx, max(1, c.get("minLevel") or 0)))
    return "—"


def _catalog(ctx: Ctx) -> dict:
    return {c["id"]: c for c in ctx.data.loot.get("currency") or []}


# ---- A gem's page -------------------------------------------------------------------------------


def _gem_page(ctx: Ctx, g: dict) -> str:
    ui, page, data = ctx.loc.ui, gem_path(g["id"]), _data(ctx)
    md = [f"# {g['name']}", ""]
    if ctx.icons:
        md += [f"{_icon(ctx, g, page, 96)} {_hex(ctx, g, page, 96)}", ""]
    md += [f"<b>{g['type']}</b> · [{ui('gems.title')}]({rel(INDEX_PAGE, page)}#{_group(g).lower()})", ""]
    md += [gem_text(ctx, g, page=page), ""]
    md += _table([ui("col.property"), ui("col.value")], [[label, value] for label, value in g["properties"]])
    if g.get("costText"):
        md += [g["costText"], ""]
    if g.get("reserve") is not None:
        md += [ui("gems.reserve_line", n=_num(g["reserve"]), link=rel(BOARD_PAGE, page) + "#eitr"), ""]
    elif g.get("reserveShare") is not None:
        md += [ui("gems.reserve_share_line", n=_pct(g["reserveShare"]), link=rel(BOARD_PAGE, page) + "#eitr"), ""]
    if g["id"] in _PERIODIC and "countStep" in data:  # GemAuras.Pulse, GemAuras.Retort (6.0.9 on)
        md += [ui("gems.periodic_line", link=rel(BOARD_PAGE, page) + "#auras"), ""]
    if _ranked(g):
        md += [f"## {ui('gems.by_rank')}", "", ui("gems.by_rank_intro", link=rel(BOARD_PAGE, page) + "#ranks"), ""]
        md += _table([ui("gems.rank"), ui("col.effect")],
                     [[str(r), gem_text(ctx, g, r, page)] for r in range(1, data.get("maxRank", 5) + 1)])
    md += _aura_form(ctx, g, page)
    if g["gifts"]:
        md += _gift_forms(ctx, page)
    md += _works_with(ctx, g, page)
    md += _staff_section(ctx, g, page)
    md += [f"## {ui('gems.how_to_get')}", ""]
    md += [ui("gems.cut_from", item=item_link(ctx, _UNCUT[g["role"]], page)), ""]
    if g.get("boss"):
        md += [ui("gems.boss_gem", line=_lower_first(_after_boss(ctx, g, page))), ""]
    if sigils := [s for s, given in data.get("sigils", {}).items() if f"gem:{g['id']}" in given]:
        md += [ui("gems.from_sigils", sigils=", ".join(_sigil_link(ctx, s, page) for s in sigils), rank=data.get("sigilRank", 3)), ""]
    return "\n".join(md + _footer(ctx))


def _pct(v: float) -> str:
    return f"{_num(v * 100)}%"


def _form_lines(ctx: Ctx, lines: list[str], page: str) -> str:
    return "<br>".join(to_md(line, ctx.loc, page) for line in lines)


def _aura_form(ctx: Ctx, g: dict, page: str) -> list[str]:
    """What the Circle of Gifts grants from this support at each of its ranks (GemAuras.Projection,
    at the circle's strength 1)."""
    forms = g.get("auraForm")
    gifts = next((x for x in _data(ctx)["gems"] if x["gifts"]), None)
    if not forms or not gifts:
        return []
    ui = ctx.loc.ui
    md = [f"## {ui('gems.aura_form')} {{ #aura-form }}", "",
          ui("gems.aura_form_text", gifts=gem_link(ctx, gifts["id"], page), link=rel(BOARD_PAGE, page) + "#auras"), ""]
    return md + _table([ui("gems.rank"), ui("gems.aura_form")],
                       [[str(r), _form_lines(ctx, lines, page)] for r, lines in enumerate(forms, 1)])


def _gift_forms(ctx: Ctx, page: str) -> list[str]:
    """On the Circle of Gifts: every support's aura form, its numbers over the support's ranks."""
    sups = [g for g in _data(ctx)["gems"] if g.get("auraForm")]
    if not sups:
        return []
    ui = ctx.loc.ui
    rows = []
    for g in sups:
        lo, hi = g["auraForm"][0], g["auraForm"][-1]
        lines = [_merge(a, b) for a, b in zip(lo, hi)] if len(lo) == len(hi) else lo
        rows.append([_icon(ctx, g, page, 32), gem_link(ctx, g["id"], page), _form_lines(ctx, lines, page)])
    return ([f"## {ui('gems.aura_forms')} {{ #aura-forms }}", "", ui("gems.aura_forms_text", link=rel(BOARD_PAGE, page) + "#auras"), ""]
            + _table(["", ui("col.name"), ui("gems.aura_form")], rows))


def _names(ctx: Ctx, ids: list[str], page: str) -> str:
    return ", ".join(gem_link(ctx, i, page, icon=True) for i in ids) or "—"


def _works_with(ctx: Ctx, g: dict, page: str) -> list[str]:
    """Its neighbours on the board that work with it (GemBoard.Resolve)."""
    ui, data, gems = ctx.loc.ui, _data(ctx), _data(ctx)["gems"]
    feeds, supports = data["feeds"], data["supports"]
    md = [f"## {ui('gems.on_board')}", ""]
    rows = []
    if g["role"] == "Trigger":
        mine = feeds.get(g["id"], {})
        rows.append([ui("gems.starts"), _names(ctx, [e for e, why in mine.items() if why is None], page)])
        no = defaultdict(list)
        for e, why in mine.items():
            if why is not None:
                no[why].append(e)
        for why, es in no.items():
            rows.append([ui("gems.cannot_start"), f"{_names(ctx, es, page)} <small>({why})</small>"])
    elif g["role"] == "Effect":
        rows.append([ui("gems.started_by"), _names(ctx, [t for t, es in feeds.items() if es.get(g["id"]) is None], page)])
        if g["curse"]:
            rows.append([ui("gems.kept_by"), _names(ctx, [x["id"] for x in gems if x["malice"]], page)])
    if g["role"] in ("Effect", "Aura"):
        rows.append([ui("gems.supported_by"), _names(ctx, [s for s, xs in supports.items() if g["id"] in xs], page)])
    if g["role"] == "Support":
        rows.append([ui("gems.supports"), _names(ctx, supports.get(g["id"], []), page)])
    if g["malice"]:
        rows.append([ui("gems.keeps"), _names(ctx, [x["id"] for x in gems if x["curse"]], page)])
    md += _table([ui("col.property"), ui("col.value")], rows)
    md += [ui("gems.adjacency", link=rel(BOARD_PAGE, page) + "#adjacency"), ""]
    return md


def _staff_section(ctx: Ctx, g: dict, page: str) -> list[str]:
    """A curse's Hexcraft option: staves' alternative attack casts it (StaffCurse.Kinds)."""
    subject = _data(ctx).get("staffCurses", {}).get(g["id"])
    found = _hex_option(ctx, subject, page) if subject else None
    term = _data(ctx).get("terms", {}).get(f"gem:{g['id']}")
    if not found or not term:
        return []
    text = " ".join(to_md(line, ctx.loc, page) for line in term["text"])
    return [f"## {_data(ctx)['text']['staff.name']}", "", ctx.loc.ui("gems.staff", option=found), "", f"> {text}", ""]


def _hex_option(ctx: Ctx, subject: str, page: str) -> str | None:
    """The mastery option granting Hex for this curse, linked: "Hexcraft: Broken Seals"."""
    from .pages import option_path

    for grp in ctx.option_groups.values():
        o = grp["options"][0]
        if any(m.get("stat") == "Hex" and m.get("subject") == subject for m in o["raw"].get("mods") or []):
            node = plain(grp["nodes"][0]["r"]["title"]) if grp["nodes"] else ""
            return f"[{node}: {plain(o['title'])}]({rel(option_path(ctx, grp), page)})"
    return None


def _sigil_link(ctx: Ctx, sigil: str, page: str) -> str:
    from .gear_pages import currency_path

    info = (ctx.loc.loot.get("items") or {}).get(sigil)
    return f"[{info['name']}]({rel(currency_path(sigil), page)})" if info else sigil


# ---- Uncut gems and the chisel ------------------------------------------------------------------


def _rank_levels(ctx: Ctx) -> list[tuple[int, int | None, int]]:
    """(first level, last level, rank) of a dropped uncut gem (GemItems.RankForLevel)."""
    data = _data(ctx)
    step, top = int(data["tunables"]["gem.rank.drop-step"]), data.get("maxRank", 5)
    return [(step * (r - 1), step * r - 1 if r < top else None, r) for r in range(1, top + 1)]


def _item_page(ctx: Ctx, prefab: str) -> str:
    ui, page, data = ctx.loc.ui, item_path(prefab), _data(ctx)
    it = data["items"][prefab]
    md = [f"# {it['name']}", ""]
    if art := _item_icon(ctx, prefab, page, 96):
        md += [art, ""]
    md += [f"<b>{it['type']}</b> · [{ui('gems.title')}]({rel(INDEX_PAGE, page)}#materials)", ""]
    md += [it["use"], ""] + [f"{line}  " for line in it["lines"]] + [""]
    if it.get("flavor"):
        md += [f"*{it['flavor']}*", ""]
    if it["cuts"]:
        md += [f"## {ui('gems.cuts_into')}", ""]
        gems = _by_id(ctx)
        md += _table(["", ui("col.name"), ui("col.effect"), ""],
                     [[_icon(ctx, gems[i], page, 32), gem_link(ctx, i, page), gem_text(ctx, gems[i], page=page),
                       _after_boss(ctx, gems[i], page) if gems[i].get("boss") else ""] for i in it["cuts"]])
        md += [ui("gems.cutting", link=rel(BOARD_PAGE, page) + "#ranks"), ""]
    else:
        md += [ui("gems.chisel", link=rel(BOARD_PAGE, page) + "#board"), ""]
    if it["cuts"]:
        md += [f"## {ui('gems.rank_by_level')}", "", ui("gems.rank_by_level_intro"), ""]
        md += _rank_table(ctx)
    md += _drops(ctx, prefab)
    given = [s for s, items in data.get("sigils", {}).items() if any(x.startswith(f"item:{prefab}:") for x in items)]
    if given:
        md += [ui("gems.item_from_sigils", sigils=", ".join(_sigil_link(ctx, s, page) for s in given)), ""]
    return "\n".join(md + _footer(ctx))


def _rank_table(ctx: Ctx) -> list[str]:
    from .item_pages import biome

    ui, rows = ctx.loc.ui, []
    for lo, hi, r in _rank_levels(ctx):
        rows.append([str(r), f"{lo}–{hi}" if hi is not None else f"{lo}+", biome(ctx, max(1, lo))])
    return _table([ui("gems.rank"), ui("gems.creature_level"), ui("gems.biome_from")], rows)


def _drops(ctx: Ctx, prefab: str) -> list[str]:
    """How it drops, as a currency of the "skill-gems" family (LootCatalog.Currency)."""
    from .gear_pages import _num as num, _pct
    from .item_pages import biome

    ui, catalog = ctx.loc.ui, _catalog(ctx)
    c = catalog.get(prefab)
    if not (c and c.get("weight", 0) > 0):
        return []
    family = [x for x in catalog.values() if x.get("family") == c.get("family") and x.get("weight", 0) > 0]
    level = max(1, c.get("minLevel") or 0)
    rows = [[ui("gear.family_label"), ui("gems.family")], [ui("items.tier"), str(c.get("tier", 1))],
            [ui("items.weight"), num(c["weight"])], [ui("gear.family_share"), _pct(c["weight"] / sum(x["weight"] for x in family))],
            [ui("items.min_level"), f"{biome(ctx, level)} <small>({level})</small>"]]
    return [f"## {ui('gear.drops')}", "", ui("gear.currency_drop_note"), ""] + _table([ui("col.property"), ui("col.value")], rows)


# ---- The board ----------------------------------------------------------------------------------


def _board_svg(ctx: Ctx) -> str:
    """The 19 cells as the board window lays them out (GemBoardPanel: pointy hexagons,
    x = R·√3·(q + r/2), y = 1.5·R·r, up on screen), open-from-the-start ones filled."""
    import math

    cells, size, out = _data(ctx)["cells"], 26.0, []
    pts = [(c, size * math.sqrt(3) * (c["q"] + c["r"] / 2), -1.5 * size * c["r"]) for c in cells]
    pad = size * 1.2
    xs, ys = [x for _, x, _ in pts], [y for _, _, y in pts]
    x0, y0, w, h = min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    for c, x, y in pts:
        corners = " ".join(f"{x + size * 0.95 * math.cos(math.radians(60 * i - 30)):.1f},{y + size * 0.95 * math.sin(math.radians(60 * i - 30)):.1f}"
                           for i in range(6))
        fill = "var(--md-accent-fg-color, #c9a227)" if c["open"] else "none"
        out.append(f'<polygon points="{corners}" fill="{fill}" fill-opacity="{0.35 if c["open"] else 0}" '
                   f'stroke="currentColor" stroke-width="1.5"/>')
    label = ctx.loc.ui("gems.board_alt", cells=len(cells), open=sum(c["open"] for c in cells))
    return (f'<svg class="pov-gem-board" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="{label}">{"".join(out)}</svg>')


def _term_text(ctx: Ctx, key: str, page: str) -> str:
    t = _data(ctx).get("terms", {}).get(key)
    return " ".join(to_md(line, ctx.loc, page) for line in t["text"]) if t else ""


def _hidden(ctx: Ctx, fid: str) -> list[str]:
    """A formula whose code changed since it was read: hidden until re-checked."""
    from .formula_pages import shown

    if shown(ctx, fid):
        return []
    ui = ctx.loc.ui
    return [f'!!! warning "{ui("formula.rechecking_title")}"', f"    {ui('formula.rechecking', version=ctx.data.version)}", ""]


def _board_page(ctx: Ctx) -> str:
    from .formula_pages import _anchor, _formula, _term, _values

    ui, page, data = ctx.loc.ui, BOARD_PAGE, _data(ctx)
    costs, curses = _values().get("gem-costs", {}), _values().get("gem-curses", {})
    t, gems = data["tunables"], data["gems"]
    cells = data["cells"]
    n = _named(ctx, page)
    md = [f"# {ui('gems.board')}", "", ui("gems.board_intro", index=rel(INDEX_PAGE, page)), ""]
    md += [f"> {data['text']['ui.help']}", ""]

    md += [f"## {ui('gems.cells')} {{ #board }}", "", _board_svg(ctx), ""]
    md += [ui("gems.cells_text", cells=len(cells), open=sum(c["open"] for c in cells),
              chisel=item_link(ctx, CHISEL, page)), ""]
    md += [f"> {data['text']['ui.locked-how']}", ""]

    md += [f"## {ui('gems.roles')} {{ #adjacency }}", ""]
    for role, key in (("Trigger", "gem:trigger"), ("Effect", "gem:effect"), ("Curse", "gem:curse"), ("Support", "gem:support"), ("Aura", "gem:aura")):
        md += [f"- **[{data['roles'][role]}]({rel(INDEX_PAGE, page)}#{role.lower()})**: {_term_text(ctx, key, page)}"]
    md += ["", ui("gems.adjacency_rules", malice=n["malice"], gifts=n["gifts"]), ""]
    md += [f"### {ui('gems.feeds')}", "", ui("gems.feeds_intro"), ""]
    triggers = [g for g in gems if g["role"] == "Trigger"]
    effects = [g for g in gems if g["role"] == "Effect"]
    rows = []
    for e in effects:
        row = [gem_link(ctx, e["id"], page)]
        for tr in triggers:
            why = data["feeds"][tr["id"]].get(e["id"])
            row.append("✓" if why is None else f'<span title="{why}">—</span>')
        rows.append(row)
    md += _table([ui("gems.effect")] + [gem_link(ctx, tr["id"], page) for tr in triggers], rows)
    md += [ui("gems.feeds_note", on_block=n["activate-block"]), ""]
    md += [f"### {ui('gems.states')}", "", ui("gems.states_intro"), ""]
    md += [f"- **{data['text'][f'state.{k}']}**: {ui(f'gems.state.{k}')}" for k in ("working", "idle", "incompatible", "off", "suspended", "capacity")]
    md += [""]

    md += [f"## {ui('gems.capacity_title')} {{ #capacity }}", ""]
    md += _hidden(ctx, "gem-capacity") or (
        _formula(ui("gems.capacity_formula", base=_num(t["gem.board.capacity"]), per=_num(t["gem.board.capacity-per-points"]),
                    most=_num(t["gem.board.capacity-growth-max"])))
        + [ui("gems.capacity_text", base=_num(t["gem.board.capacity"]), per=_num(t["gem.board.capacity-per-points"]),
              full=_num(t["gem.board.capacity"] + t["gem.board.capacity-growth-max"]),
              points=_num(t["gem.board.capacity-per-points"] * t["gem.board.capacity-growth-max"])), ""]
        + _table([ui("gems.role"), ui("gems.capacity")], _capacity_rows(ctx))
        + [ui("gems.over_capacity", over=data["text"]["ui.over"]), ""])

    md += [f"## {ui('gems.stamina_title')} {{ #stamina }}", ""]
    md += _hidden(ctx, "gem-costs") or (
        [ui("gems.stamina_text"), ""]
        + _formula(ui("gems.stamina_formula", support=_num(t["gem.board.support-cost"] * 100)))
        + [ui("gems.stamina_terms", long_seal=n["duration"], thrifty=n["economy"]), ""]
        + _stamina_example(ctx, page, n)
        + _table(["", ui("col.name"), ui("gems.price")],
                 [[_icon(ctx, g, page, 32), gem_link(ctx, g["id"], page), g["costText"]] for g in triggers]))

    md += [f"## {ui('gems.eitr_title')} {{ #eitr }}", "", _term_text(ctx, "gem:reserve", page), ""]
    auras = [g for g in gems if g["role"] == "Aura"]
    shares = any(g.get("reserveShare") is not None for g in auras)  # 6.0.7 on: a share of maximum eitr
    md += _hidden(ctx, "gem-costs") or (
        _formula(ui("gems.eitr_formula_share" if shares else "gems.eitr_formula", support=_num(t["gem.board.support-reserve"])))
        + ([ui("gems.eitr_share_terms", eitr=_term(ctx, "eitr", page), held=_anchor("held-eitr", page),
                  waiting=data["text"]["state.suspended"], cap=_num(costs.get("efficiency_cap", 0.75) * 100)), ""] if shares else
           [ui("gems.eitr_terms", eitr=_term(ctx, "eitr", page), waiting=data["text"]["state.suspended"],
               cap=_num(costs.get("efficiency_cap", 0.75) * 100)), ""])
        + [_eitr_circles(ctx, n), ""]
        + _eitr_example(ctx, page, n)
        + _table(["", ui("col.name"), ui("gems.price"), ui("gems.per_link")],
                 [[_icon(ctx, g, page, 32), gem_link(ctx, g["id"], page), _reserve_word(g), _per_link(ctx, g)] for g in auras]))
    md += _auras_section(ctx, page, n)

    md += [f"## {ui('gems.curses_title')} {{ #curses }}", "", _term_text(ctx, "gem:curse", page), ""]
    md += _hidden(ctx, "gem-curses") or (
        [ui("gems.curse_limit", base=_num(t["gem.curse.limit"]), nodes=_curse_nodes(ctx, "Limit", page) or "—",
            limit_max=_num(curses.get("limit_max", 8))), "",
         ui("gems.curse_store", malice=n["malice"]), ""]
        + _formula(ui("gems.curse_value_formula", heavy=n["support-curse-power"], max=_num(curses.get("max", 0.75) * 100)))
        + [ui("gems.curse_value_terms", nodes=_curse_nodes(ctx, "AilmentEffectPct", page) or "—"), ""]
        + _formula(ui("gems.curse_duration_formula", long_seal=n["duration"], heavy=n["support-curse-power"],
                      seconds=_num(curses.get("max_seconds", 120))))
        + [ui("gems.curse_duration_terms", nodes=_curse_nodes(ctx, "EffectDurationPct", page) or "—"), ""]
        + _table(["", ui("col.name"), ui("col.effect")],
                 [[_icon(ctx, g, page, 32), gem_link(ctx, g["id"], page), gem_text(ctx, g, page=page)] for g in gems if g["curse"]]))

    md += [f"## {ui('gems.ranks_title')} {{ #ranks }}", ""]
    md += _hidden(ctx, "gem-ranks") or (
        (_rank_rules(ctx, page) if "countStep" in data else
         [ui("gems.ranks_text", top=data.get("maxRank", 5), step=_num(data.get("rankStep", 0.1) * 100)), ""]
         + _formula(ui("gems.rank_formula", step=_num(data.get("rankStep", 0.1) * 100))))
        + [ui("gems.rank_level_text", step=_num(t["gem.rank.drop-step"])), ""]
        + _rank_table(ctx)
        + [ui("gems.cutting_text", trigger=item_link(ctx, _UNCUT["Trigger"], page), effect=item_link(ctx, _UNCUT["Effect"], page),
              support=item_link(ctx, _UNCUT["Support"], page)), ""])
    bosses = [g for g in gems if g.get("boss")]
    if bosses:
        md += [f"### {ui('gems.boss_gems')}", "", ui("gems.boss_gems_intro"), ""]
        md += _table([ui("gems.boss"), ui("gems.title")],
                     [[_boss_link(ctx, group[0], page), _names(ctx, [g["id"] for g in group], page)]
                      for group in _by_boss(bosses)])

    if data.get("sigils"):
        md += [f"## {ui('gems.sigils_title')} {{ #sigils }}", "", ui("gems.sigils_intro", rank=data.get("sigilRank", 3)), ""]
        md += _table([ui("gems.sigil"), ui("gems.received")],
                     [[_sigil_link(ctx, s, page), _given(ctx, given, page)] for s, given in data["sigils"].items()])
    md += [f"## {ui('gems.rules')}", "", f"- {data['text']['refuse.combat'].rstrip('.')}.", f"- {ui('gems.rule_same')}",
           f"- {ui('gems.rule_place')}", ""]
    return "\n".join(md + _footer(ctx))


def _named(ctx: Ctx, page: str) -> dict[str, str]:
    """Gems the board's rules name, linked, by id; "malice" and "gifts" for the two circles."""
    gems = _data(ctx)["gems"]
    out = {g["id"]: gem_link(ctx, g["id"], page) for g in gems}
    out["malice"] = next((out[g["id"]] for g in gems if g["malice"]), "")
    out["gifts"] = next((out[g["id"]] for g in gems if g["gifts"]), "")
    return out


def _param(g: dict, name: str) -> float:
    return next((p["value"] for p in g["params"] if p["name"] == name), 0.0)


def _stamina_example(ctx: Ctx, page: str, n: dict) -> list[str]:
    """A hit trigger beside an effect with two supports (GemBoard.Resolve: cost + support-cost each)."""
    gems, t = _by_id(ctx), _data(ctx)["tunables"]
    hit, effect = gems.get("activate-hit"), gems.get("storm-proc")
    if not hit or not effect:
        return []
    cost, support = hit["cost"] * 100, t["gem.board.support-cost"] * 100
    return [ctx.loc.ui("gems.stamina_example", trigger=n["activate-hit"], effect=n["storm-proc"], cost=_num(cost),
                       support=_num(support), total=_num(cost + 2 * support)), ""]


def _eitr_circles(ctx: Ctx, n: dict) -> str:
    """GemBoard.ReserveOf: the Circle of Malice's eitr per curse, and per Heavy Word on a curse
    (its "shorter" share of that)."""
    gems = _data(ctx)["gems"]
    malice = next((g for g in gems if g["malice"]), None)
    heavy = _by_id(ctx).get("support-curse-power")
    if not malice or not heavy:
        return ""
    per = _param(malice, "per-curse")
    # The Heavy Word's own rank (GemCatalog.Value of "shorter", 6.0.9 on), rank 1 before.
    shorter = next(p for p in heavy["params"] if p["name"] == "shorter")
    lo, hi = _value(heavy, shorter, 1) * per, _value(heavy, shorter, _data(ctx).get("maxRank", 5)) * per
    more = _num(lo) if _num(lo) == _num(hi) else f"{_num(lo)}–{_num(hi)}"
    return ctx.loc.ui("gems.eitr_circles", gifts=n["gifts"], malice=n["malice"], heavy=n["support-curse-power"],
                      curse=_num(per), more=more)


def _reserve_word(g: dict) -> str:
    """An aura's own reserve: a share of maximum eitr (6.0.7 on), before a flat amount."""
    return _pct(g["reserveShare"]) if g.get("reserveShare") is not None else _num(g.get("reserve") or 0)


def _eitr_example(ctx: Ctx, page: str, n: dict) -> list[str]:
    """An aura reserving a share of 200 maximum eitr with one support (GemBoard.ReserveOf)."""
    g = _by_id(ctx).get("renewal-aura")
    if not g or g.get("reserveShare") is None:
        return []
    eitr, support = 200, _data(ctx)["tunables"]["gem.board.support-reserve"]
    return [ctx.loc.ui("gems.eitr_example", aura=n["renewal-aura"], share=_pct(g["reserveShare"]), eitr=eitr,
                       support=_num(support), total=_num(g["reserveShare"] * eitr + support)), ""]


def _rank_rules(ctx: Ctx, page: str) -> list[str]:
    """What each rank above 1 changes (GemCatalog.Value): growing numbers, drawbacks (Soften),
    overflowing chances (CountChance), trigger chances (Rank, at most 100%) and the cooldowns of
    triggers that always fire (SureTrigger), and the numbers that stay unless a gem makes them its
    benefit (rankFree, GemDef.Grows)."""
    from .formula_pages import _formula, _term

    ui, data = ctx.loc.ui, _data(ctx)
    step, soft = _num(data["rankStep"] * 100), _num(data["drawbackStep"] * 100)
    count, cd = _num(data["countStep"] * 100), _num(data["cooldownStep"] * 100)
    gems = data["gems"]
    counts = ", ".join(gem_link(ctx, g["id"], page) for g in gems if g.get("counts"))
    grows = ", ".join(gem_link(ctx, g["id"], page) for g in gems if g.get("grows"))
    sure = ", ".join(gem_link(ctx, g["id"], page) for g in gems
                     if g["role"] == "Trigger" and next((p["value"] for p in g["params"] if p["name"] == "chance"), 0) >= 1)
    overflow = _term(ctx, "overflow-chance", page) or "overflowing chance"
    md = [ui("gems.ranks_rules", top=data.get("maxRank", 5)), ""]
    md += [f"- {ui('gems.rank_grow', step=step)}", f"- {ui('gems.rank_drawback', soft=soft)}",
           f"- {ui('gems.rank_count', gems=counts, overflow=overflow, count=count)}",
           f"- {ui('gems.rank_chance', step=step)}", f"- {ui('gems.rank_sure', gems=sure, cd=cd)}",
           f"- {ui('gems.rank_fixed', gems=grows)}", ""]
    md += _formula(ui("gems.rank_formula", step=step))
    md += _formula(ui("gems.rank_drawback_formula", soft=soft))
    md += _formula(ui("gems.rank_count_formula", count=count))
    md += _formula(ui("gems.rank_sure_formula", cd=cd))
    return md


def _auras_section(ctx: Ctx, page: str, n: dict) -> list[str]:
    """How a working aura's effect is reckoned (GemAuras.Strength), Inner Circle (BearerOnly), the
    Circle of Gifts' aura forms (Projection), the damage-over-time auras (GemAuras.Pulse, Retort,
    GemCast.Periodic) and the character's stats in gem effects (GemCast.With)."""
    from .formula_pages import _formula, _values

    data, ui, t = _data(ctx), ctx.loc.ui, _data(ctx)["tunables"]
    gems, v = _by_id(ctx), _values().get("gem-auras", {})
    step = _num(data.get("rankStep", 0.1) * 100)
    if "countStep" not in data or not all(k in gems for k in ("aura-self", "wide", "poison-aura", "effect-retort")):
        return []  # 6.0.9 on
    md = [f"## {ui('gems.auras_title')} {{ #auras }}", ""]
    hidden = _hidden(ctx, "gem-auras")
    if hidden:
        return md + hidden
    md += _formula(ui("gems.aura_strength_formula", step=step))
    md += [ui("gems.aura_strength_terms", inner=n["aura-self"], wide=n["wide"]), ""]
    md += [ui("gems.aura_inner", inner=n["aura-self"]), ""]
    if n.get("gifts"):
        md += [ui("gems.aura_gifts", gifts=n["gifts"], forms=rel(gem_path(next(g["id"] for g in data["gems"] if g["gifts"])), page) + "#aura-forms", step=step), ""]
    md += [ui("gems.aura_periodic", plague=n[_PERIODIC[0]], heat=n[_PERIODIC[1]], pulse=_num(t["gem.board.aura-pulse"]),
                  tick=_num(v.get("retort_tick", 0.25))), ""]
    md += [f"### {ui('gems.stats_title')}", "", ui("gems.stats_text"), ""]
    return md


def _capacity_rows(ctx: Ctx) -> list[list[str]]:
    """What a gem takes (GemCatalog: triggers 2, supports 1 per gem supported, the two circles 4,
    other effects and auras 3), from the gems themselves."""
    seen: dict[tuple[str, str], list[str]] = {}
    for g in _data(ctx)["gems"]:
        seen.setdefault((_data(ctx)["roles"][_group(g)], _capacity(ctx, g)), []).append(g["id"])
    per_role = defaultdict(int)
    for role, _ in seen:
        per_role[role] += 1
    # A role whose gems differ (the two circles among the auras): the few named.
    return [[f"{role}: {_names(ctx, ids, BOARD_PAGE)}" if per_role[role] > 1 and len(ids) <= 2 else role, cap]
            for (role, cap), ids in seen.items()]


def _per_link(ctx: Ctx, g: dict) -> str:
    """Eitr each support or curse beside an aura adds (GemBoard.ReserveOf)."""
    params = {p["name"]: p["value"] for p in g["params"]}
    if g["gifts"]:
        return ctx.loc.ui("gems.per_support", n=_num(params["per-support"]))
    out = ctx.loc.ui("gems.per_support", n=_num(_data(ctx)["tunables"]["gem.board.support-reserve"]))
    if g["malice"]:
        out += "<br>" + ctx.loc.ui("gems.per_curse", n=_num(params["per-curse"]))
    return out


def _curse_nodes(ctx: Ctx, stat: str, page: str) -> str:
    """Notables and keystones giving curses this stat (subject Curse), linked."""
    from .pages import node_path

    found = []
    for n in ctx.tree_nodes:
        if n["size"] in ("Keystone", "Notable") and any(m.get("stat") == stat and m.get("subject") == "Curse" for m in n.get("mods") or []):
            title = plain(n["r"]["title"])
            if title not in (f[0] for f in found):
                found.append((title, f"[{title}]({rel(node_path(ctx, n), page)})"))
    return ", ".join(link for _, link in found)


def _by_boss(gems: list[dict]) -> list[list[dict]]:
    groups: dict[str, list[dict]] = {}
    for g in gems:
        groups.setdefault(g["bossKey"], []).append(g)
    return list(groups.values())


def _given(ctx: Ctx, given: list[str], page: str) -> str:
    """SigilMigration.Compensation entries: "gem:<id>" or "item:<prefab>:<count>:<rank>"."""
    out = []
    for entry in given:
        kind, _, rest = entry.partition(":")
        if kind == "gem":
            out.append(gem_link(ctx, rest, page, icon=True))
        elif kind == "item":
            prefab, count, rank = (rest.split(":") + ["1", "1"])[:3]
            if prefab in _data(ctx)["items"]:  # the chisel has no rank
                key = "gems.given_item" if prefab == CHISEL else "gems.given_uncut"
                out.append(ctx.loc.ui(key, item=item_link(ctx, prefab, page), n=count, rank=rank))
    return ", ".join(out)


# ---- Links from other pages ---------------------------------------------------------------------


def sigil_gems_section(ctx: Ctx, item: str, page: str) -> list[str]:
    """On a sigil's page: the board items a character carrying it receives once
    (SigilMigration.Compensation)."""
    data = _data(ctx)
    given = data.get("sigils", {}).get(item)
    if not given:
        return []
    ui = ctx.loc.ui
    return [f"## {ui('gems.sigil_section')}", "",
            ui("gems.sigil_section_text", rank=data.get("sigilRank", 3), board=rel(BOARD_PAGE, page) + "#sigils"), "",
            _given(ctx, given, page), ""]
