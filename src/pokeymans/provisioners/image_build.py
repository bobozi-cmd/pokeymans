"""Scheme A (Reserved): Build-time layered Docker image provisioning."""

from __future__ import annotations

from pokeymans.models.config import PokeyConfig
from pokeymans.models.runtime import ProvisionResult
from pokeymans.provisioners.base import BaseProvisioner


class ImageBuildProvisioner(BaseProvisioner):
    """Scheme A provisioner (reserved for future switch from Scheme B).

    Design outline:
        - Computes a deterministic fingerprint over `(base_image, apt, pip, requirements)`.
        - Renders a layered `Dockerfile` (apt layer -> pip layer -> entrypoint wrapper)
          and builds `<pod-name>:run-<hash>` via BuildKit cache mounts.
        - Env and `debug` toggles remain runtime-injected so config tweaks do not
          invalidate Docker image layers.
    """

    def compute_layer_hash(self, config: PokeyConfig, base_image: str) -> str:
        """Compute deterministic content hash for build-time dependency layers.

        TODO: Hash base_image, sorted apt list, pip list, and requirements_file contents.
        """
        raise NotImplementedError("TODO: implement ImageBuildProvisioner.compute_layer_hash")

    def prepare(
        self,
        config: PokeyConfig,
        base_image: str,
        *,
        debug: bool = False,
        force_refresh: bool = False,
    ) -> ProvisionResult:
        """Build (or reuse cached) derived Docker image and return `ProvisionResult`.

        TODO: Implement Scheme A when migrating Run Mode from runtime bootstrap to image build.
        """
        raise NotImplementedError(
            "TODO: Scheme A (build) provisioner is reserved and not yet implemented; "
            "use strategy='runtime' (Scheme B) for now."
        )
