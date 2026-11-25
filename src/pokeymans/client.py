"""High-level Python API facade for pokeymans."""

from __future__ import annotations

from pathlib import Path

from pokeymans.base_images.registry import BaseImageRegistry
from pokeymans.config.loader import generate_config_template, load_config
from pokeymans.exceptions import ContainerRuntimeError
from pokeymans.models.base_image import BaseImageSpec
from pokeymans.models.config import (
    DEFAULT_CONFIG_FILENAME,
    PodMode,
    PokeyConfig,
    ProvisionStrategy,
)
from pokeymans.models.runtime import PodStatus
from pokeymans.modes.common import inspect_to_pod_status
from pokeymans.modes.dev_mode import DevModeController
from pokeymans.modes.run_mode import RunModeController
from pokeymans.runtime.docker import DockerBackend


class PokeyClient:
    """Programmatic entry point exposing all pokeymans capabilities as Python APIs."""

    def __init__(
        self,
        docker: DockerBackend | None = None,
        registry: BaseImageRegistry | None = None,
    ) -> None:
        self.docker = docker or DockerBackend()
        self.registry = registry or BaseImageRegistry(docker=self.docker)
        self.run_mode = RunModeController(docker=self.docker, registry=self.registry)
        self.dev_mode = DevModeController(docker=self.docker, registry=self.registry)

    # --- Configuration ---

    def init_config(
        self,
        output_path: str | Path = DEFAULT_CONFIG_FILENAME,
        *,
        name: str = "my-pod",
        base_name: str = "ubuntu24-py312",
        mode: PodMode = PodMode.RUN,
        force: bool = False,
    ) -> Path:
        """Create a starter `pokey.yaml` file."""
        return generate_config_template(
            output_path,
            name=name,
            base_name=base_name,
            mode=mode,
            force=force,
        )

    def load_config(self, path: str | Path = DEFAULT_CONFIG_FILENAME) -> PokeyConfig:
        """Load and validate `pokey.yaml`."""
        return load_config(path)

    # --- Pod Lifecycle ---

    def up(
        self,
        config: PokeyConfig,
        *,
        mode: PodMode | None = None,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        recreate: bool = False,
    ) -> PodStatus:
        """Start the pod in either Run Mode or Dev Mode."""
        active_mode = mode or config.mode
        if active_mode == PodMode.RUN:
            return self.run_mode.up(
                config,
                debug=debug,
                strategy=strategy,
                recreate=recreate,
            )
        return self.dev_mode.up(config, recreate=recreate)

    def update(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        reinstall_deps: bool = False,
    ) -> PodStatus:
        """Update a Run Mode service with the latest `pokey.yaml` configuration."""
        return self.run_mode.update(
            config,
            debug=debug,
            strategy=strategy,
            reinstall_deps=reinstall_deps,
        )

    def down(
        self,
        config: PokeyConfig,
        *,
        mode: PodMode | None = None,
        all_modes: bool = False,
        purge_volumes: bool = False,
    ) -> list[str]:
        """Stop and remove pod container(s), returning names of removed containers."""
        target_modes = [PodMode.RUN, PodMode.DEV] if all_modes else [mode or config.mode]
        removed: list[str] = []

        for active_mode in target_modes:
            cname = config.container_name(active_mode)
            info = self.docker.inspect(cname)
            if info:
                if (info.get("State") or {}).get("Running"):
                    self.docker.stop(cname)
                self.docker.remove(cname, force=True)
                removed.append(cname)

            if purge_volumes and active_mode == PodMode.DEV and config.dev.persist_home:
                vol = DevModeController.home_volume_name(config)
                try:
                    self.docker.remove_volume(vol, force=True)
                except ContainerRuntimeError:
                    pass

        return removed

    def status(
        self,
        config: PokeyConfig,
        *,
        mode: PodMode | None = None,
        all_modes: bool = False,
    ) -> list[PodStatus]:
        """Return live status of pod container(s), including resolved `/var/log/${pod-name}` paths."""
        target_modes = [PodMode.RUN, PodMode.DEV] if all_modes else [mode or config.mode]
        statuses: list[PodStatus] = []
        for active_mode in target_modes:
            cname = config.container_name(active_mode)
            info = self.docker.inspect(cname)
            statuses.append(inspect_to_pod_status(config, active_mode, info))
        return statuses

    def logs(
        self,
        config: PokeyConfig,
        *,
        mode: PodMode | None = None,
        follow: bool = False,
        tail: int | None = None,
    ) -> None:
        """Stream container logs for the specified pod mode."""
        active_mode = mode or config.mode
        cname = config.container_name(active_mode)
        if not self.docker.inspect(cname):
            raise ContainerRuntimeError(
                f"Container `{cname}` does not exist. Start it first with `pokey up --mode {active_mode.value}`."
            )
        self.docker.logs(cname, follow=follow, tail=tail)

    def exec(
        self,
        config: PokeyConfig,
        command: list[str] | None = None,
        *,
        mode: PodMode | None = None,
    ) -> int:
        """Execute an interactive command (defaults to `["bash"]`) inside the pod container."""
        active_mode = mode or config.mode
        cname = config.container_name(active_mode)
        info = self.docker.inspect(cname)
        if not info or not (info.get("State") or {}).get("Running"):
            raise ContainerRuntimeError(
                f"Container `{cname}` is not running. Start it with `pokey up --mode {active_mode.value}`."
            )
        return self.docker.exec(cname, command or ["bash"])

    # --- Dev Mode Helpers ---

    def dev_init(
        self,
        config: PokeyConfig,
        *,
        project_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Generate `.devcontainer/devcontainer.json` for VS Code."""
        return self.dev_mode.init_devcontainer(config, project_dir=project_dir, force=force)

    def dev_open(self, config: PokeyConfig, *, project_dir: Path | None = None) -> None:
        """Prepare Dev Mode and open VS Code Dev Container."""
        self.dev_mode.open_vscode(config, project_dir=project_dir)

    def dev_snapshot(
        self,
        config: PokeyConfig,
        target_image: str,
        *,
        message: str | None = None,
    ) -> str:
        """Snapshot the Dev Mode container into a Docker image."""
        return self.dev_mode.snapshot(config, target_image, message=message)

    def dev_export(self, config: PokeyConfig) -> dict[str, list[str]]:
        """Export user-installed packages from Dev Mode for `pokey.yaml`."""
        return self.dev_mode.export_packages(config)

    # --- Base Image Registry (`base-images` branch) ---

    def base_sync(self, *, force: bool = False) -> Path:
        """Sync the `base-images` branch catalog cache."""
        return self.registry.sync(force=force)

    def base_list(self, *, tag_filter: str | None = None) -> list[BaseImageSpec]:
        """List base images from the `base-images` branch."""
        return self.registry.list_images(tag_filter=tag_filter)

    def base_info(self, name: str, *, tag: str | None = None) -> BaseImageSpec:
        """Get details of a base image from the `base-images` branch."""
        return self.registry.get_image(name, tag=tag)

    def base_pull(
        self,
        name: str,
        *,
        rebuild: bool = False,
        sync_first: bool = True,
    ) -> str:
        """Pull (or build locally) a base image resolved from the `base-images` branch."""
        return self.registry.pull(name, rebuild=rebuild, sync_first=sync_first)
