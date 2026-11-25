"""Tests for DockerBackend, Scheme B RuntimeBootstrapProvisioner, RunMode, DevMode, and PokeyClient."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pokeymans import (
    BaseImageRef,
    DevConfig,
    LogMountConfig,
    PodMode,
    PokeyClient,
    PokeyConfig,
    ProvisionStrategy,
    RunConfig,
)
from pokeymans.models.runtime import ContainerRunSpec, MountSpec
from pokeymans.modes import DevModeController, RunModeController
from pokeymans.provisioners import RuntimeBootstrapProvisioner
from pokeymans.runtime import DockerBackend


class TestDockerBackendArgs(unittest.TestCase):
    def test_build_run_args_handles_multi_part_entrypoint_and_mounts(self) -> None:
        docker = DockerBackend()
        spec = ContainerRunSpec(
            container_name="pokey-demo-run",
            image="pokeymans-base/ubuntu24-py312:latest",
            workdir="/app",
            env={"FOO": "bar"},
            ports=["8000:8000"],
            mounts=[MountSpec("/var/log/demo", "/var/log/demo")],
            entrypoint=["/bin/bash", "/run/pokey/bootstrap.sh"],
            command=["--extra"],
            labels={"pokey.debug": "true"},
            gpus="all",
        )
        args = docker.build_run_args(spec)
        self.assertIn("--entrypoint", args)
        ep_idx = args.index("--entrypoint")
        self.assertEqual(args[ep_idx + 1], "/bin/bash")
        self.assertEqual(
            args[-3:],
            ["pokeymans-base/ubuntu24-py312:latest", "/run/pokey/bootstrap.sh", "--extra"],
        )
        self.assertIn("/var/log/demo:/var/log/demo", args)


class TestSchemeBProvisionerAndRunMode(unittest.TestCase):
    def test_runtime_bootstrap_renders_valid_manifest_and_bash_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            req = root / "requirements.txt"
            req.write_text("requests==2.32.3\n", encoding="utf-8")
            log_dir = root / "logs" / "${pod-name}"

            cfg = PokeyConfig(
                name="svc-a",
                base=BaseImageRef(name="ubuntu24-py312"),
                logging=LogMountConfig(enabled=True, host_dir=str(log_dir), container_dir="/var/log/${pod-name}"),
                run=RunConfig(
                    apt=["curl", "jq"],
                    pip=["fastapi"],
                    requirements_file="requirements.txt",
                    entrypoint="python3 -m http.server 8000",
                    cache_dir=str(root / "cache"),
                ),
                config_dir=root,
            )

            prov = RuntimeBootstrapProvisioner(state_root=root / "state")
            result = prov.prepare(cfg, "pokeymans-base/ubuntu24-py312:latest", debug=True)

            self.assertEqual(result.strategy, "runtime")
            self.assertEqual(result.extra_env["POKEY_DEBUG"], "true")
            self.assertEqual(result.extra_env["POKEY_LOG_DIR"], "/var/log/svc-a")
            self.assertEqual(result.entrypoint, ["/bin/bash", "/run/pokey/bootstrap.sh"])

            state_dir = root / "state" / "svc-a"
            manifest = json.loads((state_dir / "runtime-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["apt"], ["curl", "jq"])
            self.assertEqual(manifest["pip"], ["fastapi"])
            self.assertTrue(manifest["debug"])

            # Verify generated runtime-config.sh and bootstrap.sh pass `bash -n`
            subprocess.run(["bash", "-n", str(state_dir / "runtime-config.sh")], check=True)
            subprocess.run(["bash", "-n", str(state_dir / "bootstrap.sh")], check=True)

    def test_run_mode_up_and_update_mounts_log_dir_and_toggles_debug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            env_file.write_text("FROM_FILE=yes\nOVERRIDE_ME=old\n", encoding="utf-8")

            cfg = PokeyConfig(
                name="worker",
                base=BaseImageRef(name="ubuntu24-py312"),
                logging=LogMountConfig(
                    enabled=True,
                    host_dir=str(root / "var_log" / "${pod-name}"),
                    container_dir="/var/log/${pod-name}",
                ),
                run=RunConfig(
                    env_file=".env",
                    env={"OVERRIDE_ME": "new"},
                    entrypoint="bash /app/start.sh",
                    debug=False,
                ),
                config_dir=root,
            )

            mock_docker = MagicMock()
            mock_docker.inspect.side_effect = [
                None,  # up(): not existing yet
                None,  # _replace_and_start(): not existing
                {
                    "State": {"Running": True, "Status": "running"},
                    "Config": {
                        "Image": "pokeymans-base/ubuntu24-py312:latest",
                        "Labels": {
                            "pokey.debug": "true",
                            "pokey.log_host": str(root / "var_log" / "worker"),
                            "pokey.log_container": "/var/log/worker",
                        },
                    },
                },
            ]
            mock_registry = MagicMock()
            mock_registry.pull.return_value = "pokeymans-base/ubuntu24-py312:latest"

            controller = RunModeController(docker=mock_docker, registry=mock_registry)
            status = controller.up(cfg, debug=True)

            self.assertTrue(status.running)
            self.assertTrue(status.debug)
            self.assertTrue((root / "var_log" / "worker").is_dir())

            run_spec: ContainerRunSpec = mock_docker.run.call_args.args[0]
            self.assertEqual(run_spec.env["FROM_FILE"], "yes")
            self.assertEqual(run_spec.env["OVERRIDE_ME"], "new")
            self.assertEqual(run_spec.env["POKEY_DEBUG"], "true")
            mount_targets = [m.target for m in run_spec.mounts]
            self.assertIn("/var/log/worker", mount_targets)

            # Scheme A stays reserved
            with self.assertRaises(NotImplementedError):
                controller.build_run_spec(cfg, strategy=ProvisionStrategy.IMAGE_BUILD)


class TestDevModeAndClient(unittest.TestCase):
    def test_dev_mode_init_devcontainer_and_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = PokeyConfig(
                name="ml-lab",
                mode=PodMode.DEV,
                base=BaseImageRef(name="ubuntu24-py312"),
                logging=LogMountConfig(
                    enabled=True,
                    host_dir=str(root / "var_log" / "${pod-name}"),
                    container_dir="/var/log/${pod-name}",
                ),
                dev=DevConfig(
                    workspace_host=".",
                    workspace_container="/workspace",
                    persist_home=True,
                    ports=["8888:8888"],
                    vscode_extensions=["ms-python.python"],
                ),
                config_dir=root,
            )

            mock_docker = MagicMock()
            mock_docker.inspect.side_effect = [
                None,
                {
                    "State": {"Running": True, "Status": "running"},
                    "Config": {"Image": "pokeymans-base/ubuntu24-py312:latest", "Labels": {}},
                },
            ]
            mock_registry = MagicMock()
            mock_registry.pull.return_value = "pokeymans-base/ubuntu24-py312:latest"

            dev = DevModeController(docker=mock_docker, registry=mock_registry)
            dc_path = dev.init_devcontainer(cfg, project_dir=root)
            self.assertTrue(dc_path.is_file())
            dc_json = json.loads(dc_path.read_text(encoding="utf-8"))
            self.assertEqual(dc_json["image"], "pokeymans-base/ubuntu24-py312:latest")
            self.assertEqual(dc_json["forwardPorts"], [8888])
            self.assertTrue(dc_json["overrideCommand"])
            self.assertTrue(any("/var/log/ml-lab" in m for m in dc_json["mounts"]))
            self.assertTrue(any("pokey-ml-lab-dev-home" in m for m in dc_json["mounts"]))

            status = dev.up(cfg)
            self.assertTrue(status.running)
            spec: ContainerRunSpec = mock_docker.run.call_args.args[0]
            self.assertIsNone(spec.entrypoint)
            self.assertEqual(spec.command, ["sleep", "infinity"])

    def test_client_down_and_dev_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = PokeyConfig(
                name="demo",
                base=BaseImageRef(name="ubuntu24-py312"),
                logging=LogMountConfig(enabled=True, host_dir=str(root / "logs" / "${pod-name}")),
                config_dir=root,
            )
            mock_docker = MagicMock()
            mock_docker.inspect.return_value = {
                "State": {"Running": True, "Status": "running"},
                "Config": {"Image": "pokeymans-base/ubuntu24-py312:latest", "Labels": {}},
            }
            mock_docker.image_exists.return_value = True
            mock_docker.exec_capture.side_effect = ["fastapi==0.115.0\npip==24.0\n", "curl\nhtop\n"]
            mock_docker.run_ephemeral_capture.side_effect = ["pip==24.0\n", "curl\n"]

            client = PokeyClient(docker=mock_docker)
            exported = client.dev_export(cfg)
            self.assertEqual(exported, {"apt": ["htop"], "pip": ["fastapi==0.115.0"]})

            removed = client.down(cfg, all_modes=True, purge_volumes=True)
            self.assertEqual(removed, ["pokey-demo-run", "pokey-demo-dev"])
            mock_docker.remove_volume.assert_called_once_with("pokey-demo-dev-home", force=True)


if __name__ == "__main__":
    unittest.main()
