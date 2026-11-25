"""Controller for Run Mode (`pokey up --mode run`, `pokey update`)."""

from __future__ import annotations

from pokeymans.base_images.registry import BaseImageRegistry
from pokeymans.config.loader import parse_env_file, parse_mount_string
from pokeymans.models.config import PodMode, PokeyConfig, ProvisionStrategy
from pokeymans.models.runtime import ContainerRunSpec, MountSpec, PodStatus
from pokeymans.modes.common import (
    ensure_host_log_dir,
    inspect_to_pod_status,
    resolve_perf_runtime,
)
from pokeymans.provisioners import get_provisioner
from pokeymans.runtime.docker import DockerBackend


class RunModeController:
    """Manages Run Mode pod lifecycle, updates, debug toggling, perf caps, and default log mount."""

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
        """Assemble the complete `ContainerRunSpec` for Run Mode."""
        effective_debug = config.run.debug if debug is None else debug
        effective_strategy = strategy or config.run.strategy

        base_image = self.registry.pull(config.base)
        provisioner = get_provisioner(effective_strategy, docker=self.docker)
        prov = provisioner.prepare(
            config,
            base_image,
            debug=effective_debug,
            force_refresh=force_refresh,
        )
        perf_rt = resolve_perf_runtime(config)

        merged_env: dict[str, str] = {}
        merged_env.update(perf_rt.env)
        if config.run.env_file:
            merged_env.update(parse_env_file(config.resolve_path(config.run.env_file)))
        merged_env.update(config.run.env)
        merged_env.update(prov.extra_env)

        mounts: list[MountSpec] = []
        log_mount = config.effective_log_mount()
        if log_mount is not None:
            mounts.append(log_mount)

        for raw_mount in config.run.mounts:
            mounts.append(parse_mount_string(raw_mount, base_dir=config.config_dir))
        mounts.extend(perf_rt.mounts)
        mounts.extend(prov.extra_mounts)

        labels = {
            "pokey.managed": "true",
            "pokey.name": config.name,
            "pokey.mode": PodMode.RUN.value,
            "pokey.strategy": prov.strategy,
            "pokey.debug": "true" if effective_debug else "false",
            "pokey.perf": "true" if config.perf.enabled else "false",
            "pokey.base": base_image,
        }
        if log_mount is not None:
            labels["pokey.log_host"] = log_mount.source
            labels["pokey.log_container"] = log_mount.target

        return ContainerRunSpec(
            container_name=config.container_name(PodMode.RUN),
            image=prov.image,
            workdir=config.run.workdir,
            env=merged_env,
            ports=list(config.run.ports),
            mounts=mounts,
            entrypoint=prov.entrypoint,
            command=prov.command,
            labels=labels,
            gpus=config.resources.gpus,
            shm_size=config.resources.shm_size,
            network_mode=config.resources.network_mode,
            cap_add=perf_rt.cap_add,
            security_opt=perf_rt.security_opt,
            pid_mode=perf_rt.pid_mode,
            detach=True,
        )

    def _replace_and_start(self, config: PokeyConfig, spec: ContainerRunSpec) -> PodStatus:
        cname = spec.container_name
        existing = self.docker.inspect(cname)
        if existing:
            if (existing.get("State") or {}).get("Running"):
                self.docker.stop(cname)
            self.docker.remove(cname, force=True)

        ensure_host_log_dir(config)
        self.docker.run(spec)
        info = self.docker.inspect(cname)
        return inspect_to_pod_status(config, PodMode.RUN, info)

    def up(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        recreate: bool = False,
    ) -> PodStatus:
        """Start the Run Mode pod container (creating it if needed)."""
        cname = config.container_name(PodMode.RUN)
        existing = self.docker.inspect(cname)
        if existing and (existing.get("State") or {}).get("Running") and not recreate:
            return inspect_to_pod_status(config, PodMode.RUN, existing)

        spec = self.build_run_spec(
            config,
            debug=debug,
            strategy=strategy,
            force_refresh=False,
        )
        return self._replace_and_start(config, spec)

    def update(
        self,
        config: PokeyConfig,
        *,
        debug: bool | None = None,
        strategy: ProvisionStrategy | None = None,
        reinstall_deps: bool = False,
    ) -> PodStatus:
        """Apply updated `pokey.yaml` (apt/pip/env/entrypoint/debug) to the Run Mode service."""
        spec = self.build_run_spec(
            config,
            debug=debug,
            strategy=strategy,
            force_refresh=reinstall_deps,
        )
        return self._replace_and_start(config, spec)
