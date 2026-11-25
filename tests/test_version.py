"""Tests for git commit-tagged version formatting and resolution."""

import re
import unittest

import pokeymans
from pokeymans._version import BASE_VERSION, format_pep440_version


class TestVersionWithCommit(unittest.TestCase):
    def test_format_pep440_version(self) -> None:
        self.assertEqual(format_pep440_version("0.1.0", None), "0.1.0")
        self.assertEqual(format_pep440_version("0.1.0", "b1703b9", dirty=False), "0.1.0+gb1703b9")
        self.assertEqual(
            format_pep440_version("0.1.0", "b1703b9", dirty=True),
            "0.1.0+gb1703b9.dirty",
        )

    def test_runtime_version_includes_git_commit(self) -> None:
        self.assertTrue(pokeymans.__version__.startswith(BASE_VERSION))
        self.assertRegex(pokeymans.__commit__, r"^[0-9a-f]{7,}$")
        self.assertRegex(
            pokeymans.__version__,
            rf"^{re.escape(BASE_VERSION)}\+g{re.escape(pokeymans.__commit__)}(\.dirty)?$",
        )


if __name__ == "__main__":
    unittest.main()
