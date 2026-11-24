"""Controller for Dev Mode (VS Code Dev Container workflow)."""

from __future__ import annotations

from pathlib import Path

from pokeymans.base_images.registry import BaseImageRegistry
from pokeymans.models.config import PokeyConfig
from pokeymans.models.runtime import ContainerRunSpec, PodStatus
from pokeymans.runtime.docker import DockerBackend


class DevModeController:
    """Manages Dev Mode containers and VS Code Dev Container integration.

    Dev Mode uses the base image directly without service entrypoints or apt/pip locks,
    giving developers full freedom inside the container while still mounting `/var/log/${pod-name}`.
    """

    def __init__(
        self,
        docker: DockerBackend | None = None,
        registry: BaseImageRegistry | None = None,
    ) -> None:
        self.docker = docker or DockerBackend()
        self.registry = registry or BaseImageRegistry(docker=self.docker)

    def build_run_spec(self, config: PokeyConfig) -> ContainerRunSpec:
        """Build `ContainerRunSpec` for an interactive Dev Mode container.

        TODO:
            1. Resolve & pull base image from `base-images` branch via `self.registry.pull(config.base)`.
            2. Mount workspace (`config.dev.workspace_host` -> `config.dev.workspace_container`).
            3. Attach default log mount (`config.effective_log_mount()` -> `/var/log/${pod-name}`).
            4. If `config.dev.persist_home`, attach a named volume (`pokey-<name>-dev-home`).
            5. Set command to `["sleep", "infinity"]` with no service entrypoint.
        """
        raise NotImplementedError("TODO: implement DevModeController.build_run_spec")

    def up(self, config: PokeyConfig, *, recreate: bool = False) -> PodStatus:
        """Start the Dev Mode container for VS Code Attach / remote development.

        TODO: Ensure persistent volumes and host log dir exist, start container, return `PodStatus`.
        """
        raise NotImplementedError("TODO: implement DevModeController.up")

    def init_devcontainer(
        self,
        config: PokeyConfig,
        *,
        project_dir: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Generate `.devcontainer/devcontainer.json` for VS Code Dev Containers.

        TODO:
            1. Resolve base image ref from `base-images` branch.
            2. Render `templates/devcontainer.json.tmpl` with `image`, `workspaceFolder`,
               `mounts` (including `/var/log/${pod-name}` and persistent home volume),
               `forwardPorts`, `remoteUser`, and `vscode_extensions`.
            3. Write `.devcontainer/devcontainer.json` and return its Path.
        """
        raise NotImplementedError("TODO: implement DevModeController.init_devcontainer")

    def open_vscode(self, config: PokeyConfig, *, project_dir: Path | None = None) -> None:
        """Ensure dev container / devcontainer.json is ready and open VS Code.

        TODO:
            1. Ensure `.devcontainer/devcontainer.json` exists (or start dev container).
            2. Launch VS Code via `code --folder-uri vscode-remote://dev-container+...`
               or print exact attach instructions if running on a headless remote host.
        """
        raise NotImplementedError("TODO: implement DevModeController.open_vscode")

    def snapshot(
        self,
        config: PokeyConfig,
        target_image: str,
        *,
        message: str | None = None,
    ) -> str:
        """Commit the customized Dev Mode container into a reusable Docker image.

        TODO: Call `self.docker.commit(config.container_name(PodMode.DEV), target_image, message=message)`.
        """
        raise NotImplementedError("TODO: implement DevModeController.snapshot")

    def export_packages(self, config: PokeyConfig) -> dict[str, list[str]]:
        """Inspect user-installed packages inside the Dev container for Run Mode promotion.

        TODO:
            1. Diff `pip freeze` (and optionally apt manual packages) against the base image.
            2. Return `{"apt": [...], "pip": [...]}` snippet ready to paste into `pokey.yaml`.
        """
        raise NotImplementedError("TODO: implement DevModeController.export_packages")
