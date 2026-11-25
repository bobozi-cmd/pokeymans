"""Tests for PerfConfig, container profiling flags (Run + Dev), and `pokey doctor`."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pokeymans import (
    BaseImageRef,
    ConfigError,
    DevConfig,
    LogMountConfig,
    PerfConfig,
    PodMode,
    PokeyConfig,
    ResourceConfig,
    RunConfig,
)
from pokeymans.cli.main import build_parser
from pokeymans.config import dump_config, load_config
from pokeymans.doctor import run_doctor
from pokeymans.modes import DevModeController, RunModeController
from pokeymans.runtime import DockerBackend


class TestPerfConfigAndInjection(unittest.TestCase):
    def test_perf_defaults_and_gpu_auto_mode(self) -> None:
        perf = PerfConfig()
        self.assertTrue(perf.enabled)
        self.assertEqual(perf.resolve_capabilities(has_gpus=False), ["SYS_PTRACE", "PERFMON"])
        self.assertEqual(
            perf.resolve_capabilities(has_gpus=True),
            ["SYS_PTRACE", "PERFMON", "SYS_ADMIN"],
        )
        self.assertEqual(perf.resolve_security_opts(), ["seccomp=unconfined"])

        env_gpu = perf.resolve_env(has_gpus=True, log_container_dir="/var/log/demo")
        self.assertEqual(env_gpu["NVIDIA_DRIVER_CAPABILITIES"], "all")
        self.assertEqual(env_gpu["POKEY_PROFILE_DIR"], "/var/log/demo/profiles")

        disabled = PerfConfig(enabled=False)
        self.assertEqual(disabled.resolve_capabilities(has_gpus=True), [])
        self.assertEqual(disabled.resolve_security_opts(), [])
        env_disabled_gpu = disabled.resolve_env(has_gpus=True, log_container_dir="/var/log/demo")
        self.assertEqual(env_disabled_gpu["NVIDIA_DRIVER_CAPABILITIES"], "compute,utility")
        self.assertNotIn("POKEY_PROFILE_DIR", env_disabled_gpu)

    def test_perf_config_yaml_roundtrip_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pokey.yaml"
            cfg = PokeyConfig(
                name="gpu-train",
                base=BaseImageRef(name="ubuntu24-cuda12-py312"),
                resources=ResourceConfig(gpus="all", shm_size="8g"),
                perf=PerfConfig(enabled=True, gpu_profiling="true", pid_host=True, profile_subdir="prof"),
            )
            dump_config(cfg, p)
            loaded = load_config(p)
            self.assertTrue(loaded.perf.enabled)
            self.assertEqual(loaded.perf.gpu_profiling, "true")
            self.assertTrue(loaded.perf.pid_host)
            self.assertEqual(loaded.perf.profile_subdir, "prof")

            bad = Path(tmp) / "bad.yaml"
            bad.write_text("name: x\nbase: ubuntu24-py312\nperf:\n  gpu_profiling: maybe\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(bad)

    def test_run_mode_and_docker_args_include_perf_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = PokeyConfig(
                name="infer-gpu",
                base=BaseImageRef(name="ubuntu24-cuda12-py312"),
                logging=LogMountConfig(
                    enabled=True,
                    host_dir=str(root / "logs" / "${pod-name}"),
                    container_dir="/var/log/${pod-name}",
                ),
                resources=ResourceConfig(gpus="all"),
                perf=PerfConfig(enabled=True, gpu_profiling="auto", pid_host=True),
                run=RunConfig(entrypoint="python3 serve.py"),
                config_dir=root,
            )
            mock_docker = MagicMock()
            mock_registry = MagicMock()
            mock_registry.pull.return_value = "pokeymans-base/ubuntu24-cuda12-py312:latest"

            run_ctrl = RunModeController(docker=mock_docker, registry=mock_registry)
            spec = run_ctrl.build_run_spec(cfg)

            self.assertEqual(spec.cap_add, ["SYS_PTRACE", "PERFMON", "SYS_ADMIN"])
            self.assertEqual(spec.security_opt, ["seccomp=unconfined"])
            self.assertEqual(spec.pid_mode, "host")
            self.assertEqual(spec.env["NVIDIA_DRIVER_CAPABILITIES"], "all")
            self.assertEqual(spec.env["POKEY_PROFILE_DIR"], "/var/log/infer-gpu/profiles")

            args = DockerBackend().build_run_args(spec)
            self.assertIn("--cap-add", args)
            self.assertIn("SYS_ADMIN", args)
            self.assertIn("PERFMON", args)
            self.assertIn("SYS_PTRACE", args)
            self.assertIn("--security-opt", args)
            self.assertIn("seccomp=unconfined", args)
            self.assertIn("--pid", args)
            self.assertIn("host", args)

    def test_dev_mode_devcontainer_injects_perf_run_args_and_profiles_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = PokeyConfig(
                name="cuda-dev",
                mode=PodMode.DEV,
                base=BaseImageRef(name="ubuntu24-cuda12-py312"),
                logging=LogMountConfig(
                    enabled=True,
                    host_dir=str(root / "logs" / "${pod-name}"),
                    container_dir="/var/log/${pod-name}",
                ),
                resources=ResourceConfig(gpus="0"),
                perf=PerfConfig(enabled=True, gpu_profiling="auto"),
                dev=DevConfig(workspace_host=".", workspace_container="/workspace"),
                config_dir=root,
            )
            mock_docker = MagicMock()
            mock_registry = MagicMock()
            mock_registry.pull.return_value = "pokeymans-base/ubuntu24-cuda12-py312:latest"

            dev = DevModeController(docker=mock_docker, registry=mock_registry)
            dc_path = dev.init_devcontainer(cfg, project_dir=root)
            dc = json.loads(dc_path.read_text(encoding="utf-8"))

            self.assertIn("SYS_PTRACE", dc["runArgs"])
            self.assertIn("PERFMON", dc["runArgs"])
            self.assertIn("SYS_ADMIN", dc["runArgs"])
            self.assertIn("seccomp=unconfined", dc["runArgs"])
            self.assertEqual(dc["containerEnv"]["NVIDIA_DRIVER_CAPABILITIES"], "all")
            self.assertEqual(dc["containerEnv"]["POKEY_PROFILE_DIR"], "/var/log/cuda-dev/profiles")
            self.assertTrue((root / "logs" / "cuda-dev" / "profiles").is_dir())


class TestHostDoctor(unittest.TestCase):
    def test_run_doctor_parses_sysctl_and_nvidia_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / "sys/kernel").mkdir(parents=True)
            (proc / "sys/kernel/perf_event_paranoid").write_text("2\n", encoding="utf-8")
            (proc / "sys/kernel/kptr_restrict").write_text("0\n", encoding="utf-8")
            (proc / "driver/nvidia").mkdir(parents=True)
            (proc / "driver/nvidia/params").write_text(
                "Mobile: 4294967295\nRmProfilingAdminOnly: 1\n",
                encoding="utf-8",
            )

            mock_docker = MagicMock()
            mock_docker.check_available.return_value = True
            mock_docker.info_json.return_value = {"ServerVersion": "29.9.1", "Runtimes": {"nvidia": {}}}

            results = {r.name: r for r in run_doctor(docker=mock_docker, proc_root=proc)}
            self.assertEqual(results["docker-daemon"].status, "ok")
            self.assertEqual(results["kernel.perf_event_paranoid"].status, "warn")
            self.assertIn("sysctl", results["kernel.perf_event_paranoid"].remediation)
            self.assertEqual(results["kernel.kptr_restrict"].status, "ok")
            self.assertEqual(results["nvidia-ncu-counters"].status, "warn")
            self.assertIn("NVreg_RestrictProfilingToAdminUsers=0", results["nvidia-ncu-counters"].remediation)

            # Flip RmProfilingAdminOnly to 0 -> ok
            (proc / "driver/nvidia/params").write_text("RmProfilingAdminOnly: 0\n", encoding="utf-8")
            results_ok = {r.name: r for r in run_doctor(docker=mock_docker, proc_root=proc)}
            self.assertEqual(results_ok["nvidia-ncu-counters"].status, "ok")

    def test_cli_parses_doctor_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor", "--gpu", "--json"])
        self.assertTrue(args.gpu)
        self.assertTrue(args.as_json)
        self.assertTrue(callable(args.handler))


if __name__ == "__main__":
    unittest.main()
