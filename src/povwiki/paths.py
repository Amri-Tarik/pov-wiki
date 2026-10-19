from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CACHE = ROOT / ".cache"
MODS = CACHE / "mod"  # unpacked mod archives, one folder per version
EXTRACTED = CACHE / "extracted"  # data pulled out of the DLL, one folder per version

CONTENT = ROOT / "content"  # hand-written pages, per language
I18N = ROOT / "i18n"
BASE_CONFIG = ROOT / "zensical.toml"

BUILD = ROOT / "build"  # generated docs + per-language config
SITE = ROOT / "site"  # final static site (GitHub Pages artifact)
