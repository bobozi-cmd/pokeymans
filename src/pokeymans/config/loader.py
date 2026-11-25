"""Loader, serializer, and parsing helpers for `pokey.yaml`."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from pokeymans.exceptions import ConfigError
from pokeymans.models.config import (
    DEFAULT_BASE_IMAGES_BRANCH,
    DEFAULT_BASE_IMAGES_REPO,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_HOST_LOG_DIR_TEMPLATE,
    DEFAULT_LOG_DIR_TEMPLATE,
    BaseImageRef,
    DevConfig,
    LogMountConfig,
    PerfConfig,
    PodMode,
    PokeyConfig,
    ProvisionStrategy,
    ResourceConfig,
    RunConfig,
)
from pokeymans.models.runtime import MountSpec

_KNOWN_TOP_KEYS = {
    "version",
    "name",
    "mode",
    "base",
    "logging",
    "resources",
    "perf",
    "run",
    "dev",
}


def _as_str_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"`{field_name}` must be a list of strings.")
    return [str(item) for item in value]


def _as_str_dict(value: Any, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"`{field_name}` must be a mapping of key-value pairs.")
    return {str(k): "" if v is None else str(v) for k, v in value.items()}


def _parse_base(raw: Any) -> BaseImageRef:
    if isinstance(raw, str):
        name, _, tag = raw.partition(":")
        return BaseImageRef(name=name.strip(), tag=tag.strip() or "latest")
    if isinstance(raw, dict):
        name = str(raw.get("name") or "").strip()
        tag = str(raw.get("tag") or "latest").strip()
        if ":" in name and "tag" not in raw:
            name, _, tag = name.partition(":")
        return BaseImageRef(
            name=name,
            tag=tag or "latest",
            repo_url=str(raw.get("repo_url") or DEFAULT_BASE_IMAGES_REPO),
            branch=str(raw.get("branch") or DEFAULT_BASE_IMAGES_BRANCH),
            raw_image=str(raw["raw_image"]) if raw.get("raw_image") else None,
        )
    raise ConfigError("`base` must be a mapping (e.g. {name: ubuntu24-py312}) or string.")


def _parse_logging(raw: Any) -> LogMountConfig:
    if raw is None:
        return LogMountConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`logging` must be a mapping.")
    return LogMountConfig(
        enabled=bool(raw.get("enabled", True)),
        host_dir=str(raw.get("host_dir", DEFAULT_HOST_LOG_DIR_TEMPLATE)),
        container_dir=str(raw.get("container_dir", DEFAULT_LOG_DIR_TEMPLATE)),
    )


def _parse_resources(raw: Any) -> ResourceConfig:
    if raw is None:
        return ResourceConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`resources` must be a mapping.")
    raw_gpus = raw.get("gpus")
    if isinstance(raw_gpus, bool):
        gpus: str | None = "all" if raw_gpus else None
    elif raw_gpus is None or raw_gpus == "":
        gpus = None
    else:
        gpus = str(raw_gpus)
    return ResourceConfig(
        gpus=gpus,
        shm_size=str(raw["shm_size"]) if raw.get("shm_size") else None,
        network_mode=str(raw["network_mode"]) if raw.get("network_mode") else None,
    )


def _parse_perf(raw: Any) -> PerfConfig:
    if raw is None:
        return PerfConfig()
    if isinstance(raw, bool):
        return PerfConfig(enabled=raw)
    if not isinstance(raw, dict):
        raise ConfigError("`perf` must be a mapping or boolean.")
    raw_gpu_prof = raw.get("gpu_profiling", "auto")
    if isinstance(raw_gpu_prof, bool):
        gpu_profiling = "true" if raw_gpu_prof else "false"
    else:
        gpu_profiling = str(raw_gpu_prof).strip().lower()
    return PerfConfig(
        enabled=bool(raw.get("enabled", True)),
        gpu_profiling=gpu_profiling,
        mount_host_perf=bool(raw.get("mount_host_perf", False)),
        pid_host=bool(raw.get("pid_host", False)),
        profile_subdir=str(raw.get("profile_subdir", "profiles") or ""),
    )


def _parse_run(raw: Any) -> RunConfig:
    if raw is None:
        return RunConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`run` must be a mapping.")
    raw_strategy = str(raw.get("strategy", ProvisionStrategy.RUNTIME_BOOTSTRAP.value))
    try:
        strategy = ProvisionStrategy(raw_strategy)
    except ValueError as exc:
        valid = ", ".join(s.value for s in ProvisionStrategy)
        raise ConfigError(f"Invalid `run.strategy` {raw_strategy!r}; expected one of: {valid}") from exc

    raw_pip = raw.get("pip")
    requirements_file = raw.get("requirements_file")
    if isinstance(raw_pip, dict):
        if raw_pip.get("requirements") and not requirements_file:
            requirements_file = raw_pip.get("requirements")
        pip_packages = _as_str_list(raw_pip.get("packages"), "run.pip.packages")
    else:
        pip_packages = _as_str_list(raw_pip, "run.pip")

    entrypoint_val = raw.get("entrypoint")
    entrypoint = str(entrypoint_val) if entrypoint_val not in (None, "") else None

    return RunConfig(
        strategy=strategy,
        apt=_as_str_list(raw.get("apt"), "run.apt"),
        apt_mirror=str(raw["apt_mirror"]) if raw.get("apt_mirror") else None,
        pip=pip_packages,
        requirements_file=str(requirements_file) if requirements_file else None,
        pip_index_url=str(raw["pip_index_url"]) if raw.get("pip_index_url") else None,
        env=_as_str_dict(raw.get("env"), "run.env"),
        env_file=str(raw["env_file"]) if raw.get("env_file") else None,
        workdir=str(raw.get("workdir") or "/app"),
        entrypoint=entrypoint,
        debug=bool(raw.get("debug", False)),
        ports=_as_str_list(raw.get("ports"), "run.ports"),
        mounts=_as_str_list(raw.get("mounts"), "run.mounts"),
        cache_dir=str(raw["cache_dir"]) if raw.get("cache_dir") else None,
    )


def _parse_dev(raw: Any) -> DevConfig:
    if raw is None:
        return DevConfig()
    if not isinstance(raw, dict):
        raise ConfigError("`dev` must be a mapping.")
    return DevConfig(
        workspace_host=str(raw.get("workspace_host") or "."),
        workspace_container=str(raw.get("workspace_container") or "/workspace"),
        persist_home=bool(raw.get("persist_home", True)),
        remote_user=str(raw["remote_user"]) if raw.get("remote_user") else None,
        ports=_as_str_list(raw.get("ports"), "dev.ports"),
        mounts=_as_str_list(raw.get("mounts"), "dev.mounts"),
        vscode_extensions=_as_str_list(raw.get("vscode_extensions"), "dev.vscode_extensions"),
    )


def load_config(path: str | Path = DEFAULT_CONFIG_FILENAME) -> PokeyConfig:
    """Load, parse, and validate a `pokey.yaml` file into a `PokeyConfig` object."""
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except OSError as exc:
        raise ConfigError(f"Failed to read {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} must contain a top-level YAML mapping.")

    name = str(data.get("name") or "").strip()
    if not name:
        raise ConfigError("Missing required field `name` in pokey.yaml.")

    if "base" not in data or data["base"] is None:
        raise ConfigError("Missing required field `base` in pokey.yaml.")

    raw_mode = str(data.get("mode", PodMode.RUN.value))
    try:
        mode = PodMode(raw_mode)
    except ValueError as exc:
        valid = ", ".join(m.value for m in PodMode)
        raise ConfigError(f"Invalid `mode` {raw_mode!r}; expected one of: {valid}") from exc

    extra = {k: v for k, v in data.items() if k not in _KNOWN_TOP_KEYS}

    config = PokeyConfig(
        version=str(data.get("version", "1")),
        name=name,
        mode=mode,
        base=_parse_base(data["base"]),
        logging=_parse_logging(data.get("logging")),
        resources=_parse_resources(data.get("resources")),
        perf=_parse_perf(data.get("perf")),
        run=_parse_run(data.get("run")),
        dev=_parse_dev(data.get("dev")),
        extra=extra,
        config_dir=config_path.parent,
    )

    try:
        config.validate()
    except ValueError as exc:
        raise ConfigError(f"Invalid configuration in {config_path}: {exc}") from exc

    return config


def dump_config(config: PokeyConfig, path: str | Path) -> Path:
    """Serialize a `PokeyConfig` dataclass to a YAML file."""
    output = Path(path).expanduser()
    payload: dict[str, Any] = {
        "version": config.version,
        "name": config.name,
        "mode": config.mode.value,
        "base": {
            "name": config.base.name,
            "tag": config.base.tag,
            "repo_url": config.base.repo_url,
            "branch": config.base.branch,
            "raw_image": config.base.raw_image,
        },
        "logging": {
            "enabled": config.logging.enabled,
            "host_dir": config.logging.host_dir,
            "container_dir": config.logging.container_dir,
        },
        "resources": {
            "gpus": config.resources.gpus,
            "shm_size": config.resources.shm_size,
            "network_mode": config.resources.network_mode,
        },
        "perf": {
            "enabled": config.perf.enabled,
            "gpu_profiling": config.perf.gpu_profiling,
            "mount_host_perf": config.perf.mount_host_perf,
            "pid_host": config.perf.pid_host,
            "profile_subdir": config.perf.profile_subdir,
        },
        "run": {
            "strategy": config.run.strategy.value,
            "apt": list(config.run.apt),
            "apt_mirror": config.run.apt_mirror,
            "pip": list(config.run.pip),
            "requirements_file": config.run.requirements_file,
            "pip_index_url": config.run.pip_index_url,
            "env_file": config.run.env_file,
            "env": dict(config.run.env),
            "workdir": config.run.workdir,
            "entrypoint": config.run.entrypoint,
            "debug": config.run.debug,
            "ports": list(config.run.ports),
            "mounts": list(config.run.mounts),
            "cache_dir": config.run.cache_dir,
        },
        "dev": {
            "workspace_host": config.dev.workspace_host,
            "workspace_container": config.dev.workspace_container,
            "persist_home": config.dev.persist_home,
            "remote_user": config.dev.remote_user,
            "ports": list(config.dev.ports),
            "mounts": list(config.dev.mounts),
            "vscode_extensions": list(config.dev.vscode_extensions),
        },
    }
    payload.update(config.extra)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output


def generate_config_template(
    output_path: str | Path = DEFAULT_CONFIG_FILENAME,
    *,
    name: str = "my-pod",
    base_name: str = "ubuntu24-py312",
    mode: PodMode = PodMode.RUN,
    force: bool = False,
) -> Path:
    """Generate a starter `pokey.yaml` from the bundled package template."""
    target = Path(output_path).expanduser()
    if target.exists() and not force:
        raise ConfigError(f"{target} already exists. Pass --force to overwrite.")

    template_text = (
        resources.files("pokeymans.templates")
        .joinpath("pokey.yaml.tmpl")
        .read_text(encoding="utf-8")
    )
    rendered = (
        template_text.replace("${name}", name)
        .replace("${base_name}", base_name)
        .replace("${mode}", mode.value)
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return target


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a `.env` file into key-value pairs."""
    if not path.is_file():
        raise ConfigError(f"Environment file not found: {path}")

    result: dict[str, str] = {}
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ConfigError(f"Invalid env entry at {path}:{line_no}: {raw_line!r}")
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if not key:
            raise ConfigError(f"Empty env key at {path}:{line_no}")
        result[key] = val
    return result


def parse_mount_string(raw: str, base_dir: Path | None = None) -> MountSpec:
    """Parse `source:target[:ro|rw]` into a normalized `MountSpec`."""
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ConfigError(f"Invalid mount syntax {raw!r}; expected `source:target[:ro|rw]`.")

    source_raw, target = parts[0].strip(), parts[1].strip()
    mode_flag = parts[2].strip() if len(parts) == 3 else "rw"
    if not source_raw or not target:
        raise ConfigError(f"Invalid mount syntax {raw!r}: source and target must be non-empty.")
    if not target.startswith("/"):
        raise ConfigError(f"Invalid mount target {target!r}: must be an absolute container path.")
    if mode_flag not in ("ro", "rw"):
        raise ConfigError(f"Invalid mount mode {mode_flag!r} in {raw!r}; expected 'ro' or 'rw'.")

    is_bind = (
        source_raw.startswith("/")
        or source_raw.startswith(".")
        or source_raw.startswith("~")
        or "/" in source_raw
    )
    if is_bind:
        src_path = Path(source_raw).expanduser()
        if not src_path.is_absolute():
            src_path = ((base_dir or Path.cwd()) / src_path).resolve()
        return MountSpec(
            source=str(src_path),
            target=target,
            read_only=(mode_flag == "ro"),
            mount_type="bind",
        )

    return MountSpec(
        source=source_raw,
        target=target,
        read_only=(mode_flag == "ro"),
        mount_type="volume",
    )
