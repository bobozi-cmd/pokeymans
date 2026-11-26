"""Tests for git tag + commit version formatting and resolution."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pokeymans
from pokeymans._version import (
    BASE_VERSION,
    format_pep440_version,
    parse_tag_version,
    resolve_git_version,
)


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


class TestVersionWithTagAndCommit(unittest.TestCase):
    def test_parse_tag_version(self) -> None:
        self.assertEqual(parse_tag_version("v0.2.0"), "0.2.0")
        self.assertEqual(parse_tag_version("0.2.0"), "0.2.0")
        self.assertEqual(parse_tag_version("v1.2.3rc1"), "1.2.3rc1")
        self.assertIsNone(parse_tag_version("v-not-a-version"))
        self.assertIsNone(parse_tag_version("release-foo"))

    def test_format_pep440_version(self) -> None:
        self.assertEqual(format_pep440_version("0.1.0", None), "0.1.0")
        self.assertEqual(format_pep440_version("0.2.0", "b1703b9", dirty=False), "0.2.0+gb1703b9")
        self.assertEqual(
            format_pep440_version("0.2.0", "b1703b9", distance=2, dirty=False),
            "0.2.0.post2+gb1703b9",
        )
        self.assertEqual(
            format_pep440_version("0.2.0", "b1703b9", dirty=True),
            "0.2.0+gb1703b9.dirty",
        )

    def test_resolve_git_version_across_tags_commits_and_dirty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git(repo, "init", "-b", "main")
            _git(repo, "config", "user.name", "tester")
            _git(repo, "config", "user.email", "tester@example.com")

            f = repo / "app.txt"
            f.write_text("v1\n", encoding="utf-8")
            _git(repo, "add", "app.txt")
            _git(repo, "commit", "-m", "initial")
            sha1 = _git(repo, "rev-parse", "--short=7", "HEAD")

            # 1. No tags yet -> falls back to BASE_VERSION + commit
            ver, commit, dirty = resolve_git_version(repo)
            self.assertEqual(ver, f"{BASE_VERSION}+g{sha1}")
            self.assertEqual(commit, sha1)
            self.assertFalse(dirty)

            # 2. Exact v0.2.0 tag on HEAD -> 0.2.0+g<sha1>
            _git(repo, "tag", "-a", "v0.2.0", "-m", "Release v0.2.0")
            ver, commit, dirty = resolve_git_version(repo)
            self.assertEqual(ver, f"0.2.0+g{sha1}")
            self.assertFalse(dirty)

            # 3. Advance 2 commits past v0.2.0 -> 0.2.0.post2+g<sha3>
            f.write_text("v2\n", encoding="utf-8")
            _git(repo, "commit", "-am", "commit 2")
            f.write_text("v3\n", encoding="utf-8")
            _git(repo, "commit", "-am", "commit 3")
            sha3 = _git(repo, "rev-parse", "--short=7", "HEAD")
            ver, commit, dirty = resolve_git_version(repo)
            self.assertEqual(ver, f"0.2.0.post2+g{sha3}")
            self.assertEqual(commit, sha3)
            self.assertFalse(dirty)

            # 4. Dirty tracked file -> appends .dirty
            f.write_text("dirty\n", encoding="utf-8")
            ver, commit, dirty = resolve_git_version(repo)
            self.assertEqual(ver, f"0.2.0.post2+g{sha3}.dirty")
            self.assertTrue(dirty)

            # 5. POKEY_VERSION env override takes precedence
            with patch.dict(os.environ, {"POKEY_VERSION": "v0.9.0"}):
                ver, commit, dirty = resolve_git_version(repo)
                self.assertEqual(ver, f"0.9.0+g{sha3}.dirty")

    def test_runtime_version_includes_git_commit(self) -> None:
        self.assertRegex(pokeymans.__commit__, r"^[0-9a-f]{7,}$")
        self.assertRegex(
            pokeymans.__version__,
            rf"^\d+\.\d+\.\d+(\.post\d+)?\+g{re.escape(pokeymans.__commit__)}(\.dirty)?$",
        )


if __name__ == "__main__":
    unittest.main()
