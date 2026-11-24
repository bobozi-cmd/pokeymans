"""Configuration models matching `pokey.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pokeymans.models.runtime import MountSpec

DEFAULT_CONFIG_FILENAME = "pokey.yaml"
DEFAULT_LOG_DIR_TEMPLATE = "/var/log/${pod-name}"
DEFAULT_BASE_IMAGES_REPO = "git@github.com:bobozi-cmd/pokeymans.git"
DEFAULT_BASE_IMAGES_BRANCH = "base-images"


class PodMode(str, Enum):
    """Supported pod operating modes."""

    RUN = "run"
    DEV = "dev"


class ProvisionStrategy(str, Enum):
    """Provisioning strategy for Run Mode dependencies.

    - RUNTIME_BOOTSTRAP (Scheme B, default): Mount/inject a bootstrap script into the
      base container and install apt/pip + export env + run entrypoint at container start.
    - IMAGE_BUILD (Scheme A, reserved): Render a layered Dockerfile on top of base image
      and build a derived Docker image.
    """

    RUNTIME_BOOTSTRAP = "runtime"
    IMAGE_BUILD = "build"


@dataclass
class BaseImageRef:
    """Reference to a base image stored in the `base-images` branch catalog."""

    name: str
    tag: str = "latest"
    repo_url: str = DEFAULT_BASE_IMAGES_REPO
    branch: str = DEFAULT_BASE_IMAGES_BRANCH
    raw_image: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"


@dataclass
class LogMountConfig:
    """Default persistent log directory mount (`/var/log/${pod-name}`)."""

    enabled: bool = True
    host_dir: str = DEFAULT_LOG_DIR_TEMPLATE
    container_dir: str = DEFAULT_LOG_DIR_TEMPLATE

    def resolve_mount(self, pod_name: str) -> MountSpec | None:
        """Expand `${pod-name}` and return the resolved MountSpec if enabled."""
        if not self.enabled:
            return None
        host = self.host_dir.replace("${pod-name}", pod_name)
        container = self.container_dir.replace("${pod-name}", pod_name)
        return MountSpec(source=host, target=container, read_only=False)


@dataclass
class ResourceConfig:
    """Shared container resource configuration."""

    gpus: str | None = None
    shm_size: str | None = None
    network_mode: str | None = None


@dataclass
class RunConfig:
    """Run Mode configuration (apt, pip, env, entrypoint, debug, strategy)."""

    strategy: ProvisionStrategy = ProvisionStrategy.RUNTIME_BOOTSTRAP
    apt: list[str] = field(default_factory=list)
    apt_mirror: str | None = None
    pip: list[str] = field(default_factory=list)
    requirements_file: str | None = None
    pip_index_url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    env_file: str | None = None
    workdir: str = "/app"
    entrypoint: str | None = None
    debug: bool = False
    ports: list[str] = field(default_factory=list)
    mounts: list[str] = field(default_factory=list)
    cache_dir: str | None = None


@dataclass
class DevConfig:
    """Dev Mode configuration for VS Code Dev Containers.

    Intentionally does not enforce service entrypoint or apt/pip lists so users
    have full freedom inside the container.
    """

    workspace_host: str = "."
    workspace_container: str = "/workspace"
    persist_home: bool = True
    remote_user: str | None = None
    ports: list[str] = field(default_factory=list)
    mounts: list[str] = field(default_factory=list)
    vscode_extensions: list[str] = field(default_factory=list)


@dataclass
class PokeyConfig:
    """Root configuration parsed from `pokey.yaml`."""

    name: str
    base: BaseImageRef
    version: str = "1"
    mode: PodMode = PodMode.RUN
    logging: LogMountConfig = field(default_factory=LogMountConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    run: RunConfig = field(default_factory=RunConfig)
    dev: DevConfig = field(default_factory=DevConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    def container_name(self, mode: PodMode | None = None) -> str:
        """Return deterministic container name isolated by pod name and mode."""
        active_mode = mode or self.mode
        return f"pokey-{self.name}-{active_mode.value}"

    def effective_log_mount(self) -> MountSpec | None:
        """Return the resolved default `/var/log/${pod-name}` mount specification."""
        return self.logging.resolve_mount(self.name)

    def validate(self) -> None:
        """Validate configuration invariants.

        TODO: Expand validation rules (pod name charset, port format, mount syntax,
        requirements_file/env_file existence checks, etc.).
        """
        if not self.name or not self.name.strip():
            raise ValueError("`name` must be a non-empty string.")
        if not self.base.name and not self.base.raw_image:
            raise ValueError("Either `base.name` or `base.raw_image` must be set.")
