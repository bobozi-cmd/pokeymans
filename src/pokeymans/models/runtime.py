"""Runtime state, container launch specification, and host diagnostics models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MountSpec:
    """Bind or named volume mount specification."""

    source: str
    target: str
    read_only: bool = False
    mount_type: str = "bind"  # "bind" | "volume"

    def to_docker_flag(self) -> str:
        """Format as a `-v` argument string (e.g. `/var/log/foo:/var/log/foo`)."""
        suffix = ":ro" if self.read_only else ""
        return f"{self.source}:{self.target}{suffix}"


@dataclass
class ContainerRunSpec:
    """Normalized Docker container launch specification."""

    container_name: str
    image: str
    workdir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    ports: list[str] = field(default_factory=list)
    mounts: list[MountSpec] = field(default_factory=list)
    entrypoint: list[str] | None = None
    command: list[str] | None = None
    labels: dict[str, str] = field(default_factory=dict)
    gpus: str | None = None
    shm_size: str | None = None
    network_mode: str | None = None
    cap_add: list[str] = field(default_factory=list)
    security_opt: list[str] = field(default_factory=list)
    pid_mode: str | None = None
    detach: bool = True


@dataclass
class ProvisionResult:
    """Output produced by a Run Mode provisioner (Scheme B or Scheme A)."""

    image: str
    strategy: str
    extra_mounts: list[MountSpec] = field(default_factory=list)
    extra_env: dict[str, str] = field(default_factory=dict)
    entrypoint: list[str] | None = None
    command: list[str] | None = None


@dataclass
class PodStatus:
    """Live runtime status summary for a pod container."""

    pod_name: str
    mode: str
    container_name: str
    exists: bool
    running: bool
    image: str = ""
    status_text: str = "not created"
    debug: bool = False
    log_dir_host: str | None = None
    log_dir_container: str | None = None


@dataclass(frozen=True)
class DoctorCheckResult:
    """Single host readiness check reported by `pokey doctor`."""

    name: str
    status: str  # "ok" | "warn" | "fail" | "skip"
    detail: str
    remediation: str = ""
