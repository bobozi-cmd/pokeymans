"""Shared helpers for Run Mode and Dev Mode controllers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pokeymans.exceptions import ProvisionError
from pokeymans.models.config import PodMode, PokeyConfig
from pokeymans.models.runtime import MountSpec, PodStatus


def ensure_host_log_dir(config: PokeyConfig) -> MountSpec | None:
    """Ensure the host `/var/log/${pod-name}` directory exists if log mounting is enabled."""
    mount = config.effective_log_mount()
    if mount is None:
        return None
    if mount.mount_type == "bind":
        host_path = Path(mount.source)
        try:
            host_path.mkdir(parents=True, exist_ok=True)
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
