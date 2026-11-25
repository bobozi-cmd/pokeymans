"""Framework smoke tests verifying models, defaults, CLI wiring, and API contracts."""

import unittest

from pokeymans import (
    BaseImageRef,
    LogMountConfig,
    PodMode,
    PokeyClient,
    PokeyConfig,
    ProvisionStrategy,
)
from pokeymans.cli.main import build_parser
from pokeymans.provisioners import (
    ImageBuildProvisioner,
    RuntimeBootstrapProvisioner,
    get_provisioner,
)


class TestModelsAndDefaults(unittest.TestCase):
    def test_default_log_mount_expands_pod_name(self) -> None:
        cfg = PokeyConfig(name="orders-api", base=BaseImageRef(name="ubuntu24-py312"))
        mount = cfg.effective_log_mount()
        self.assertIsNotNone(mount)
        assert mount is not None
        self.assertEqual(mount.source, "/var/log/orders-api")
        self.assertEqual(mount.target, "/var/log/orders-api")
        self.assertEqual(mount.to_docker_flag(), "/var/log/orders-api:/var/log/orders-api")

    def test_disabled_log_mount_returns_none(self) -> None:
        cfg = PokeyConfig(
            name="orders-api",
            base=BaseImageRef(name="ubuntu24-py312"),
            logging=LogMountConfig(enabled=False),
        )
        self.assertIsNone(cfg.effective_log_mount())

    def test_run_mode_defaults_to_scheme_b_runtime_bootstrap(self) -> None:
        cfg = PokeyConfig(name="orders-api", base=BaseImageRef(name="ubuntu24-py312"))
        self.assertEqual(cfg.run.strategy, ProvisionStrategy.RUNTIME_BOOTSTRAP)
        self.assertIsInstance(get_provisioner(cfg.run.strategy), RuntimeBootstrapProvisioner)
        self.assertIsInstance(
            get_provisioner(ProvisionStrategy.IMAGE_BUILD), ImageBuildProvisioner
        )

    def test_container_naming_isolated_by_mode(self) -> None:
        cfg = PokeyConfig(name="demo", base=BaseImageRef(name="ubuntu24-py312"))
        self.assertEqual(cfg.container_name(PodMode.RUN), "pokey-demo-run")
        self.assertEqual(cfg.container_name(PodMode.DEV), "pokey-demo-dev")

    def test_base_image_default_branch(self) -> None:
        ref = BaseImageRef(name="ubuntu24-py312")
        self.assertEqual(ref.branch, "base-images")
        self.assertEqual(ref.full_name, "ubuntu24-py312:latest")


class TestCliParsingAndApi(unittest.TestCase):
    def test_cli_parses_all_top_level_commands(self) -> None:
        parser = build_parser()
        cases = [
            ["init", "--name", "demo", "--base", "ubuntu24-py312", "--mode", "run"],
            ["up", "-c", "pokey.yaml", "--mode", "run", "--debug", "--strategy", "runtime"],
            ["update", "-c", "pokey.yaml", "--no-debug", "--reinstall-deps"],
            ["down", "--mode", "all", "--purge-volumes"],
            ["status", "--mode", "run", "--json"],
            ["logs", "--mode", "run", "-f", "--tail", "100"],
            ["exec", "--mode", "dev", "--", "bash", "-l"],
            ["dev", "init", "--force"],
            ["dev", "open"],
            ["dev", "snapshot", "my-dev:v1", "-m", "checkpoint"],
            ["dev", "export"],
            ["base", "sync", "--force"],
            ["base", "list", "--tag", "python"],
            ["base", "info", "ubuntu24-py312"],
            ["base", "pull", "ubuntu24-py312", "--rebuild"],
        ]
        for argv in cases:
            args = parser.parse_args(argv)
            self.assertTrue(callable(getattr(args, "handler", None)), f"No handler for {argv}")

    def test_client_exposes_expected_api(self) -> None:
        client = PokeyClient()
        for method in (
            "init_config",
            "load_config",
            "up",
            "update",
            "down",
            "status",
            "logs",
            "exec",
            "dev_init",
            "dev_open",
            "dev_snapshot",
            "dev_export",
            "base_sync",
            "base_list",
            "base_info",
            "base_pull",
        ):
            self.assertTrue(callable(getattr(client, method)), f"Missing API method: {method}")


if __name__ == "__main__":
    unittest.main()
