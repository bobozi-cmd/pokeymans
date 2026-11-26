"""Version and git tag/commit metadata resolution for pokeymans."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

BASE_VERSION = "0.1.0"

_PEP440_TAG_RE = re.compile(r"^v?(\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?)$")
_DESCRIBE_RE = re.compile(r"^(?P<tag>.+)-(?P<dist>\d+)-g(?P<sha>[0-9a-f]+)$")


def parse_tag_version(tag: str) -> str | None:
    """Extract a PEP 440 version from a git tag like `v0.2.0` or `v0.2.0rc1`."""
    match = _PEP440_TAG_RE.match(tag.strip())
    if not match:
        return None
    return match.group(1)


def format_pep440_version(
    base: str,
    commit: str | None,
    *,
    distance: int = 0,
    dirty: bool = False,
) -> str:
    """Format a PEP 440 version string with optional `.post<N>` and `+g<sha>[.dirty]`."""
    ver = f"{base}.post{distance}" if distance > 0 else base
    if not commit:
        return ver
    suffix = ".dirty" if dirty else ""
    return f"{ver}+g{commit}{suffix}"


def _find_git_root(start_dir: Path) -> Path | None:
    for parent in (start_dir, *start_dir.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _run_git(repo_root: Path, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_git_version(
    repo_root: Path,
    *,
    fallback_base: str = BASE_VERSION,
) -> tuple[str, str | None, bool]:
    """Compute `(full_version, commit_sha, dirty)` from git tags & HEAD in `repo_root`.

    Resolution priority for the version base:
        1. `POKEY_VERSION` environment variable (if set and valid PEP 440).
        2. Exact `v*` git tag on `HEAD` -> `<tag>+g<sha>[.dirty]`.
        3. Commits ahead of latest `v*` tag -> `<tag>.post<N>+g<sha>[.dirty]`.
        4. Fallback `BASE_VERSION` -> `<BASE_VERSION>+g<sha>[.dirty]`.
    """
    env_override = os.environ.get("POKEY_VERSION", "").strip()
    explicit_base = parse_tag_version(env_override) if env_override else None

    if not (repo_root / ".git").exists():
        return (explicit_base or fallback_base), None, False

    commit = _run_git(repo_root, ["rev-parse", "--short=7", "HEAD"])
    if not commit:
        return (explicit_base or fallback_base), None, False

    status_out = _run_git(repo_root, ["status", "--porcelain", "--untracked-files=no"])
    dirty = bool(status_out)

    if explicit_base:
        return (
            format_pep440_version(explicit_base, commit, distance=0, dirty=dirty),
            commit,
            dirty,
        )

    # Prefer an exact tag match on HEAD if multiple tags exist.
    exact_tag = _run_git(repo_root, ["describe", "--tags", "--exact-match", "--match", "v*", "HEAD"])
    if exact_tag:
        parsed = parse_tag_version(exact_tag)
        if parsed:
            return (
                format_pep440_version(parsed, commit, distance=0, dirty=dirty),
                commit,
                dirty,
            )

    # Otherwise check distance from the most recent v* tag.
    described = _run_git(repo_root, ["describe", "--tags", "--long", "--match", "v*", "HEAD"])
    if described:
        match = _DESCRIBE_RE.match(described)
        if match:
            parsed = parse_tag_version(match.group("tag"))
            dist = int(match.group("dist"))
            if parsed:
                return (
                    format_pep440_version(parsed, commit, distance=dist, dirty=dirty),
                    commit,
                    dirty,
                )

    return (
        format_pep440_version(fallback_base, commit, distance=0, dirty=dirty),
        commit,
        dirty,
    )


def _resolve_runtime_version() -> tuple[str, str]:
    # 1. Prefer build-time baked metadata inside installed wheels (`_build_info.py`).
    try:
        from pokeymans import _build_info  # type: ignore[attr-defined]

        ver = getattr(_build_info, "VERSION", "")
        commit = getattr(_build_info, "GIT_COMMIT", "unknown")
        if ver:
            return str(ver), str(commit)
    except ImportError:
        pass

    # 2. Fallback to live git tag/commit detection when running from source / editable install.
    repo_root = _find_git_root(Path(__file__).resolve().parent)
    if repo_root is not None:
        full_ver, commit, _dirty = resolve_git_version(repo_root, fallback_base=BASE_VERSION)
        if commit:
            return full_ver, commit

    # 3. Last fallback: installed package metadata or plain BASE_VERSION.
    try:
        from importlib.metadata import version as dist_version

        return dist_version("pokeymans"), "unknown"
    except Exception:
        return BASE_VERSION, "unknown"


__version__, __commit__ = _resolve_runtime_version()
