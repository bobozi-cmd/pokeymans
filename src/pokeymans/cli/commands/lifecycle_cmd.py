"""CLI commands: `pokey up`, `update`, `down`, `status`, `logs`, `exec`."""

from __future__ import annotations

import argparse

from pokeymans.client import PokeyClient
from pokeymans.models.config import (
    DEFAULT_CONFIG_FILENAME,
    PodMode,
    ProvisionStrategy,
)


def _add_config_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help=f"Path to pokey configuration file (default: {DEFAULT_CONFIG_FILENAME}).",
    )


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    # --- up ---
    p_up = subparsers.add_parser(
        "up",
        help="Start pod environment according to pokey.yaml (Run Mode or Dev Mode).",
    )
    _add_config_flag(p_up)
    p_up.add_argument(
        "--mode",
        choices=[m.value for m in PodMode],
        default=None,
        help="Override mode from pokey.yaml (run | dev).",
    )
    p_up.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="[Run Mode] Skip service entrypoint script and keep container alive for debugging.",
    )
    p_up.add_argument(
        "--strategy",
        choices=[s.value for s in ProvisionStrategy],
        default=None,
        help="[Run Mode] Provisioning strategy: runtime (Scheme B, default) or build (Scheme A).",
    )
    p_up.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate container even if it is already running.",
    )
    p_up.set_defaults(handler=handle_up)

    # --- update ---
    p_update = subparsers.add_parser(
        "update",
        help="[Run Mode] Update running service with latest pokey.yaml (apt/pip/env/entrypoint/debug).",
    )
    _add_config_flag(p_update)
    debug_group = p_update.add_mutually_exclusive_group()
    debug_group.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=None,
        help="Enable debug mode (do not run service entrypoint).",
    )
    debug_group.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        help="Disable debug mode and execute service entrypoint.",
    )
    p_update.add_argument(
        "--strategy",
        choices=[s.value for s in ProvisionStrategy],
        default=None,
        help="Override Run Mode strategy (runtime | build).",
    )
    p_update.add_argument(
        "--reinstall-deps",
        action="store_true",
        help="Force re-installing apt/pip dependencies (or no-cache rebuild in Scheme A).",
    )
    p_update.set_defaults(handler=handle_update)

    # --- down ---
    p_down = subparsers.add_parser(
        "down",
        help="Stop and remove pod container(s).",
    )
    _add_config_flag(p_down)
    p_down.add_argument(
        "--mode",
        choices=[PodMode.RUN.value, PodMode.DEV.value, "all"],
        default=None,
        help="Which mode container to tear down (default: mode in pokey.yaml).",
    )
    p_down.add_argument(
        "--purge-volumes",
        action="store_true",
        help="Also remove persistent Dev Mode named volumes (host /var/log/${pod-name} is preserved).",
    )
    p_down.set_defaults(handler=handle_down)

    # --- status ---
    p_status = subparsers.add_parser(
        "status",
        help="Show pod container status, mode, base image, and /var/log/${pod-name} mount.",
    )
    _add_config_flag(p_status)
    p_status.add_argument(
        "--mode",
        choices=[PodMode.RUN.value, PodMode.DEV.value, "all"],
        default="all",
        help="Filter by mode (default: all).",
    )
    p_status.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print status as JSON.",
    )
    p_status.set_defaults(handler=handle_status)

    # --- logs ---
    p_logs = subparsers.add_parser(
        "logs",
        help="Stream or display pod container logs.",
    )
    _add_config_flag(p_logs)
    p_logs.add_argument(
        "--mode",
        choices=[m.value for m in PodMode],
        default=None,
        help="Target pod mode (default: mode in pokey.yaml).",
    )
    p_logs.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow log output.",
    )
    p_logs.add_argument(
        "--tail",
        type=int,
        default=None,
        help="Number of lines to show from the end of the logs.",
    )
    p_logs.set_defaults(handler=handle_logs)

    # --- exec ---
    p_exec = subparsers.add_parser(
        "exec",
        help="Execute a command inside the running pod container (default: bash).",
    )
    _add_config_flag(p_exec)
    p_exec.add_argument(
        "--mode",
        choices=[m.value for m in PodMode],
        default=None,
        help="Target pod mode (default: mode in pokey.yaml).",
    )
    p_exec.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute inside the container (prefix with `--`).",
    )
    p_exec.set_defaults(handler=handle_exec)


def handle_up(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Render clean summary table (container name, mode, debug, /var/log/${pod-name} mount).
    config = client.load_config(args.config)
    mode = PodMode(args.mode) if args.mode else None
    strategy = ProvisionStrategy(args.strategy) if args.strategy else None
    client.up(
        config,
        mode=mode,
        debug=args.debug,
        strategy=strategy,
        recreate=args.recreate,
    )
    return 0


def handle_update(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Display updated service status and diff summary.
    config = client.load_config(args.config)
    strategy = ProvisionStrategy(args.strategy) if args.strategy else None
    client.update(
        config,
        debug=args.debug,
        strategy=strategy,
        reinstall_deps=args.reinstall_deps,
    )
    return 0


def handle_down(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Print stopped/removed containers.
    config = client.load_config(args.config)
    all_modes = args.mode == "all"
    mode = None if (args.mode is None or all_modes) else PodMode(args.mode)
    client.down(
        config,
        mode=mode,
        all_modes=all_modes,
        purge_volumes=args.purge_volumes,
    )
    return 0


def handle_status(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Format status output as table or JSON (`--json`).
    config = client.load_config(args.config)
    all_modes = args.mode == "all"
    mode = None if all_modes else PodMode(args.mode)
    client.status(config, mode=mode, all_modes=all_modes)
    return 0


def handle_logs(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Also print host log directory `/var/log/${pod-name}` hint.
    config = client.load_config(args.config)
    mode = PodMode(args.mode) if args.mode else None
    client.logs(config, mode=mode, follow=args.follow, tail=args.tail)
    return 0


def handle_exec(args: argparse.Namespace, client: PokeyClient) -> int:
    config = client.load_config(args.config)
    mode = PodMode(args.mode) if args.mode else None
    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    return client.exec(config, command=cmd or ["bash"], mode=mode)
