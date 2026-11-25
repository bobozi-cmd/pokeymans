"""Registry client that retrieves base images from the `base-images` git branch."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

from pokeymans.exceptions import BaseImageNotFoundError, BaseImageSyncError
from pokeymans.models.base_image import BaseImageCatalog, BaseImageSpec
from pokeymans.models.config import (
    DEFAULT_BASE_IMAGES_BRANCH,
    DEFAULT_BASE_IMAGES_REPO,
    BaseImageRef,
)
from pokeymans.runtime.docker import DockerBackend

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "pokeymans" / "base-images"


def _split_name_tag(raw: str, explicit_tag: str | None = None) -> tuple[str, str | None]:
    if explicit_tag is not None:
        return raw, explicit_tag
    if ":" in raw:
        name, _, tag = raw.partition(":")
        return name.strip(), tag.strip() or None
    return raw.strip(), None


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
        self.cache_dir = Path(cache_dir)
        self.docker = docker or DockerBackend()

    def _run_git(self, args: list[str], cwd: Path | None = None) -> str:
        cmd = ["git", *args]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                check=True,
                capture_output=True,
                text=True,
            )
            return proc.stdout.strip()
        except FileNotFoundError as exc:
            raise BaseImageSyncError("`git` binary not found in PATH.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise BaseImageSyncError(
                f"Git command failed ({' '.join(cmd)}): {stderr or exc}"
            ) from exc

    def _for_ref(self, ref: BaseImageRef) -> BaseImageRegistry:
        """Return a registry scoped to `ref.repo_url` and `ref.branch`."""
        if ref.repo_url == self.repo_url and ref.branch == self.branch:
            return self
        digest = hashlib.sha256(f"{ref.repo_url}#{ref.branch}".encode("utf-8")).hexdigest()[:12]
        scoped_cache = self.cache_dir.parent / f"base-images-{digest}"
        return BaseImageRegistry(
            repo_url=ref.repo_url,
            branch=ref.branch,
            cache_dir=scoped_cache,
            docker=self.docker,
        )

    def sync(self, force: bool = False) -> Path:
        """Clone or fetch the `base-images` branch into `self.cache_dir`."""
        git_dir = self.cache_dir / ".git"
        catalog_path = self.cache_dir / "catalog.yaml"

        if not git_dir.exists():
            self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
            self._run_git(
                [
                    "clone",
                    "--branch",
                    self.branch,
                    "--single-branch",
                    "--depth",
                    "1",
                    self.repo_url,
                    str(self.cache_dir),
                ]
            )
            return self.cache_dir

        try:
            current_remote = self._run_git(["remote", "get-url", "origin"], cwd=self.cache_dir)
            if current_remote != self.repo_url:
                self._run_git(["remote", "set-url", "origin", self.repo_url], cwd=self.cache_dir)
            self._run_git(["fetch", "--depth", "1", "origin", self.branch], cwd=self.cache_dir)
            self._run_git(["checkout", "-B", self.branch, "FETCH_HEAD"], cwd=self.cache_dir)
        except BaseImageSyncError as exc:
            if not force and catalog_path.is_file():
                print(
                    f"[pokeymans] Warning: failed to sync {self.branch} ({exc}); "
                    f"using cached catalog at {self.cache_dir}",
                    file=sys.stderr,
                )
                return self.cache_dir
            raise

        return self.cache_dir

    def load_catalog(self, auto_sync: bool = True) -> BaseImageCatalog:
        """Parse `catalog.yaml` from the synced `base-images` branch cache."""
        catalog_path = self.cache_dir / "catalog.yaml"
        if not catalog_path.is_file():
            if auto_sync:
                self.sync(force=False)
            if not catalog_path.is_file():
                raise BaseImageSyncError(
                    f"catalog.yaml not found in {self.cache_dir} (branch: {self.branch})."
                )

        try:
            data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise BaseImageSyncError(f"Failed to parse {catalog_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise BaseImageSyncError(f"Malformed catalog file: {catalog_path}")

        raw_images = data.get("images") or []
        if not isinstance(raw_images, list):
            raise BaseImageSyncError(f"`images` must be a list in {catalog_path}")

        specs: list[BaseImageSpec] = []
        for entry in raw_images:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            specs.append(
                BaseImageSpec(
                    name=str(entry["name"]),
                    tag=str(entry.get("tag") or "latest"),
                    description=str(entry.get("description") or ""),
                    dockerfile=str(entry.get("dockerfile") or ""),
                    meta=str(entry.get("meta") or ""),
                    registry_ref=str(entry.get("registry_ref") or ""),
                    os=str(entry.get("os") or ""),
                    python=str(entry.get("python") or ""),
                    tags=[str(t) for t in (entry.get("tags") or [])],
                )
            )

        return BaseImageCatalog(
            version=str(data.get("version") or "1"),
            branch=str(data.get("branch") or self.branch),
            images=specs,
        )

    def list_images(
        self,
        tag_filter: str | None = None,
        *,
        auto_sync: bool = True,
    ) -> list[BaseImageSpec]:
        """Return all base images registered in `base-images/catalog.yaml`."""
        catalog = self.load_catalog(auto_sync=auto_sync)
        if not tag_filter:
            return list(catalog.images)
        needle = tag_filter.strip().lower()
        return [
            img
            for img in catalog.images
            if any(t.lower() == needle for t in img.tags)
        ]

    def get_image(
        self,
        name: str,
        tag: str | None = None,
        *,
        auto_sync: bool = True,
    ) -> BaseImageSpec:
        """Look up a single base image spec from `base-images` catalog."""
        parsed_name, parsed_tag = _split_name_tag(name, tag)
        catalog = self.load_catalog(auto_sync=auto_sync)
        spec = catalog.find(parsed_name, parsed_tag)
        if spec is None:
            available = ", ".join(img.full_name for img in catalog.images) or "<none>"
            requested = f"{parsed_name}:{parsed_tag}" if parsed_tag else parsed_name
            raise BaseImageNotFoundError(
                f"Base image {requested!r} not found in branch `{self.branch}`. "
                f"Available: {available}"
            )
        return spec

    def pull(
        self,
        ref: str | BaseImageRef,
        *,
        rebuild: bool = False,
        sync_first: bool = True,
    ) -> str:
        """Ensure the requested base image is available locally in Docker and return its image ref."""
        if isinstance(ref, BaseImageRef):
            if ref.raw_image:
                if rebuild or not self.docker.image_exists(ref.raw_image):
                    self.docker.pull(ref.raw_image)
                return ref.raw_image
            scoped = self._for_ref(ref)
            if scoped is not self:
                return scoped.pull(ref.full_name, rebuild=rebuild, sync_first=sync_first)
            lookup_name, lookup_tag = ref.name, ref.tag
        else:
            lookup_name, lookup_tag = _split_name_tag(ref)

        if sync_first:
            self.sync(force=False)

        spec = self.get_image(lookup_name, tag=lookup_tag, auto_sync=not sync_first)

        if spec.registry_ref and not rebuild:
            if not self.docker.image_exists(spec.registry_ref):
                self.docker.pull(spec.registry_ref)
            return spec.registry_ref

        if not spec.dockerfile:
            raise BaseImageNotFoundError(
                f"Base image {spec.full_name!r} has neither `registry_ref` nor `dockerfile`."
            )

        dockerfile_path = self.cache_dir / spec.dockerfile
        if not dockerfile_path.is_file():
            raise BaseImageSyncError(
                f"Dockerfile for {spec.full_name!r} not found at {dockerfile_path}"
            )

        target_tag = spec.local_image_ref
        if rebuild or not self.docker.image_exists(target_tag):
            self.docker.build(
                context_dir=dockerfile_path.parent,
                dockerfile=dockerfile_path,
                tag=target_tag,
                no_cache=rebuild,
            )
        return target_tag
