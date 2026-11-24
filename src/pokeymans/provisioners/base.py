"""Abstract strategy interface for Run Mode environment provisioning."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pokeymans.models.config import PokeyConfig
from pokeymans.models.runtime import ProvisionResult
from pokeymans.runtime.docker import DockerBackend


class BaseProvisioner(ABC):
    """Strategy interface decoupling Run Mode orchestration from Scheme B vs Scheme A."""

    def __init__(self, docker: DockerBackend | None = None) -> None:
        self.docker = docker or DockerBackend()

    @abstractmethod
    def prepare(
        self,
        config: PokeyConfig,
        base_image: str,
        *,
        debug: bool = False,
        force_refresh: bool = False,
    ) -> ProvisionResult:
        """Prepare the image, mounts, env, and entrypoint needed to launch Run Mode.

        Args:
            config: Parsed `PokeyConfig` from `pokey.yaml`.
            base_image: Resolved local Docker image ref from `base-images` branch.
            debug: When True, keep all apt/pip/env configured but skip service entrypoint.
            force_refresh: Force reinstalling dependencies (Scheme B) or no-cache rebuild (Scheme A).

        Returns:
            A `ProvisionResult` consumed by `RunModeController` to build `ContainerRunSpec`.
        """
