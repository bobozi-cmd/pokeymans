"""CLI command group: `pokey dev init|open|snapshot|export`."""

from __future__ import annotations

import argparse
from pathlib import Path

from pokeymans.client import PokeyClient
from pokeymans.models.config import DEFAULT_CONFIG_FILENAME


def _add_config_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help=f"Path to pokey configuration file (default: {DEFAULT_CONFIG_FILENAME}).",
    )


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_dev = subparsers.add_parser(
        "dev",
        help="Dev Mode & VS Code Dev Container management.",
    )
    dev_sub = p_dev.add_subparsers(dest="dev_command", metavar="<subcommand>")

    # --- dev init ---
    p_init = dev_sub.add_parser(
        "init",
        help="Generate .devcontainer/devcontainer.json from pokey.yaml.",
    )
    _add_config_flag(p_init)
    p_init.add_argument(
        "--dir",
        dest="project_dir",
        default=".",
        help="Project directory where .devcontainer/ will be created (default: .).",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .devcontainer/devcontainer.json.",
    )
    p_init.set_defaults(handler=handle_dev_init)

    # --- dev open ---
    p_open = dev_sub.add_parser(
        "open",
        help="Ensure dev container / devcontainer.json is ready and open VS Code.",
    )
    _add_config_flag(p_open)
    p_open.add_argument(
        "--dir",
        dest="project_dir",
        default=".",
        help="Project directory (default: .).",
    )
    p_open.set_defaults(handler=handle_dev_open)

    # --- dev snapshot ---
    p_snap = dev_sub.add_parser(
        "snapshot",
        help="Commit current Dev Mode container into a reusable Docker image.",
    )
    _add_config_flag(p_snap)
    p_snap.add_argument(
        "target_image",
        help="Target Docker image tag (e.g. my-service-dev:v1).",
    )
    p_snap.add_argument(
        "-m",
        "--message",
        default=None,
        help="Optional commit message for the snapshot image.",
    )
    p_snap.set_defaults(handler=handle_dev_snapshot)

    # --- dev export ---
    p_export = dev_sub.add_parser(
        "export",
        help="Export ad-hoc packages installed in Dev container as a pokey.yaml snippet.",
    )
    _add_config_flag(p_export)
    p_export.set_defaults(handler=handle_dev_export)

    p_dev.set_defaults(handler=lambda _args, _client: _print_help(p_dev))


def _print_help(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 0


def handle_dev_init(args: argparse.Namespace, client: PokeyClient) -> int:
    config = client.load_config(args.config)
    path = client.dev_init(
        config,
        project_dir=Path(args.project_dir),
        force=args.force,
    )
    print(f"Generated {path}")
    return 0


def handle_dev_open(args: argparse.Namespace, client: PokeyClient) -> int:
    config = client.load_config(args.config)
    client.dev_open(config, project_dir=Path(args.project_dir))
    return 0


def handle_dev_snapshot(args: argparse.Namespace, client: PokeyClient) -> int:
    config = client.load_config(args.config)
    image = client.dev_snapshot(config, args.target_image, message=args.message)
    print(f"Created snapshot image: {image}")
    return 0


def handle_dev_export(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Render exported apt/pip dict as YAML snippet.
    config = client.load_config(args.config)
    client.dev_export(config)
    return 0
