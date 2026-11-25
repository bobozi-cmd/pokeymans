"""Tests for BaseImageRegistry retrieving from a git `base-images` branch."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pokeymans import BaseImageNotFoundError, BaseImageRef
from pokeymans.base_images import BaseImageRegistry


class TestBaseImageRegistry(unittest.TestCase):
    def test_sync_list_info_and_pull_from_local_git_base_images_branch(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            mock_docker = MagicMock()
            mock_docker.image_exists.return_value = False

            registry = BaseImageRegistry(
                repo_url=str(repo_root),
                branch="base-images",
                cache_dir=cache_dir,
                docker=mock_docker,
            )

            # Sync clones the `base-images` branch from this repo
            synced = registry.sync()
            self.assertEqual(synced, cache_dir)
            self.assertTrue((cache_dir / "catalog.yaml").is_file())

            # List & tag filtering
            images = registry.list_images(auto_sync=False)
            self.assertGreaterEqual(len(images), 1)
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
            # Create a mini git repo with a `base-images` branch that has registry_ref
            remote = Path(tmp) / "remote"
            remote.mkdir()
            subprocess.run(["git", "init", "-b", "base-images"], cwd=remote, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=remote, check=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=remote, check=True)
            (remote / "catalog.yaml").write_text(
                'version: "1"\nimages:\n  - name: cuda12\n    tag: latest\n    registry_ref: ghcr.io/org/cuda12:latest\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "catalog.yaml"], cwd=remote, check=True)
            subprocess.run(["git", "commit", "-m", "add cuda12"], cwd=remote, check=True, capture_output=True)

            mock_docker = MagicMock()
            mock_docker.image_exists.return_value = False
            registry = BaseImageRegistry(
                repo_url=str(remote),
                branch="base-images",
                cache_dir=Path(tmp) / "cache",
                docker=mock_docker,
            )
            resolved = registry.pull("cuda12")
            self.assertEqual(resolved, "ghcr.io/org/cuda12:latest")
            mock_docker.pull.assert_called_once_with("ghcr.io/org/cuda12:latest")
            mock_docker.build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
