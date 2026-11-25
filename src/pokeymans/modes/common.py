"""Shared helpers for Run Mode and Dev Mode controllers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pokeymans.exceptions import ProvisionError
from pokeymans.models.config import PodMode, PokeyConfig
from pokeymans.models.runtime import MountSpec, PodStatus


@dataclass
class PerfRuntimeSettings:
    """Resolved runtime flags, env vars, and mounts derived from `config.perf`."""

    cap_add: list[str] = field(default_factory=list)
    security_opt: list[str] = field(default_factory=list)
    pid_mode: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    mounts: list[MountSpec] = field(default_factory=list)


def resolve_perf_runtime(config: PokeyConfig) -> PerfRuntimeSettings:
    """Compute container capabilities, seccomp, env, and optional host perf mount."""
    has_gpus = bool(config.resources.gpus)
    log_mount = config.effective_log_mount()
    log_container_dir = log_mount.target if log_mount else None

    cap_add = config.perf.resolve_capabilities(has_gpus=has_gpus)
    security_opt = config.perf.resolve_security_opts()
    pid_mode = "host" if (config.perf.enabled and config.perf.pid_host) else None
    env = config.perf.resolve_env(has_gpus=has_gpus, log_container_dir=log_container_dir)

    mounts: list[MountSpec] = []
    if config.perf.enabled and config.perf.mount_host_perf:
        perf_bin = shutil.which("perf")
        if perf_bin:
            resolved_perf = Path(perf_bin).resolve()
            if resolved_perf.is_file():
                mounts.append(
                    MountSpec(
                        source=str(resolved_perf),
                        target="/usr/local/bin/perf",
                        read_only=True,
                    )
                )

    return PerfRuntimeSettings(
        cap_add=cap_add,
        security_opt=security_opt,
        pid_mode=pid_mode,
        env=env,
        mounts=mounts,
    )


def ensure_host_log_dir(config: PokeyConfig) -> MountSpec | None:
    """Ensure host `/var/log/${pod-name}` (and optional profiles subdir) exists."""
    mount = config.effective_log_mount()
    if mount is None:
        return None
    if mount.mount_type == "bind":
        host_path = Path(mount.source)
        try:
            host_path.mkdir(parents=True, exist_ok=True)
            if config.perf.enabled and config.perf.profile_subdir:
                (host_path / config.perf.profile_subdir.lstrip("/")).mkdir(
                    parents=True, exist_ok=True
                )
        except PermissionError as exc:
            raise ProvisionError(
                f"Permission denied creating host log directory {host_path}. "
                f"Create it once (`sudo mkdir -p {host_path} && sudo chown $USER {host_path}`) "
                f"or set `logging.host_dir` in pokey.yaml."
            ) from exc
        except OSError as exc:
            raise ProvisionError(f"Failed to create host log directory {host_path}: {exc}") from exc
    return mount


def inspect_to_pod_status(
    config: PokeyConfig,
    mode: PodMode,
    info: dict[str, Any] | None,
) -> PodStatus:
    """Convert raw `docker inspect` JSON into a normalized `PodStatus`."""
    cname = config.container_name(mode)
    log_mount = config.effective_log_mount()
    default_log_host = log_mount.source if log_mount else None
    default_log_container = log_mount.target if log_mount else None

    if not info:
        return PodStatus(
            pod_name=config.name,
            mode=mode.value,
            container_name=cname,
            exists=False,
            running=False,
            image="",
            status_text="not created",
            debug=False,
            log_dir_host=default_log_host,
            log_dir_container=default_log_container,
        )

    state = info.get("State") or {}
    cfg = info.get("Config") or {}
    labels = cfg.get("Labels") or {}

    return PodStatus(
        pod_name=config.name,
        mode=mode.value,
        container_name=cname,
        exists=True,
        running=bool(state.get("Running", False)),
        image=str(cfg.get("Image") or ""),
        status_text=str(state.get("Status") or "unknown"),
        debug=str(labels.get("pokey.debug", "false")).lower() == "true",
        log_dir_host=labels.get("pokey.log_host") or default_log_host,
        log_dir_container=labels.get("pokey.log_container") or default_log_container,
    )
