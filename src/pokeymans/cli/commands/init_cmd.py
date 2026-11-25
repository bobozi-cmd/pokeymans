"""CLI command: `pokey init`."""

from __future__ import annotations

import argparse

from pokeymans.client import PokeyClient
from pokeymans.models.config import DEFAULT_CONFIG_FILENAME, PodMode


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "init",
        help="Initialize a starter pokey.yaml configuration file.",
    )
    parser.add_argument(
        "--name",
        default="my-pod",
        help="Pod name (also used for default /var/log/${pod-name} mount).",
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Base image name from the `base-images` branch catalog.",
    )
    parser.add_argument(
        "--mode",
        choices=[m.value for m in PodMode],
        default=PodMode.RUN.value,
        help="Default pod mode written to pokey.yaml (default: run).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_CONFIG_FILENAME,
        help=f"Output file path (default: {DEFAULT_CONFIG_FILENAME}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pokey.yaml if present.",
    )
    parser.set_defaults(handler=handle_init)


def handle_init(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Handle output formatting and confirmation message after template generation.
    path = client.init_config(
        output_path=args.output,
        name=args.name,
        base_name=args.base,
        mode=PodMode(args.mode),
        force=args.force,
    )
    print(f"Created {path}")
    return 0
