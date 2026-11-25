"""Configuration models matching `pokey.yaml`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pokeymans.models.runtime import MountSpec

DEFAULT_CONFIG_FILENAME = "pokey.yaml"
DEFAULT_LOG_DIR_TEMPLATE = "/var/log/${pod-name}"
DEFAULT_HOST_LOG_DIR_TEMPLATE = "~/.local/state/pokeymans/logs/${pod-name}"
DEFAULT_BASE_IMAGES_REPO = "git@github.com:bobozi-cmd/pokeymans.git"
DEFAULT_BASE_IMAGES_BRANCH = "base-images"

_POD_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_VALID_GPU_PROFILING = {"auto", "true", "false"}


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
    """Default persistent log directory mount (`~/.local/state/pokeymans/logs/${pod-name}` -> `/var/log/${pod-name}`)."""

    enabled: bool = True
    host_dir: str = DEFAULT_HOST_LOG_DIR_TEMPLATE
    container_dir: str = DEFAULT_LOG_DIR_TEMPLATE

    def resolve_mount(self, pod_name: str) -> MountSpec | None:
        """Expand `~` and `${pod-name}` and return the resolved MountSpec if enabled."""
        if not self.enabled:
            return None
        host = str(Path(self.host_dir.replace("${pod-name}", pod_name)).expanduser())
        container = self.container_dir.replace("${pod-name}", pod_name)
        return MountSpec(source=host, target=container, read_only=False)


@dataclass
class ResourceConfig:
    """Shared container resource configuration."""

    gpus: str | None = None
    shm_size: str | None = None
    network_mode: str | None = None


@dataclass
class PerfConfig:
    """Container observability & profiling configuration (CPU flamegraphs, nsys, ncu).

    Enabled by default so pods can run `py-spy`, `perf`, `strace`, `htop`, and
    (when GPU is enabled) `nvidia-smi`, `nsys`, and `ncu` out of the box.
    """

    enabled: bool = True
    gpu_profiling: str = "auto"  # "auto" | "true" | "false"
    mount_host_perf: bool = False
    pid_host: bool = False
    profile_subdir: str = "profiles"

    def gpu_profiling_enabled(self, has_gpus: bool) -> bool:
        """Determine whether GPU profiling privileges (nsys/ncu) should be enabled."""
        if not self.enabled:
            return False
        mode = self.gpu_profiling.lower()
        if mode == "true":
            return True
        if mode == "false":
            return False
        return has_gpus

    def resolve_capabilities(self, has_gpus: bool) -> list[str]:
        """Return Linux capabilities required for profiling."""
        if not self.enabled:
            return []
        caps = ["SYS_PTRACE", "PERFMON"]
        if self.gpu_profiling_enabled(has_gpus):
            caps.append("SYS_ADMIN")
        return caps

    def resolve_security_opts(self) -> list[str]:
        """Return Docker `--security-opt` entries required for profiling syscalls."""
        if not self.enabled:
            return []
        return ["seccomp=unconfined"]

    def resolve_env(self, has_gpus: bool, log_container_dir: str | None = None) -> dict[str, str]:
        """Return profiling-related environment variables."""
        env: dict[str, str] = {
            "POKEY_PERF_ENABLED": "true" if self.enabled else "false",
        }
        if has_gpus:
            if self.gpu_profiling_enabled(has_gpus):
                env["NVIDIA_DRIVER_CAPABILITIES"] = "all"
            else:
                env["NVIDIA_DRIVER_CAPABILITIES"] = "compute,utility"
        if self.enabled and log_container_dir and self.profile_subdir:
            env["POKEY_PROFILE_DIR"] = f"{log_container_dir.rstrip('/')}/{self.profile_subdir.lstrip('/')}"
        return env


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
    perf: PerfConfig = field(default_factory=PerfConfig)
    run: RunConfig = field(default_factory=RunConfig)
    dev: DevConfig = field(default_factory=DevConfig)
    extra: dict[str, Any] = field(default_factory=dict)
    config_dir: Path | None = field(default=None, repr=False, compare=False)

    def container_name(self, mode: PodMode | None = None) -> str:
        """Return deterministic container name isolated by pod name and mode."""
        active_mode = mode or self.mode
        return f"pokey-{self.name}-{active_mode.value}"

    def effective_log_mount(self) -> MountSpec | None:
        """Return the resolved default `/var/log/${pod-name}` mount specification."""
        return self.logging.resolve_mount(self.name)

    def resolve_path(self, raw_path: str) -> Path:
        """Resolve a path relative to the directory containing `pokey.yaml`."""
        p = Path(raw_path).expanduser()
        if p.is_absolute():
            return p
        base_dir = self.config_dir or Path.cwd()
        return (base_dir / p).resolve()

    def validate(self) -> None:
        """Validate configuration invariants."""
        if not self.name or not self.name.strip():
            raise ValueError("`name` must be a non-empty string.")
        if not _POD_NAME_RE.match(self.name):
            raise ValueError(
                f"Invalid pod name {self.name!r}: must start with alphanumeric and "
                "contain only [a-zA-Z0-9_.-]."
            )
        if not self.base.name and not self.base.raw_image:
            raise ValueError("Either `base.name` or `base.raw_image` must be set.")
        if self.logging.enabled:
            if not self.logging.host_dir or not self.logging.container_dir:
                raise ValueError("`logging.host_dir` and `logging.container_dir` must be non-empty.")
        if self.perf.gpu_profiling.lower() not in _VALID_GPU_PROFILING:
            raise ValueError(
                f"Invalid `perf.gpu_profiling` {self.perf.gpu_profiling!r}; "
                "expected one of: auto, true, false."
            )
        if not self.dev.workspace_container.startswith("/"):
            raise ValueError("`dev.workspace_container` must be an absolute container path.")
        if not self.run.workdir.startswith("/"):
            raise ValueError("`run.workdir` must be an absolute container path.")
