"""Build hook linking git tag + commit ID into wheel version and `_build_info.py`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent


def _load_version_module():
    spec = importlib.util.spec_from_file_location(
        "_pokeymans_version_build",
        ROOT / "src" / "pokeymans" / "_version.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load src/pokeymans/_version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ver_mod = _load_version_module()
FULL_VERSION, GIT_COMMIT, GIT_DIRTY = _ver_mod.resolve_git_version(ROOT)


class BuildPyWithGitInfo(_build_py):
    """Write `pokeymans/_build_info.py` into build_lib without dirtying `src/`."""

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
