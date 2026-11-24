"""Docker runtime wrapper encapsulating container and image operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pokeymans.models.runtime import ContainerRunSpec


class DockerBackend:
    """Thin wrapper around the host `docker` CLI (or Docker SDK).

    Keeping all Docker invocations behind this boundary simplifies unit testing
    and makes future backends (e.g. Podman / K8s) straightforward to add.
    """

    def __init__(self, binary: str = "docker") -> None:
        self.binary = binary

    def check_available(self) -> bool:
        """Check whether the Docker daemon is reachable.

        TODO: Run `docker info` and return True/False.
        """
        raise NotImplementedError("TODO: implement DockerBackend.check_available")

    def pull(self, image: str) -> None:
        """Pull an image from a remote container registry.

        TODO: Run `docker pull <image>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.pull({image!r})")

    def build(
        self,
        context_dir: Path,
        dockerfile: Path,
        tag: str,
        *,
        no_cache: bool = False,
        build_args: dict[str, str] | None = None,
    ) -> None:
        """Build a Docker image using BuildKit (`docker build`).

        TODO: Run `DOCKER_BUILDKIT=1 docker build -f <dockerfile> -t <tag> <context_dir>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.build({tag!r})")

    def image_exists(self, image: str) -> bool:
        """Check if an image exists in the local Docker daemon.

        TODO: Run `docker image inspect <image>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.image_exists({image!r})")

    def run(self, spec: ContainerRunSpec) -> str:
        """Create and start a container from `ContainerRunSpec`, returning its container ID.

        TODO: Translate `ContainerRunSpec` fields (mounts, env, ports, gpus, shm_size,
        labels, entrypoint, command) into `docker run` arguments.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.run({spec.container_name!r})")

    def stop(self, container_name: str, timeout: int = 10) -> None:
        """Stop a running container gracefully.

        TODO: Run `docker stop -t <timeout> <container_name>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.stop({container_name!r})")

    def remove(self, container_name: str, force: bool = False) -> None:
        """Remove a container.

        TODO: Run `docker rm [-f] <container_name>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.remove({container_name!r})")

    def inspect(self, container_name: str) -> dict[str, Any] | None:
        """Inspect a container and return parsed JSON metadata, or None if not found.

        TODO: Run `docker inspect <container_name>` and parse JSON output.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.inspect({container_name!r})")

    def logs(self, container_name: str, *, follow: bool = False, tail: int | None = None) -> None:
        """Stream or print container logs to stdout/stderr.

        TODO: Run `docker logs [-f] [--tail N] <container_name>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.logs({container_name!r})")

    def exec(
        self,
        container_name: str,
        command: list[str],
        *,
        interactive: bool = True,
        tty: bool = True,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        """Execute a command inside a running container and return its exit code.

        TODO: Run `docker exec [-it] [-w ...] [-e ...] <container_name> <command...>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.exec({container_name!r})")

    def commit(self, container_name: str, target_image: str, message: str | None = None) -> None:
        """Commit a container's filesystem changes into a new Docker image (`dev snapshot`).

        TODO: Run `docker commit [-m ...] <container_name> <target_image>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.commit({container_name!r})")

    def ensure_volume(self, volume_name: str) -> None:
        """Create a named Docker volume if it does not already exist.

        TODO: Run `docker volume create <volume_name>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.ensure_volume({volume_name!r})")

    def remove_volume(self, volume_name: str, force: bool = False) -> None:
        """Remove a named Docker volume.

        TODO: Run `docker volume rm [-f] <volume_name>`.
        """
        raise NotImplementedError(f"TODO: implement DockerBackend.remove_volume({volume_name!r})")
