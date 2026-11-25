"""Version and git commit metadata resolution for pokeymans."""

from __future__ import annotations

import subprocess
from pathlib import Path

BASE_VERSION = "0.1.0"


def _detect_git_info(start_dir: Path) -> tuple[str | None, bool]:
    """Detect short git commit SHA and dirty flag if running inside a git checkout."""
    repo_root: Path | None = None
    for parent in (start_dir, *start_dir.parents):
        if (parent / ".git").exists():
            repo_root = parent
            break
    if repo_root is None:
        return None, False

    try:
        sha_proc = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        commit = sha_proc.stdout.strip()
        if not commit:
            return None, False

        status_proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        dirty = bool(status_proc.stdout.strip())
        return commit, dirty
    except (OSError, subprocess.SubprocessError):
        return None, False


def format_pep440_version(base: str, commit: str | None, dirty: bool = False) -> str:
    """Format PEP 440 version string with optional `+g<sha>[.dirty]` local tag."""
    if not commit:
        return base
    suffix = ".dirty" if dirty else ""
    return f"{base}+g{commit}{suffix}"


def _resolve_version() -> tuple[str, str]:
    # 1. Prefer build-time baked metadata inside installed wheels (`_build_info.py`).
    try:
        from pokeymans import _build_info  # type: ignore[attr-defined]

        ver = getattr(_build_info, "VERSION", "")
        commit = getattr(_build_info, "GIT_COMMIT", "unknown")
        if ver:
            return str(ver), str(commit)
    except ImportError:
        pass

    # 2. Fallback to live git detection when running directly from source / editable install.
    commit, dirty = _detect_git_info(Path(__file__).resolve().parent)
    if commit:
        return format_pep440_version(BASE_VERSION, commit, dirty=dirty), commit

    # 3. Last fallback: installed package metadata or plain BASE_VERSION.
    try:
        from importlib.metadata import version as dist_version

        return dist_version("pokeymans"), "unknown"
    except Exception:
        return BASE_VERSION, "unknown"


__version__, __commit__ = _resolve_version()
