"""Scheme B (Default): Runtime bootstrap provisioning at container startup."""

from __future__ import annotations

from pathlib import Path

from pokeymans.models.config import PokeyConfig
from pokeymans.models.runtime import ProvisionResult
from pokeymans.provisioners.base import BaseProvisioner


class RuntimeBootstrapProvisioner(BaseProvisioner):
    """Scheme B provisioner: runs directly on `base_image` and injects startup bootstrap.

    Design outline:
        - Generates a runtime manifest JSON (apt list, pip list, requirements_file,
          mirrors, env, entrypoint, debug flag) in a host state dir.
        - Mounts `templates/bootstrap.sh` and the runtime manifest read-only into `/run/pokey/`.
        - Optionally mounts apt/pip host cache dir (`run.cache_dir`) to accelerate restarts.
        - Sets container entrypoint to `["/bin/bash", "/run/pokey/bootstrap.sh"]`.
        - When `debug=True`, sets `POKEY_DEBUG=true` so `bootstrap.sh` installs deps & exports
          env, then runs `sleep infinity` instead of executing `run.entrypoint`.
    """

    def render_runtime_manifest(
        self,
        config: PokeyConfig,
        output_dir: Path,
        *,
        debug: bool = False,
    ) -> Path:
        """Write the runtime bootstrap manifest consumed by `bootstrap.sh`.

        TODO:
            1. Serialize `config.run` (apt, pip, requirements, env, mirrors, entrypoint, debug)
               to `<output_dir>/runtime-manifest.json`.
            2. Copy/extract bundled `templates/bootstrap.sh` with executable permissions.
        """
        raise NotImplementedError("TODO: implement RuntimeBootstrapProvisioner.render_runtime_manifest")

    def prepare(
        self,
        config: PokeyConfig,
        base_image: str,
        *,
        debug: bool = False,
        force_refresh: bool = False,
    ) -> ProvisionResult:
        """Prepare Scheme B container launch inputs without building a new Docker image.

        TODO:
            1. Create pod runtime state directory (e.g. `~/.cache/pokeymans/runtime/<pod-name>/`).
            2. Render bootstrap script + runtime manifest via `render_runtime_manifest()`.
            3. Build `extra_mounts` (bootstrap.sh, manifest, optional cache_dir, requirements_file).
            4. Populate `extra_env` (`POKEY_POD_NAME`, `POKEY_DEBUG`, `POKEY_ENTRYPOINT`, `POKEY_LOG_DIR`).
            5. Return `ProvisionResult(image=base_image, strategy="runtime", ...)`.
        """
        raise NotImplementedError("TODO: implement RuntimeBootstrapProvisioner.prepare (Scheme B)")
