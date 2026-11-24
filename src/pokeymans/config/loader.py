"""Loader and writer for `pokey.yaml`."""

from __future__ import annotations

from pathlib import Path

from pokeymans.models.config import (
    DEFAULT_CONFIG_FILENAME,
    PodMode,
    PokeyConfig,
)


def load_config(path: str | Path = DEFAULT_CONFIG_FILENAME) -> PokeyConfig:
    """Load, parse, and validate a `pokey.yaml` file into a `PokeyConfig` object.

    TODO:
        1. Read YAML via `yaml.safe_load`.
        2. Map nested sections (`base`, `logging`, `resources`, `run`, `dev`) into dataclasses.
        3. Parse enum fields (`mode`, `run.strategy`) and resolve relative paths against
           the directory containing `pokey.yaml`.
        4. Call `config.validate()` and raise `ConfigError` on invalid input.
    """
    raise NotImplementedError(f"TODO: implement load_config for {path}")


def dump_config(config: PokeyConfig, path: str | Path) -> Path:
    """Serialize a `PokeyConfig` dataclass to a YAML file.

    TODO:
        1. Convert `PokeyConfig` (and nested dataclasses/enums) to a clean dict.
        2. Write formatted YAML using `yaml.safe_dump(sort_keys=False)`.
    """
    raise NotImplementedError(f"TODO: implement dump_config for {path}")


def generate_config_template(
    output_path: str | Path = DEFAULT_CONFIG_FILENAME,
    *,
    name: str = "my-pod",
    base_name: str = "ubuntu24-py312",
    mode: PodMode = PodMode.RUN,
    force: bool = False,
) -> Path:
    """Generate a starter `pokey.yaml` from the bundled package template.

    TODO:
        1. Load `pokeymans/templates/pokey.yaml.tmpl` via `importlib.resources`.
        2. Substitute `name`, `base_name`, and `mode`.
        3. Guard against overwriting existing file unless `force=True`.
        4. Write out the rendered `pokey.yaml` and return its Path.
    """
    raise NotImplementedError(f"TODO: implement generate_config_template -> {output_path}")
