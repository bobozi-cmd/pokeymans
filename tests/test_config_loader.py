"""Unit tests for `pokey.yaml` loading, dumping, template generation, and helpers."""

import tempfile
import unittest
from pathlib import Path

from pokeymans import ConfigError, PodMode, ProvisionStrategy
from pokeymans.config import (
    dump_config,
    generate_config_template,
    load_config,
    parse_env_file,
    parse_mount_string,
)


class TestConfigLoader(unittest.TestCase):
    def test_load_example_pokey_yaml(self) -> None:
        example_path = Path(__file__).resolve().parent.parent / "examples" / "pokey.yaml"
        cfg = load_config(example_path)
        self.assertEqual(cfg.name, "demo-service")
        self.assertEqual(cfg.mode, PodMode.RUN)
        self.assertEqual(cfg.base.name, "ubuntu24-py312")
        self.assertEqual(cfg.base.branch, "base-images")
        self.assertEqual(cfg.run.strategy, ProvisionStrategy.RUNTIME_BOOTSTRAP)
        self.assertEqual(cfg.run.apt, ["curl", "vim"])
        self.assertEqual(cfg.run.env["APP_ENV"], "production")
        log_mount = cfg.effective_log_mount()
        assert log_mount is not None
        self.assertEqual(log_mount.source, str(Path.home() / ".local/state/pokeymans/logs/demo-service"))
        self.assertEqual(log_mount.target, "/var/log/demo-service")

    def test_generate_template_preserves_pod_name_placeholder_and_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pokey.yaml"
            generate_config_template(out, name="billing", base_name="ubuntu24-py312", mode=PodMode.DEV)
            text = out.read_text(encoding="utf-8")
            self.assertIn("/var/log/${pod-name}", text)

            # Should refuse overwrite without force
            with self.assertRaises(ConfigError):
                generate_config_template(out, name="billing")

            # Round-trip load & dump
            cfg = load_config(out)
            self.assertEqual(cfg.name, "billing")
            self.assertEqual(cfg.mode, PodMode.DEV)
            log_mount = cfg.effective_log_mount()
            assert log_mount is not None
            self.assertEqual(log_mount.source, str(Path.home() / ".local/state/pokeymans/logs/billing"))

            dumped = Path(tmp) / "dumped.yaml"
            dump_config(cfg, dumped)
            cfg2 = load_config(dumped)
            self.assertEqual(cfg2.name, cfg.name)
            self.assertEqual(cfg2.mode, cfg.mode)
            self.assertEqual(cfg2.base.full_name, cfg.base.full_name)

    def test_invalid_configs_raise_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("name: 'bad name!'\nbase: ubuntu24-py312\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(bad)

            bad2 = Path(tmp) / "bad2.yaml"
            bad2.write_text("name: ok\nbase: ubuntu24-py312\nmode: invalid\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(bad2)

    def test_parse_env_file_and_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            env_path = base_dir / ".env"
            env_path.write_text(
                '# comment\nexport FOO="bar baz"\nPLAIN=123\nSINGLE=\'hello\'\n',
                encoding="utf-8",
            )
            parsed = parse_env_file(env_path)
            self.assertEqual(parsed, {"FOO": "bar baz", "PLAIN": "123", "SINGLE": "hello"})

            rel_mount = parse_mount_string("./src:/app/src:ro", base_dir=base_dir)
            self.assertEqual(rel_mount.mount_type, "bind")
            self.assertEqual(rel_mount.source, str((base_dir / "src").resolve()))
            self.assertTrue(rel_mount.read_only)

            vol_mount = parse_mount_string("my_cache:/cache", base_dir=base_dir)
            self.assertEqual(vol_mount.mount_type, "volume")
            self.assertEqual(vol_mount.source, "my_cache")


if __name__ == "__main__":
    unittest.main()
