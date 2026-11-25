"""Docker runtime wrapper encapsulating container and image operations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pokeymans.exceptions import ContainerRuntimeError
from pokeymans.models.runtime import ContainerRunSpec


class DockerBackend:
    """Thin wrapper around the host `docker` CLI.

    Keeping all Docker invocations behind this boundary simplifies unit testing
    and makes future backends (e.g. Podman / K8s) straightforward to add.
    """

    def __init__(self, binary: str = "docker") -> None:
        self.binary = binary

    def _run(
        self,
        args: list[str],
        *,
        capture_output: bool = True,
        check: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [self.binary, *args]
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ContainerRuntimeError(
                f"Container runtime binary {self.binary!r} not found in PATH."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or str(exc)
            raise ContainerRuntimeError(
                f"Docker command failed ({' '.join(cmd)}): {detail}"
            ) from exc

    def check_available(self) -> bool:
        """Check whether the Docker daemon is reachable."""
        try:
            proc = self._run(
                ["info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                check=False,
            )
            return proc.returncode == 0
        except ContainerRuntimeError:
            return False

    def pull(self, image: str) -> None:
        """Pull an image from a remote container registry."""
        self._run(["pull", image], capture_output=False, check=True)

    def build(
        self,
        context_dir: Path,
        dockerfile: Path,
        tag: str,
        *,
        no_cache: bool = False,
        build_args: dict[str, str] | None = None,
    ) -> None:
        """Build a Docker image using BuildKit (`docker build`)."""
        args = ["build", "-f", str(dockerfile), "-t", tag]
        if no_cache:
            args.append("--no-cache")
        for key, val in (build_args or {}).items():
            args.extend(["--build-arg", f"{key}={val}"])
        args.append(str(context_dir))
        self._run(
            args,
            capture_output=False,
            check=True,
            extra_env={"DOCKER_BUILDKIT": "1"},
        )

    def image_exists(self, image: str) -> bool:
        """Check if an image exists in the local Docker daemon."""
        proc = self._run(["image", "inspect", image], capture_output=True, check=False)
        return proc.returncode == 0

    def build_run_args(self, spec: ContainerRunSpec) -> list[str]:
        """Translate `ContainerRunSpec` into `docker run` CLI arguments."""
        args: list[str] = ["run"]
        if spec.detach:
            args.append("-d")
        args.extend(["--name", spec.container_name])

        if spec.workdir:
            args.extend(["-w", spec.workdir])
        if spec.gpus:
            args.extend(["--gpus", spec.gpus])
        if spec.shm_size:
            args.extend(["--shm-size", spec.shm_size])
        if spec.network_mode:
            args.extend(["--network", spec.network_mode])

        for key, val in spec.env.items():
            args.extend(["-e", f"{key}={val}"])
        for port in spec.ports:
            args.extend(["-p", port])
        for mount in spec.mounts:
            args.extend(["-v", mount.to_docker_flag()])
        for key, val in spec.labels.items():
            args.extend(["--label", f"{key}={val}"])

        trailing_cmd: list[str] = []
        if spec.entrypoint:
            args.extend(["--entrypoint", spec.entrypoint[0]])
            if len(spec.entrypoint) > 1:
                trailing_cmd.extend(spec.entrypoint[1:])
        if spec.command:
            trailing_cmd.extend(spec.command)

        args.append(spec.image)
        args.extend(trailing_cmd)
        return args

    def run(self, spec: ContainerRunSpec) -> str:
        """Create and start a container from `ContainerRunSpec`, returning its container ID."""
        args = self.build_run_args(spec)
        proc = self._run(args, capture_output=True, check=True)
        return proc.stdout.strip()

    def run_ephemeral_capture(self, image: str, command: list[str]) -> str:
        """Run a short-lived container (`docker run --rm`) and capture stdout."""
        proc = self._run(
            ["run", "--rm", "--entrypoint", command[0], image, *command[1:]],
            capture_output=True,
            check=True,
        )
        return proc.stdout

    def stop(self, container_name: str, timeout: int = 10) -> None:
        """Stop a running container gracefully."""
        self._run(["stop", "-t", str(timeout), container_name], capture_output=True, check=True)

    def remove(self, container_name: str, force: bool = False) -> None:
        """Remove a container."""
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(container_name)
        self._run(args, capture_output=True, check=True)

    def inspect(self, container_name: str) -> dict[str, Any] | None:
        """Inspect a container and return parsed JSON metadata, or None if not found."""
        proc = self._run(["inspect", container_name], capture_output=True, check=False)
        if proc.returncode != 0:
            return None
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ContainerRuntimeError(f"Failed to decode docker inspect output: {exc}") from exc
        if isinstance(payload, list) and payload:
            return payload[0]
        return None

    def logs(self, container_name: str, *, follow: bool = False, tail: int | None = None) -> None:
        """Stream or print container logs to stdout/stderr."""
        args = ["logs"]
        if follow:
            args.append("-f")
        if tail is not None:
            args.extend(["--tail", str(tail)])
        args.append(container_name)
        try:
            self._run(args, capture_output=False, check=True)
        except KeyboardInterrupt:
            return

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
        """Execute a command inside a running container and return its exit code."""
        args = ["exec"]
        if interactive:
            args.append("-i")
        if tty and sys.stdin.isatty() and sys.stdout.isatty():
            args.append("-t")
        if workdir:
            args.extend(["-w", workdir])
        for key, val in (env or {}).items():
            args.extend(["-e", f"{key}={val}"])
        args.append(container_name)
        args.extend(command)
        proc = self._run(args, capture_output=False, check=False)
        return proc.returncode

    def exec_capture(
        self,
        container_name: str,
        command: list[str],
        *,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Execute a command inside a running container and return stdout."""
        args = ["exec"]
        if workdir:
            args.extend(["-w", workdir])
        for key, val in (env or {}).items():
            args.extend(["-e", f"{key}={val}"])
        args.append(container_name)
        args.extend(command)
        proc = self._run(args, capture_output=True, check=True)
        return proc.stdout

    def commit(self, container_name: str, target_image: str, message: str | None = None) -> None:
        """Commit a container's filesystem changes into a new Docker image (`dev snapshot`)."""
        args = ["commit"]
        if message:
            args.extend(["-m", message])
        args.extend([container_name, target_image])
        self._run(args, capture_output=True, check=True)

    def ensure_volume(self, volume_name: str) -> None:
        """Create a named Docker volume if it does not already exist."""
        self._run(["volume", "create", volume_name], capture_output=True, check=True)

    def remove_volume(self, volume_name: str, force: bool = False) -> None:
        """Remove a named Docker volume."""
        args = ["volume", "rm"]
        if force:
            args.append("-f")
        args.append(volume_name)
        self._run(args, capture_output=True, check=True)
