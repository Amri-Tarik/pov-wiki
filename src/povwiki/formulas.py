"""Formulas: the game's math, written down by hand and checked against the code on every build.

A formula can't be extracted like the game's text: someone reads the code and writes it down
(formulas/registry.toml: its numbers, and the code it was read from). So that a patch can't
leave a wrong formula on the site, each formula lists its "anchors", the pieces of decompiled
code it depends on (povwiki.decompile), and the registry keeps a fingerprint of them as they
were when the formula was last checked:

    anchors = ["PassiveTree/XpSources.cs :: XpSources.Award",       # a method (or property)
               "valheim/HitData.cs :: HitData.ApplyArmor#1",          # Valheim's own code
               'PassiveTree/Plugin.cs :: "Experience per star"']    # the statement with this C# string

On every build the anchors are hashed again. A formula whose code changed (or can't be found)
is hidden from the site and reported; once re-read and updated, `povwiki formulas --accept ID`
records the new fingerprint.
"""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from .paths import ROOT

REGISTRY = ROOT / "formulas" / "registry.toml"
HEADER = """# The game's formulas, as read from the mod's code (see src/povwiki/formulas.py).
#
# Each formula: its page text is in i18n/ui/<lang>.toml under [formula.<id>]; "values" holds the
# numbers that can't be read from the game data (BepInEx setting defaults, numbers written inline
# in the code); "anchors" lists the code it was read from. The build hides a formula whose anchors
# changed since "checked"; re-read it, update it, then `povwiki formulas --accept <id>`.
# Anchors: "File.cs :: Type.Member" (a method, property or field; "#2" for the second overload;
# "valheim/<Type>.cs" for Valheim's own code)
# or 'File.cs :: "text"' (the one statement holding that C# string or code).

"""
_IL = re.compile(r"^\s*//IL_.*$", re.M)  # decompiler notes, not code


@dataclass
class Status:
    id: str
    ok: bool
    reason: str = ""  # why it is hidden: "changed", or the anchor that can't be found


def load() -> dict:
    return tomllib.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"formula": []}


def _member(source: str, type_name: str, member: str) -> str | None:
    """A method or property's declaration and body, braces matched, in the type's own text.
    "Name#2" picks the second overload."""
    member, _, nth = member.partition("#")
    start = re.search(rf"\b(class|struct|record)\s+{re.escape(type_name)}\b", source)
    if not start:
        return None
    decl = re.compile(rf"^[ \t]*(?:\[[^\]]*\]\s*)*(?:(?:public|private|internal|protected|static|override|virtual|readonly|unsafe|extern|new|async|sealed)\s+)*"
                      rf"[\w<>\[\],.? ()]*?\b{re.escape(member)}\b\s*(?:<[^>]*>)?\s*(?:\(|=>|$|\{{|=)", re.M)
    found = [m for m in decl.finditer(source, start.end()) if not source[m.start():m.end()].lstrip().startswith(("return", "if", "else"))]
    found = [m for m in found if not re.search(r";\s*$", source[m.start():source.find("\n", m.start())]) or "=" in source[m.start():source.find("\n", m.start())]]
    index = int(nth) - 1 if nth else 0
    if len(found) <= index:
        return None
    i = found[index].start()
    line_end = source.find("\n", i)
    line = source[i:line_end]
    if line.rstrip().endswith(";"):  # a one-line field or expression-bodied member
        return line
    depth, j = 0, source.find("{", i)
    if j < 0:
        return None
    while j < len(source):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[i:j + 1]
        j += 1
    return None


def _statement(source: str, needle: str) -> str | None:
    """The whole statement (up to its ';') containing a substring; it must be unique."""
    hits = [m.start() for m in re.finditer(re.escape(needle), source)]
    if len(hits) != 1:
        return None
    start = source.rfind("\n", 0, hits[0]) + 1
    end = source.find(";", hits[0])
    line_end = source.find("\n", hits[0])
    if line_end >= 0 and source[start:line_end].rstrip().endswith(","):  # an element of a long list (Tunables)
        return source[start:line_end].rstrip()
    return source[start:end + 1] if end >= 0 else None


def anchor_text(code: Path, anchor: str) -> str | None:
    """The code an anchor points at, or None when it can't be found (exactly once)."""
    path, _, what = (part.strip() for part in anchor.partition("::"))
    if path.startswith("valheim/"):  # Valheim's own code: valheim/<Type>.cs
        from .decompile import valheim_type

        file = valheim_type(path.removeprefix("valheim/").removesuffix(".cs"))
    else:
        file = code / path
    if not file.exists():
        return None
    source = _IL.sub("", file.read_text(encoding="utf-8-sig"))
    if what.startswith('"'):  # the statement holding this text: a C# string literal, quotes and all, or code
        return _statement(source, what) or _statement(source, what[1:-1])
    type_name, _, member = what.rpartition(".")
    return _member(source, type_name, member)


def fingerprint(code: Path, anchors: list[str]) -> tuple[str | None, str]:
    """(hash of every anchor's code, whitespace ignored; or None and the anchor that's missing)."""
    h = hashlib.sha1()
    for anchor in anchors:
        text = anchor_text(code, anchor)
        if text is None:
            return None, anchor
        h.update(re.sub(r"\s+", " ", text).strip().encode())
        h.update(b"\0")
    return h.hexdigest()[:12], ""


def check(version: str) -> dict[str, Status]:
    """Every formula's status for a mod version: shown (its code is as checked) or hidden."""
    from .decompile import decompile

    code = decompile(version)
    out = {}
    for f in load()["formula"]:
        digest, missing = fingerprint(code, f["anchors"])
        if digest is None:
            out[f["id"]] = Status(f["id"], False, f"anchor not found: {missing}")
        elif digest != f.get("fingerprint"):
            out[f["id"]] = Status(f["id"], False, "code changed since it was checked")
        else:
            out[f["id"]] = Status(f["id"], True)
    return out


def accept(version: str, ids: list[str]) -> None:
    """Record the current code of these formulas as checked (after re-reading them)."""
    from .decompile import decompile

    code, reg = decompile(version), load()
    for f in reg["formula"]:
        if f["id"] in ids or ids == ["all"]:
            digest, missing = fingerprint(code, f["anchors"])
            if digest is None:
                raise SystemExit(f"{f['id']}: anchor not found: {missing}")
            f["fingerprint"], f["checked"] = digest, version
            print(f"{f['id']}: checked against {version} ({digest})")
    REGISTRY.write_text(HEADER + tomli_w.dumps(reg), encoding="utf-8")


def report(version: str) -> None:
    for s in check(version).values():
        print(f"  {'ok    ' if s.ok else 'HIDDEN'}  {s.id}{'' if s.ok else '  - ' + s.reason}")
