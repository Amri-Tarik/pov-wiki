"""Bosses and creatures the mod adds, and its changes to Valheim's bosses.

The mod builds every creature in a running game by copying a Valheim one, so this lists what
those copies are made of, from the mod's own tables and constants:
- Mist Mother (MistMother, BlightMist): a Seeker Queen called at the Altar of the Mist Mother
  once the Blight Mist's bar is full. Like every creature of a mist she is matched to the
  mist's "anchor" creature (RunicKin.anchors, by the mist's top biome), then made stronger
  (BlightMist.HealthMult/DamageMult; the warden also WardenHealth/WardenDamage).
- Monolith bosses (MonolithBoss.All: Rungard, Morgrim): stone golems called at an Altar of
  Summoning with Offering visages; health, damage and the Stone Summoning timings are tunables
  (Tunables.Of). Rune spikes: the numbers in MonolithBoss.Brain.Spikes are written inline
  (first after 8 s, every 16 s, 60 damage, 10 or 12 spikes): keep in sync.
- Valheim's bosses (CreatureLevels.Bosses): which biome each one stands for.
- Runic kin (RunicKin.specs, RunicBiomeKin.kinds and rosters): the glowing copies that guard
  monoliths, by rank and biome.
- Blight creatures: their names in a mist (BlightMist.HeraldName: keep the species in sync)
  and the Blight Hare (BlightHare constants; 60% blunt, 40% poison written inline).
"""

from System.Reflection import BindingFlags

_ANY = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic


def _type(name: str):
    from System import AppDomain

    asm = next(a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == "PathOfValheiman")
    return asm.GetType(f"PassiveTree.{name}")


def _static(type_name: str, field: str):
    return _type(type_name).GetField(field, _ANY).GetValue(None)


def _tunables(prefix: str) -> dict:
    from PassiveTree import Tunables

    return {k.Id: float(Tunables.Of(k.Id)) for k in Tunables.All if k.Id.startswith(prefix)}


def _list(strings) -> list[str]:
    return [str(s) for s in strings] if strings is not None else []


def render_bosses(errors: list) -> dict:
    from PassiveTree import BlightMist, BossRoster, BossSpikes, CreatureLevels, L, MistMother, MonolithBoss

    out: dict = {}
    try:
        pin = {b.Id: f"PassiveTree.map.{b.Pin}.png" for b in (BossRoster.MistMother, BossRoster.Rungard, BossRoster.Morgrim)}
        out["mistMother"] = {
            "prefab": MistMother.Name, "name": MistMother.Title, "pin": pin["mist-mother"], "source": "SeekerQueen",
            "altar": L.Id("blight.altar.name-mother", ""), "altarFill": L.Id("blight.altar.fill", ""),
            "health": float(BlightMist.HealthMult), "damage": float(BlightMist.DamageMult),
            "wardenHealth": float(BlightMist.WardenHealth), "wardenDamage": float(BlightMist.WardenDamage),
            "anchors": {str(kv.Key): str(kv.Value) for kv in _static("RunicKin", "anchors")},
        }
        shared = _tunables("monolith-boss.")
        out["monolith"] = {
            "bosses": [{
                "prefab": str(d.Name), "key": str(d.Key), "name": d.Title, "pin": pin[d.Roster.Id], "source": "StoneGolem",
                "essence": str(d.Essence), "visage": str(d.Visage), "native": int(d.Native),
                "health": shared[f"{d.Knob}-health"], "damage": shared[f"{d.Knob}-damage"],
                "level": shared[f"{d.Knob}-level"],
            } for d in MonolithBoss.All],
            "tunables": {k.removeprefix("monolith-boss."): v for k, v in shared.items()},
            "offering": int(MonolithBoss.Offering),
            "spikes": {"first": 8, "every": 16, "damage": 60, "count": {"PT_Rungard": 10, "PT_Morgrim": 12},
                       "warn": float(BossSpikes.Warn), "radius": float(BossSpikes.Radius)},
            "altar": L.Id("summon-altar.name", ""),
            "stoneText": L.Id("monolith-boss.stone", ""),
            "revealed": L.Id("summon-altar.revealed", ""),
        }
        out["vanilla"] = [{"prefab": str(b.Item1), "biome": str(b.Item3)} for b in CreatureLevels.Bosses]
        kin = _type("RunicKin")
        specs = kin.GetField("specs", _ANY).GetValue(None)
        spec = specs[0].GetType()
        out["runic"] = {
            "base": [{"prefab": str(spec.GetField("Prefab").GetValue(s)), "source": str(spec.GetField("Source").GetValue(s)),
                      "rank": str(spec.GetField("Rank").GetValue(s))} for s in specs],
            "kinds": [],
            "rosters": {},
        }
        kinds = _static("RunicBiomeKin", "kinds")
        kind = kinds[0].GetType()
        for k in kinds:
            out["runic"]["kinds"].append({
                "id": str(kind.GetField("Id").GetValue(k)), "sources": _list(kind.GetField("Sources").GetValue(k)),
                "rank": str(kind.GetField("Look").GetValue(k)),
            })
        for kv in _static("RunicBiomeKin", "rosters"):
            r = kv.Value
            out["runic"]["rosters"][str(kv.Key)] = {
                slot: _list(r.GetType().GetField(slot).GetValue(r)) for slot in ("Common", "Brute", "Special", "Champion")}
        out["blight"] = {
            "names": {
                "Seeker": L.Id("blight.creature.herald", ""), "SeekerBrute": L.Id("blight.creature.brute", ""),
                "Tick": L.Id("blight.creature.tick", ""), "SeekerBrood": L.Id("blight.creature.brood", ""),
                "Gjall": L.Id("blight.creature.gjall", ""),
            },
            "roster": str(BlightMist.Roster),
            "hare": {"prefab": str(_static("BlightHare", "Name")), "sight": float(_static("BlightHare", "Sight")),
                     "burst": float(_static("BlightHare", "Burst")), "radius": float(_static("BlightHare", "Radius")),
                     "damage": float(_static("BlightHare", "BaseDamage")), "blunt": 0.6, "poison": 0.4},
        }
    except Exception as ex:
        errors.append({"bosses": str(ex).split("\n")[0]})
    return out
