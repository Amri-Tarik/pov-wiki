import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# POVWIKI_CACHE: another checkout's cache (a git worktree shares the main one's extracted data).
CACHE = Path(os.environ["POVWIKI_CACHE"]) if os.environ.get("POVWIKI_CACHE") else ROOT / ".cache"
MODS = CACHE / "mod"  # unpacked mod archives, one folder per version
EXTRACTED = CACHE / "extracted"  # data pulled out of the DLL, one folder per version
# POVWIKI_RENDERED: the folder rendered game text goes to and is read from, inside a version's
# extracted data; a worktree renders its own copy ("rendered-<name>") without touching the main one.
RENDERED = os.environ.get("POVWIKI_RENDERED") or "rendered"

CONTENT = ROOT / "content"  # hand-written pages, per language
I18N = ROOT / "i18n"
BASE_CONFIG = ROOT / "zensical.toml"

BUILD = ROOT / "build"  # generated docs + per-language config
SITE = ROOT / "site"  # final static site (GitHub Pages artifact)
