"""Controller for Run Mode (`pokey up --mode run`, `pokey update`)."""

from __future__ import annotations

from pokeymans.base_images.registry import BaseImageRegistry
from pokeymans.models.config import PokeyConfig, ProvisionStrategy
from pokeymans.models.runtime import ContainerRunSpec, PodStatus
from pokeymans.provisioners import get_provisioner
from pokeymans.runtime.docker import DockerBackend


class RunModeController:
    """Manages Run Mode pod lifecycle, updates, debug toggling, and default log mount."""

    def __init__(
        self,
        docker: DockerBackend | None = None,
        registry: BaseImageRegistry | None = None,
    ) -> None:
        self.docker = docker or DockerBackend()
        self.registry = registry or BaseImageRegistry(docker=self.docker)

    def build_run_spec(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        force_refresh: bool = False,
    ) -> ContainerRunSpec:
        """Assemble the complete `ContainerRunSpec` for Run Mode.

        TODO:
            1. Resolve & pull base image from `base-images` branch via `self.registry.pull(config.base)`.
            2. Select provisioner (`strategy or config.run.strategy`, defaults to Scheme B `runtime`).
            3. Call `provisioner.prepare(config, base_image, debug=effective_debug, force_refresh=...)`.
            4. Attach default log mount (`config.effective_log_mount()` -> `/var/log/${pod-name}`)
               and ensure host log directory exists.
            5. Merge user-configured `config.run.mounts`, `ports`, `env`/`env_file`, `resources`,
               and container labels (`pokey.name`, `pokey.mode=run`, `pokey.debug`).
        """
        _ = get_provisioner(strategy or config.run.strategy, docker=self.docker)
        raise NotImplementedError("TODO: implement RunModeController.build_run_spec")

    def up(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        recreate: bool = False,
    ) -> PodStatus:
        """Start the Run Mode pod container (creating it if needed).

        TODO:
            1. Check existing container via `self.docker.inspect(config.container_name(PodMode.RUN))`.
            2. If running and not `recreate`, return status (or inform user to use `pokey update`).
            3. Otherwise remove old container if present, build spec, start container, and return `PodStatus`.
        """
        raise NotImplementedError("TODO: implement RunModeController.up")

    def update(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        reinstall_deps: bool = False,
    ) -> PodStatus:
        """Apply updated `pokey.yaml` (apt/pip/env/entrypoint/debug) to the Run Mode service.

        TODO:
            1. For Scheme B (`runtime`): regenerate runtime manifest, stop/replace container
               (or trigger in-container reload when only env/entrypoint changed).
            2. For Scheme A (`build`): compute layer hash, rebuild only if apt/pip/base changed,
               then recreate container.
            3. Preserve `/var/log/${pod-name}` logs across updates.
        """
        raise NotImplementedError("TODO: implement RunModeController.update")
