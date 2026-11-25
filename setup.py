"""Build hook injecting git commit ID into wheel version and `_build_info.py`."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent


def _read_base_version() -> str:
    text = (ROOT / "src" / "pokeymans" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'^BASE_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find BASE_VERSION in src/pokeymans/_version.py")
    return match.group(1)


def _git_info() -> tuple[str | None, bool]:
    if not (ROOT / ".git").exists():
        return None, False
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not commit:
            return None, False
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=str(ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return None, False


BASE_VERSION = _read_base_version()
GIT_COMMIT, GIT_DIRTY = _git_info()
FULL_VERSION = (
    f"{BASE_VERSION}+g{GIT_COMMIT}{'.dirty' if GIT_DIRTY else ''}"
    if GIT_COMMIT
    else BASE_VERSION
)


class BuildPyWithGitInfo(_build_py):
    """Write `pokeymans/_build_info.py` into the build output without dirtying `src/`."""

    def run(self) -> None:
        super().run()
        out_file = Path(self.build_lib) / "pokeymans" / "_build_info.py"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(
            "# Auto-generated during wheel build by setup.py\n"
            f'VERSION = "{FULL_VERSION}"\n'
            f'GIT_COMMIT = "{GIT_COMMIT or "unknown"}"\n'
            f"GIT_DIRTY = {bool(GIT_DIRTY)!r}\n",
            encoding="utf-8",
        )


setup(
    version=FULL_VERSION,
    cmdclass={"build_py": BuildPyWithGitInfo},
)
