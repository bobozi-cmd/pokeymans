"""Main entry point and argument parser for the `pokey` CLI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from pokeymans import __version__
from pokeymans.cli.commands import base_cmd, dev_cmd, doctor_cmd, init_cmd, lifecycle_cmd
from pokeymans.client import PokeyClient
from pokeymans.exceptions import PokeyError


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level `pokey` CLI parser and all subcommands."""
    parser = argparse.ArgumentParser(
        prog="pokey",
        description=(
            "pokeymans - Lightweight pod environment builder "
            "(Run Mode with runtime bootstrap / Dev Mode with VS Code Dev Containers)."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    init_cmd.register(subparsers)
    lifecycle_cmd.register(subparsers)
    dev_cmd.register(subparsers)
    base_cmd.register(subparsers)
    doctor_cmd.register(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point registered as `pokey` and `pokeymans`."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    client = PokeyClient()
    try:
        return int(handler(args, client))
    except NotImplementedError as exc:
        print(f"[NOT IMPLEMENTED] {exc}", file=sys.stderr)
        return 2
    except PokeyError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
