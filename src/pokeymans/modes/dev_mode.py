"""Controller for Dev Mode (VS Code Dev Container workflow)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pokeymans.base_images.registry import BaseImageRegistry
from pokeymans.config.loader import parse_mount_string
from pokeymans.exceptions import ConfigError, ContainerRuntimeError
from pokeymans.models.config import PodMode, PokeyConfig
from pokeymans.models.runtime import ContainerRunSpec, MountSpec, PodStatus
from pokeymans.modes.common import (
    ensure_host_log_dir,
    inspect_to_pod_status,
    resolve_perf_runtime,
)
from pokeymans.runtime.docker import DockerBackend


def _parse_forward_ports(ports: list[str]) -> list[int]:
    result: list[int] = []
    for raw in ports:
        parts = raw.split(":")
        candidate = parts[-1].split("/")[0].strip()
        if candidate.isdigit():
            port_num = int(candidate)
            if port_num not in result:
                result.append(port_num)
    return result


def _mount_to_devcontainer_str(mount: MountSpec) -> str:
    base = f"source={mount.source},target={mount.target},type={mount.mount_type}"
    if mount.read_only:
        return f"{base},readonly"
    return base


def _parse_pkg_lines(raw: str) -> set[str]:
    pkgs: set[str] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pkgs.add(stripped)
    return pkgs


class DevModeController:
    """Manages Dev Mode containers and VS Code Dev Container integration.

    Dev Mode uses the base image directly without service entrypoints or apt/pip locks,
    giving developers full freedom inside the container while enabling perf profiling
    and mounting `/var/log/${pod-name}`.
    """

    def __init__(
        self,
        docker: DockerBackend | None = None,
        registry: BaseImageRegistry | None = None,
    ) -> None:
        self.docker = docker or DockerBackend()
        self.registry = registry or BaseImageRegistry(docker=self.docker)

    @staticmethod
    def home_volume_name(config: PokeyConfig) -> str:
        """Deterministic named volume for persisting Dev Mode user home configs."""
        return f"pokey-{config.name}-dev-home"

    @staticmethod
    def _home_target(config: PokeyConfig) -> str:
        user = config.dev.remote_user
        if not user or user == "root":
            return "/root"
        return f"/home/{user}"

    def build_run_spec(self, config: PokeyConfig) -> ContainerRunSpec:
        """Build `ContainerRunSpec` for an interactive Dev Mode container."""
        base_image = self.registry.pull(config.base)
        perf_rt = resolve_perf_runtime(config)

        mounts: list[MountSpec] = [
            parse_mount_string(
                f"{config.dev.workspace_host}:{config.dev.workspace_container}",
                base_dir=config.config_dir,
            )
        ]

        log_mount = config.effective_log_mount()
        if log_mount is not None:
            mounts.append(log_mount)

        if config.dev.persist_home:
            mounts.append(
                MountSpec(
                    source=self.home_volume_name(config),
                    target=self._home_target(config),
                    read_only=False,
                    mount_type="volume",
                )
            )

        for raw_mount in config.dev.mounts:
            mounts.append(parse_mount_string(raw_mount, base_dir=config.config_dir))
        mounts.extend(perf_rt.mounts)

        env = {"POKEY_POD_NAME": config.name, "POKEY_MODE": PodMode.DEV.value}
        env.update(perf_rt.env)

        labels = {
            "pokey.managed": "true",
            "pokey.name": config.name,
            "pokey.mode": PodMode.DEV.value,
            "pokey.perf": "true" if config.perf.enabled else "false",
            "pokey.base": base_image,
        }
        if log_mount is not None:
            labels["pokey.log_host"] = log_mount.source
            labels["pokey.log_container"] = log_mount.target

        return ContainerRunSpec(
            container_name=config.container_name(PodMode.DEV),
            image=base_image,
            workdir=config.dev.workspace_container,
            env=env,
            ports=list(config.dev.ports),
            mounts=mounts,
            entrypoint=None,
            command=["sleep", "infinity"],
            labels=labels,
            gpus=config.resources.gpus,
            shm_size=config.resources.shm_size,
            network_mode=config.resources.network_mode,
            cap_add=perf_rt.cap_add,
            security_opt=perf_rt.security_opt,
            pid_mode=perf_rt.pid_mode,
            detach=True,
        )

    def up(self, config: PokeyConfig, *, recreate: bool = False) -> PodStatus:
        """Start the Dev Mode container for VS Code Attach / remote development."""
        cname = config.container_name(PodMode.DEV)
        existing = self.docker.inspect(cname)
        if existing and (existing.get("State") or {}).get("Running") and not recreate:
            return inspect_to_pod_status(config, PodMode.DEV, existing)

        spec = self.build_run_spec(config)
        if existing:
            if (existing.get("State") or {}).get("Running"):
                self.docker.stop(cname)
            self.docker.remove(cname, force=True)

        if config.dev.persist_home:
            self.docker.ensure_volume(self.home_volume_name(config))
        ensure_host_log_dir(config)

        self.docker.run(spec)
        info = self.docker.inspect(cname)
        return inspect_to_pod_status(config, PodMode.DEV, info)

    def init_devcontainer(
        self,
        config: PokeyConfig,
        *,
        project_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Generate `.devcontainer/devcontainer.json` for VS Code Dev Containers."""
        root_dir = (project_dir or config.config_dir or Path.cwd()).resolve()
        target = root_dir / ".devcontainer" / "devcontainer.json"
        if target.exists() and not force:
            raise ConfigError(f"{target} already exists. Pass --force to overwrite.")

        base_image = self.registry.pull(config.base)
        perf_rt = resolve_perf_runtime(config)

        if config.dev.persist_home:
            self.docker.ensure_volume(self.home_volume_name(config))
        log_mount = ensure_host_log_dir(config)

        mounts: list[str] = []
        if log_mount is not None:
            mounts.append(_mount_to_devcontainer_str(log_mount))
        if config.dev.persist_home:
            mounts.append(
                _mount_to_devcontainer_str(
                    MountSpec(
                        source=self.home_volume_name(config),
                        target=self._home_target(config),
                        mount_type="volume",
                    )
                )
            )
        for raw_mount in config.dev.mounts:
            mounts.append(
                _mount_to_devcontainer_str(
                    parse_mount_string(raw_mount, base_dir=config.config_dir)
                )
            )
        for perf_mount in perf_rt.mounts:
            mounts.append(_mount_to_devcontainer_str(perf_mount))

        run_args: list[str] = ["--name", config.container_name(PodMode.DEV)]
        if config.resources.gpus:
            run_args.extend(["--gpus", config.resources.gpus])
        if config.resources.shm_size:
            run_args.extend(["--shm-size", config.resources.shm_size])
        if config.resources.network_mode:
            run_args.extend(["--network", config.resources.network_mode])
        if perf_rt.pid_mode:
            run_args.extend(["--pid", perf_rt.pid_mode])
        for cap in perf_rt.cap_add:
            run_args.extend(["--cap-add", cap])
        for opt in perf_rt.security_opt:
            run_args.extend(["--security-opt", opt])

        container_env = {"POKEY_POD_NAME": config.name, "POKEY_MODE": PodMode.DEV.value}
        container_env.update(perf_rt.env)

        payload: dict[str, Any] = {
            "name": f"pokey-{config.name}-dev",
            "image": base_image,
            "workspaceFolder": config.dev.workspace_container,
            "workspaceMount": (
                f"source=${{localWorkspaceFolder}},target={config.dev.workspace_container},"
                "type=bind,consistency=cached"
            ),
            "overrideCommand": True,
            "runArgs": run_args,
            "containerEnv": container_env,
        }
        if mounts:
            payload["mounts"] = mounts
        forward_ports = _parse_forward_ports(config.dev.ports)
        if forward_ports:
            payload["forwardPorts"] = forward_ports
        if config.dev.remote_user:
            payload["remoteUser"] = config.dev.remote_user
            if config.dev.remote_user != "root":
                payload["updateRemoteUserUID"] = True
        if config.dev.vscode_extensions:
            payload["customizations"] = {
                "vscode": {"extensions": list(config.dev.vscode_extensions)}
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target

    def open_vscode(self, config: PokeyConfig, *, project_dir: Path | None = None) -> None:
        """Ensure dev container / devcontainer.json is ready and open VS Code."""
        root_dir = (project_dir or config.config_dir or Path.cwd()).resolve()
        devcontainer_file = root_dir / ".devcontainer" / "devcontainer.json"
        if not devcontainer_file.is_file():
            self.init_devcontainer(config, project_dir=root_dir, force=False)

        code_bin = shutil.which("code")
        if code_bin:
            hex_path = str(root_dir).encode("utf-8").hex()
            uri = f"vscode-remote://dev-container+{hex_path}{config.dev.workspace_container}"
            subprocess.run([code_bin, "--folder-uri", uri], check=False)
            return

        status = self.up(config, recreate=False)
        print(f"VS Code CLI (`code`) not found on this host; started Dev container `{status.container_name}`.")
        print(f"Connect from local VS Code via Remote-SSH -> Dev Containers: Attach to `{status.container_name}`.")
        print(f"devcontainer.json is ready at: {devcontainer_file}")

    def snapshot(
        self,
        config: PokeyConfig,
        target_image: str,
        *,
        message: str | None = None,
    ) -> str:
        """Commit the customized Dev Mode container into a reusable Docker image."""
        cname = config.container_name(PodMode.DEV)
        info = self.docker.inspect(cname)
        if not info:
            raise ContainerRuntimeError(
                f"Dev container `{cname}` does not exist. Start it first with `pokey up --mode dev`."
            )
        self.docker.commit(cname, target_image, message=message)
        return target_image

    def export_packages(self, config: PokeyConfig) -> dict[str, list[str]]:
        """Inspect user-installed packages inside the Dev container for Run Mode promotion."""
        cname = config.container_name(PodMode.DEV)
        info = self.docker.inspect(cname)
        if not info or not (info.get("State") or {}).get("Running"):
            raise ContainerRuntimeError(
                f"Dev container `{cname}` is not running. Start it with `pokey up --mode dev`."
            )

        base_image = str((info.get("Config") or {}).get("Image") or "")

        dev_pip = _parse_pkg_lines(
            self._safe_exec_capture(
                cname,
                ["bash", "-lc", "python3 -m pip freeze 2>/dev/null || pip freeze 2>/dev/null || true"],
            )
        )
        dev_apt = _parse_pkg_lines(
            self._safe_exec_capture(cname, ["bash", "-lc", "apt-mark showmanual 2>/dev/null || true"])
        )

        base_pip: set[str] = set()
        base_apt: set[str] = set()
        if base_image and self.docker.image_exists(base_image):
            try:
                base_pip = _parse_pkg_lines(
                    self.docker.run_ephemeral_capture(
                        base_image,
                        ["bash", "-lc", "python3 -m pip freeze 2>/dev/null || pip freeze 2>/dev/null || true"],
                    )
                )
            except ContainerRuntimeError:
                base_pip = set()
            try:
                base_apt = _parse_pkg_lines(
                    self.docker.run_ephemeral_capture(
                        base_image,
                        ["bash", "-lc", "apt-mark showmanual 2>/dev/null || true"],
                    )
                )
            except ContainerRuntimeError:
                base_apt = set()

        return {
            "apt": sorted(dev_apt - base_apt),
            "pip": sorted(dev_pip - base_pip),
        }

    def _safe_exec_capture(self, container_name: str, command: list[str]) -> str:
        try:
            return self.docker.exec_capture(container_name, command)
        except ContainerRuntimeError:
            return ""
