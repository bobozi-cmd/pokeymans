"""Tests for BaseImageRegistry retrieving from a git `base-images` branch."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pokeymans import BaseImageNotFoundError, BaseImageRef
from pokeymans.base_images import BaseImageRegistry


def _init_base_images_repo(repo_dir: Path, catalog_yaml: str, dockerfiles: dict[str, str] | None = None) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "base-images"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo_dir, check=True)

    (repo_dir / "catalog.yaml").write_text(catalog_yaml, encoding="utf-8")
    for rel, body in (dockerfiles or {}).items():
        target = repo_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init base-images"], cwd=repo_dir, check=True, capture_output=True)


class TestBaseImageRegistry(unittest.TestCase):
    def test_sync_list_info_and_pull_from_local_git_base_images_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            remote = tmp_path / "remote"
            _init_base_images_repo(
                remote,
                catalog_yaml=(
                    'version: "1"\n'
                    'branch: "base-images"\n'
                    "images:\n"
                    '  - name: "ubuntu24-py312"\n'
                    '    tag: "latest"\n'
                    '    description: "Ubuntu 24.04 + Python 3.12"\n'
                    '    dockerfile: "images/ubuntu24-py312/Dockerfile"\n'
                    '    registry_ref: ""\n'
                    '    os: "ubuntu:24.04"\n'
                    '    python: "3.12"\n'
                    "    tags:\n"
                    "      - ubuntu\n"
                    "      - python\n"
                ),
                dockerfiles={"images/ubuntu24-py312/Dockerfile": "FROM ubuntu:24.04\n"},
            )

            cache_dir = tmp_path / "cache"
            mock_docker = MagicMock()
            mock_docker.image_exists.return_value = False

            registry = BaseImageRegistry(
                repo_url=str(remote),
                branch="base-images",
                cache_dir=cache_dir,
                docker=mock_docker,
            )

            # Sync clones the `base-images` branch from the test git repo
            synced = registry.sync()
            self.assertEqual(synced, cache_dir)
            self.assertTrue((cache_dir / "catalog.yaml").is_file())

            # List & tag filtering
            images = registry.list_images(auto_sync=False)
            self.assertEqual(len(images), 1)
            py_images = registry.list_images(tag_filter="python", auto_sync=False)
            self.assertEqual(py_images[0].name, "ubuntu24-py312")

            # Info lookup
            spec = registry.get_image("ubuntu24-py312:latest", auto_sync=False)
            self.assertEqual(spec.dockerfile, "images/ubuntu24-py312/Dockerfile")

            # Missing image error
            with self.assertRaises(BaseImageNotFoundError):
                registry.get_image("does-not-exist", auto_sync=False)

            # Pull builds locally because catalog entry has empty registry_ref
            resolved = registry.pull("ubuntu24-py312", sync_first=False)
            self.assertEqual(resolved, "pokeymans-base/ubuntu24-py312:latest")
            mock_docker.build.assert_called_once()

            # Raw image escape hatch bypasses catalog
            raw_ref = BaseImageRef(name="", raw_image="python:3.12-slim")
            raw_resolved = registry.pull(raw_ref, sync_first=False)
            self.assertEqual(raw_resolved, "python:3.12-slim")
            mock_docker.pull.assert_called_once_with("python:3.12-slim")

    def test_pull_uses_registry_ref_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            remote = tmp_path / "remote"
            _init_base_images_repo(
                remote,
                catalog_yaml=(
                    'version: "1"\n'
                    "images:\n"
                    "  - name: cuda12\n"
                    "    tag: latest\n"
                    "    registry_ref: ghcr.io/org/cuda12:latest\n"
                ),
            )

            mock_docker = MagicMock()
            mock_docker.image_exists.return_value = False
            registry = BaseImageRegistry(
                repo_url=str(remote),
                branch="base-images",
                cache_dir=tmp_path / "cache",
                docker=mock_docker,
            )
            resolved = registry.pull("cuda12")
            self.assertEqual(resolved, "ghcr.io/org/cuda12:latest")
            mock_docker.pull.assert_called_once_with("ghcr.io/org/cuda12:latest")
            mock_docker.build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
