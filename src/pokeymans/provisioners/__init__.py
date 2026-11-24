"""Run Mode provisioning strategies (Scheme B runtime bootstrap & Scheme A image build)."""

from pokeymans.models.config import ProvisionStrategy
from pokeymans.provisioners.base import BaseProvisioner
from pokeymans.provisioners.image_build import ImageBuildProvisioner
from pokeymans.provisioners.runtime_bootstrap import RuntimeBootstrapProvisioner
from pokeymans.runtime.docker import DockerBackend


def get_provisioner(
    strategy: ProvisionStrategy,
    *,
    docker: DockerBackend | None = None,
) -> BaseProvisioner:
    """Factory returning the provisioner implementation for the requested strategy."""
    if strategy == ProvisionStrategy.RUNTIME_BOOTSTRAP:
        return RuntimeBootstrapProvisioner(docker=docker)
    if strategy == ProvisionStrategy.IMAGE_BUILD:
        return ImageBuildProvisioner(docker=docker)
    raise ValueError(f"Unsupported provision strategy: {strategy}")


__all__ = [
    "BaseProvisioner",
    "RuntimeBootstrapProvisioner",
    "ImageBuildProvisioner",
    "get_provisioner",
]
