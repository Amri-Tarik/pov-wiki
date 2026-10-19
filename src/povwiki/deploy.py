"""Publish site/ to the gh-pages branch, which GitHub Pages serves as is (no Actions run).

The branch only ever holds the latest build: each deploy is a single fresh commit, force-pushed.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from .paths import ROOT, SITE

BRANCH = "gh-pages"


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def deploy(message: str) -> None:
    if not (SITE / "index.html").exists():
        raise SystemExit("Nothing to deploy: run `povwiki build` first.")
    remote = _git("remote", "get-url", "origin", cwd=ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "site"
        shutil.copytree(SITE, work)
        (work / ".nojekyll").touch()  # serve files as they are, no Jekyll pass
        _git("init", "-q", "-b", BRANCH, cwd=work)
        _git("add", "-A", cwd=work)
        _git("commit", "-q", "-m", message, cwd=work)
        _git("push", "-q", "--force", remote, BRANCH, cwd=work)
    print(f"deployed to {BRANCH}: {message}")
