"""Monster modifiers and rarity, as the game defines and shows them.

- Modifiers (RarityMods.All): name, description and icon key of each modifier a creature can
  wear, in the game's order. Their numbers are the settings in ModifierTuning (the elements share
  one "element" group), shown at their defaults the way the settings window prints them
  (Knob.Value.ToString(Fmt)). The "Modifier strength" setting rescales them all; at its default
  (1) the defaults are what creatures get.
- Bosses: modifiers a summoned boss never rolls by default (BossStars.DefaultModsOff).
- Rarity: the rarity a creature with N stars shows (CreatureStars.Tier), with its name and colour.
"""

from System import Single
from System.Globalization import CultureInfo


def _hex(color) -> str:
    return "#" + "".join(f"{round(float(c) * 255):02X}" for c in (color.r, color.g, color.b))


def render_monsters(icons, errors: list) -> dict:
    from PassiveTree import BossStars, CreatureStars, ModifierTuning, Rarity, RarityMods

    mods = []
    for m in RarityMods.All():
        try:
            mods.append({
                "id": m.Id, "name": m.Name, "about": m.About, "icon": icons.by_key(m.Icon),
                "settings": [{
                    "label": k.Shown, "about": k.Hint,
                    "value": Single(k.Default).ToString(k.Fmt, CultureInfo.InvariantCulture),
                } for k in ModifierTuning.Of(m.Id)],
            })
        except Exception as ex:
            errors.append({"monster mod": m.Id, "error": str(ex).split("\n")[0]})

    tiers: dict = {}
    for stars in range(0, 11):
        tier = CreatureStars.Tier(stars)
        style = Rarity.Of(tier)
        t = tiers.setdefault(style.Id, {"id": style.Id, "name": style.Shown, "color": _hex(style.Name), "stars": []})
        t["stars"].append(stars)
    off = [s.strip() for s in BossStars.DefaultModsOff.split(",") if s.strip()]
    return {"mods": mods, "rarity": list(tiers.values()), "bossOff": off}
