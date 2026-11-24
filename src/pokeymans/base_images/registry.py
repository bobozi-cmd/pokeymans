"""Registry client that retrieves base images from the `base-images` git branch."""

from __future__ import annotations

from pathlib import Path

from pokeymans.models.base_image import BaseImageCatalog, BaseImageSpec
from pokeymans.models.config import (
    DEFAULT_BASE_IMAGES_BRANCH,
    DEFAULT_BASE_IMAGES_REPO,
    BaseImageRef,
)
from pokeymans.runtime.docker import DockerBackend

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pokeymans" / "base-images"


class BaseImageRegistry:
    """Discovers, caches, and pulls/builds base images from the `base-images` branch."""

    def __init__(
        self,
        repo_url: str = DEFAULT_BASE_IMAGES_REPO,
        branch: str = DEFAULT_BASE_IMAGES_BRANCH,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        docker: DockerBackend | None = None,
    ) -> None:
        self.repo_url = repo_url
        self.branch = branch
        self.cache_dir = cache_dir
        self.docker = docker or DockerBackend()

    def sync(self, force: bool = False) -> Path:
        """Clone or fetch the `base-images` branch into `self.cache_dir`.

        TODO:
            1. If `self.cache_dir` does not exist, run `git clone --branch <branch> --single-branch --depth 1`.
            2. Otherwise run `git fetch origin <branch> && git reset --hard origin/<branch>`.
            3. Support offline fallback when `force=False` and cache is already populated.
            4. Raise `BaseImageSyncError` on git failures.
        """
        raise NotImplementedError("TODO: implement BaseImageRegistry.sync")

    def load_catalog(self, auto_sync: bool = True) -> BaseImageCatalog:
        """Parse `catalog.yaml` from the synced `base-images` branch cache.

        TODO:
            1. Call `self.sync()` if cache is missing and `auto_sync=True`.
            2. Parse `<cache_dir>/catalog.yaml` into `BaseImageCatalog` and `BaseImageSpec` list.
        """
        raise NotImplementedError("TODO: implement BaseImageRegistry.load_catalog")

    def list_images(self, tag_filter: str | None = None) -> list[BaseImageSpec]:
        """Return all base images registered in `base-images/catalog.yaml`.

        TODO:
            1. Load catalog via `self.load_catalog()`.
            2. Filter by `tag_filter` if provided.
        """
        raise NotImplementedError("TODO: implement BaseImageRegistry.list_images")

    def get_image(self, name: str, tag: str | None = None) -> BaseImageSpec:
        """Look up a single base image spec from `base-images` catalog.

        TODO:
            1. Support `<name>` or `<name>:<tag>` shorthand.
            2. Raise `BaseImageNotFoundError` if not present in `catalog.yaml`.
        """
        raise NotImplementedError(f"TODO: implement BaseImageRegistry.get_image({name!r}, {tag!r})")

    def pull(
        self,
        ref: str | BaseImageRef,
        *,
        rebuild: bool = False,
        sync_first: bool = True,
    ) -> str:
        """Ensure the requested base image is available locally in Docker and return its image ref.

        TODO:
            1. If `ref` is a `BaseImageRef` with `raw_image` set, pull `raw_image` directly.
            2. Otherwise look up `BaseImageSpec` from the `base-images` branch catalog.
            3. If `spec.registry_ref` is non-empty and `not rebuild`, `docker pull spec.registry_ref`.
            4. Otherwise build locally from `<cache_dir>/<spec.dockerfile>` and tag as `spec.local_image_ref`.
            5. Return the final usable Docker image reference.
        """
        raise NotImplementedError(f"TODO: implement BaseImageRegistry.pull({ref!r})")
