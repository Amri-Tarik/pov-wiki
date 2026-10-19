"""Download the latest mod release from hexium.

The mod page carries schema.org JSON-LD (`SoftwareApplication`) with `softwareVersion` and
`downloadUrl`, which is more stable than scraping the page layout.
"""

import json
import re
import shutil
import urllib.request
from pathlib import Path

from .paths import CACHE

MOD_PAGE = "https://valheim.hexium.gg/mods/treextr/PathOfValheiman"
DOWNLOADS = CACHE / "downloads"
USER_AGENT = "pov-wiki (+https://github.com/Amri-Tarik/pov-wiki)"

_LD_JSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _get(url: str):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60)


def latest_release() -> tuple[str, str]:
    """Return (version, download url) of the latest release."""
    html = _get(MOD_PAGE).read().decode("utf-8")
    for block in _LD_JSON.findall(html):
        data = json.loads(block)
        if data.get("@type") == "SoftwareApplication":
            return data["softwareVersion"], data["downloadUrl"]
    raise SystemExit(f"No SoftwareApplication JSON-LD found on {MOD_PAGE}; the page layout changed.")


def fetch() -> Path:
    """Download the latest release zip into .cache/downloads/ (skipped if already there)."""
    version, url = latest_release()
    target = DOWNLOADS / f"PathOfValheiman-{version}.zip"
    if target.exists():
        print(f"{version} already downloaded")
        return target
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    print(f"downloading {version} from {url}")
    partial = target.with_suffix(".part")
    with _get(url) as resp, open(partial, "wb") as f:
        shutil.copyfileobj(resp, f)
    partial.replace(target)
    return target
