"""Publish site/ to the gh-pages branch, which GitHub Pages serves as is (no Actions run).

The branch only ever holds the latest build: each deploy is a single fresh commit, force-pushed.
A custom domain (zensical.toml site_url not on github.io) goes in a CNAME file at the branch
root: GitHub Pages reads the domain from there, so every deploy must carry it.
"""

import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from .paths import ROOT, SITE

BRANCH = "gh-pages"


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def custom_domain() -> str | None:
    """The site's own domain, from site_url; None when it is served from github.io."""
    url = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8")).get("project", {}).get("site_url", "")
    host = urlparse(url).hostname or ""
    return None if not host or host.endswith(".github.io") else host


def deploy(message: str) -> None:
    if not (SITE / "index.html").exists():
        raise SystemExit("Nothing to deploy: run `povwiki build` first.")
    remote = _git("remote", "get-url", "origin", cwd=ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "site"
        shutil.copytree(SITE, work)
        (work / ".nojekyll").touch()  # serve files as they are, no Jekyll pass
        if domain := custom_domain():
            (work / "CNAME").write_text(domain + "\n", encoding="utf-8")
        _git("init", "-q", "-b", BRANCH, cwd=work)
        _git("add", "-A", cwd=work)
        _git("commit", "-q", "-m", message, cwd=work)
        _git("push", "-q", "--force", remote, BRANCH, cwd=work)
    print(f"deployed to {BRANCH}: {message}")
