"""Old versions' cached data, kept small: a local git store of every version's unpacked mod,
extracted data and decompiled code (.cache/archive.git, never pushed: the mod's licence forbids
publishing it).

Git keeps each file once however many versions share it (the images, the unchanged code) and
stores the rest as deltas when it packs, so the whole history takes about the room of a version or
two. `povwiki archive` adds every version to the store, checks that each stored copy is identical
to the files on disk, and then deletes the copies the pipeline no longer needs. The newest version
stays whole (mod, extracted data, decompiled code), and so does the extracted data of the one
before it, which the patch record compares against. Anything else comes back with
`povwiki archive --restore <version>`, and the pipeline restores what it needs by itself: the
previous version for a patch record (patch_pages.update), an old version's code for
`povwiki formulas --diff` (decompile.decompile).

Not stored: rendered copies of worktree agents (extracted/<v>/rendered-*) and the icon cache
(extracted/<v>/web), which a build makes again from the images.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .paths import CACHE, EXTRACTED, MODS

STORE = CACHE / "archive.git"
DECOMPILED = CACHE / "decompiled"
DOWNLOADS = CACHE / "downloads"
# The parts of a version, as folders of the cache: unpacked mod, extracted data, decompiled code.
PARTS = ("mod", "extracted", "decompiled")
_SKIP = ("rendered-", "web")  # top-level entries of extracted/<v> left out of the store


def _key(v: str):
    return tuple(int(p) if p.isdigit() else p for p in v.split("."))


def _git(*args: str, index: Path | None = None, check: bool = True, capture: bool = True) -> str:
    env = dict(os.environ)
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    r = subprocess.run(["git", f"--git-dir={STORE}", f"--work-tree={CACHE}", *args], env=env, check=check, cwd=CACHE,
                       stdout=subprocess.PIPE if capture else None, text=True, encoding="utf-8")
    return (r.stdout or "").strip()


def _init() -> None:
    if not STORE.exists():
        subprocess.run(["git", "init", "--bare", "-q", str(STORE)], check=True)
        # Bytes as they are: no line-ending changes, no packing of huge files without deltas.
        for k, v in (("core.autocrlf", "false"), ("core.safecrlf", "false"), ("core.bigFileThreshold", "512m"),
                     ("gc.auto", "0"), ("core.longpaths", "true"), ("user.name", "povwiki"), ("user.email", "povwiki@localhost")):
            _git("config", k, v)


def _paths(version: str) -> list[str]:
    """The cache paths (relative to .cache) that hold this version."""
    out = []
    for part in PARTS:
        root = CACHE / part / version
        if not root.exists():
            continue
        if part == "extracted":
            out += [f"{part}/{version}/{e.name}" for e in sorted(root.iterdir()) if not e.name.startswith(_SKIP)]
        else:
            out.append(f"{part}/{version}")
    return out


def _tree(version: str) -> str | None:
    """The tree id of the files on disk for this version (as the store would keep them)."""
    paths = _paths(version)
    if not paths:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        _git("add", "-f", "--", *paths, index=index)
        return _git("write-tree", index=index)


def stored() -> dict[str, str]:
    """version -> its tree id in the store."""
    if not STORE.exists():
        return {}
    out = {}
    for line in _git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/tags/").splitlines():
        tag, commit = line.split()
        out[tag] = _git("rev-parse", f"{commit}^{{tree}}")
    return out


def _parts_of(tree: str) -> set[str]:
    return set(_git("ls-tree", "--name-only", tree).split())


def add(version: str) -> str:
    """Store this version's files (all parts on disk); a version stored before keeps the parts it
    had that are no longer on disk. Returns the stored tree id."""
    _init()
    tree = _tree(version)
    if tree is None:
        raise SystemExit(f"nothing of {version} on disk")
    old = stored().get(version)
    if old and old != tree:  # merge: parts now on disk replace theirs, the others stay
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index"
            _git("read-tree", old, index=index)
            on_disk = [p for p in PARTS if (CACHE / p / version).exists()]
            _git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *(f"{p}/{version}" for p in on_disk), index=index)
            _git("add", "-f", "--", *_paths(version), index=index)
            tree = _git("write-tree", index=index)
    if old == tree:
        return tree
    commit = _git("commit-tree", tree, "-m", f"Path of Valheiman {version}")
    _git("tag", "-f", version, commit)
    return tree


def verified(version: str, part: str) -> bool:
    """Whether the store holds exactly the files on disk for this part of the version."""
    tree = stored().get(version)
    root = CACHE / part / version
    if tree is None or not root.exists():
        return False
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        paths = [p for p in _paths(version) if p.startswith(f"{part}/")]
        _git("add", "-f", "--", *paths, index=index)
        mine = _git("rev-parse", f"{_git('write-tree', index=index)}:{part}/{version}", check=False)
    theirs = _git("rev-parse", f"{tree}:{part}/{version}", check=False)
    return bool(mine) and mine == theirs


def restore(version: str, parts: tuple[str, ...] = PARTS) -> list[str]:
    """Put a stored version's parts back into the cache (the ones not already there)."""
    tree = stored().get(version)
    if tree is None:
        return []
    have = _parts_of(tree)
    back = [p for p in parts if p in have and not (CACHE / p / version).exists()]
    if back:
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index"
            _git("read-tree", tree, index=index)
            _git("checkout", tree, "--", *(f"{p}/{version}" for p in back), index=index)
    return back


def keep() -> dict[str, set[str]]:
    """part -> the versions kept on disk: everything of the newest, the extracted data of the one
    before it (the patch record's comparison)."""
    versions = sorted({p.name for part in PARTS for p in (CACHE / part).glob("*") if p.is_dir() and p.name[0].isdigit()}
                      | set(stored()), key=_key)
    if not versions:
        return {p: set() for p in PARTS}
    latest = versions[-1]
    before = versions[-2] if len(versions) > 1 else latest
    return {"mod": {latest}, "decompiled": {latest}, "extracted": {latest, before}}


def run(dry: bool = False) -> None:
    """Store every version, then delete what is verified stored and not kept, and the mod zips
    already stored as unpacked folders (except the newest zip, which `povwiki fetch` checks for)."""
    on_disk = sorted({p.name for part in PARTS for p in (CACHE / part).glob("*") if p.is_dir() and p.name[0].isdigit()}, key=_key)
    kept = keep()
    freed = 0
    for v in on_disk:
        if not dry:
            add(v)
            print(f"stored {v}")
        for part in PARTS:
            root = CACHE / part / v
            if v in kept[part] or not root.exists():
                continue
            size = _size(root)
            if dry:
                print(f"would delete {part}/{v} ({size / 2**20:.0f} MB)")
                freed += size
            elif verified(v, part):
                shutil.rmtree(root, onerror=_writable)
                freed += size
                print(f"deleted {part}/{v} ({size / 2**20:.0f} MB, stored)")
            else:
                print(f"kept {part}/{v}: the stored copy differs, so it was not deleted")
    zips = sorted(DOWNLOADS.glob("PathOfValheiman-*.zip"), key=lambda z: _key(z.stem.split("-", 1)[1]))
    have = stored()
    for z in zips[:-1]:
        v = z.stem.split("-", 1)[1]
        if v in have and "mod" in _parts_of(have[v]):
            freed += z.stat().st_size
            print(f"{'would delete' if dry else 'deleted'} downloads/{z.name} (its unpacked mod is stored)")
            if not dry:
                z.unlink()
    if not dry and STORE.exists():
        print("packing the store (deltas between versions)...")
        _git("-c", "pack.windowMemory=512m", "repack", "-a", "-d", "-f", "--window=50", "--depth=50", "-q", capture=False)
        _git("prune-packed")
        print(f"store: {_size(STORE) / 2**20:.0f} MB")
    print(f"{'would free' if dry else 'freed'} {freed / 2**30:.1f} GB")


def _size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _writable(func, path, _exc) -> None:
    """Git and the decompiler leave read-only files on Windows; make them writable and retry."""
    os.chmod(path, 0o666)
    func(path)


def ensure(version: str, part: str) -> bool:
    """Whether this part of the version is on disk, restoring it from the store when it is not."""
    if (CACHE / part / version).exists():
        return True
    return part in restore(version, (part,))


def versions_with(part: str) -> list[str]:
    """Versions that have this part on disk or in the store."""
    out = {p.name for p in (CACHE / part).glob("*") if p.is_dir() and p.name[0].isdigit()}
    out |= {v for v, tree in stored().items() if part in _parts_of(tree)}
    return sorted(out, key=_key)


__all__ = ["run", "restore", "ensure", "versions_with", "stored", "EXTRACTED", "MODS"]
