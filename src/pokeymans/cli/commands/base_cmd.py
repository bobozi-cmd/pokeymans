"""CLI command group: `pokey base sync|list|info|pull` (backed by `base-images` branch)."""

from __future__ import annotations

import argparse

from pokeymans.client import PokeyClient
from pokeymans.models.config import (
    DEFAULT_BASE_IMAGES_BRANCH,
    DEFAULT_BASE_IMAGES_REPO,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_base = subparsers.add_parser(
        "base",
        help="Manage base images indexed on the git `base-images` branch.",
    )
    p_base.add_argument(
        "--repo",
        default=DEFAULT_BASE_IMAGES_REPO,
        help=f"Git repo hosting base-images branch (default: {DEFAULT_BASE_IMAGES_REPO}).",
    )
    p_base.add_argument(
        "--branch",
        default=DEFAULT_BASE_IMAGES_BRANCH,
        help=f"Branch name hosting base images catalog (default: {DEFAULT_BASE_IMAGES_BRANCH}).",
    )
    base_sub = p_base.add_subparsers(dest="base_command", metavar="<subcommand>")

    # --- base sync ---
    p_sync = base_sub.add_parser(
        "sync",
        help="Fetch/update the local catalog cache from the `base-images` branch.",
    )
    p_sync.add_argument(
        "--force",
        action="store_true",
        help="Force fresh fetch from remote `base-images` branch.",
    )
    p_sync.set_defaults(handler=handle_base_sync)

    # --- base list ---
    p_list = base_sub.add_parser(
        "list",
        help="List all base images registered on the `base-images` branch.",
    )
    p_list.add_argument(
        "--tag",
        dest="tag_filter",
        default=None,
        help="Filter base images by catalog tag (e.g. python, gpu).",
    )
    p_list.set_defaults(handler=handle_base_list)

    # --- base info ---
    p_info = base_sub.add_parser(
        "info",
        help="Display metadata and Dockerfile path for a base image.",
    )
    p_info.add_argument("name", help="Base image name (or `<name>:<tag>`).")
    p_info.set_defaults(handler=handle_base_info)

    # --- base pull ---
    p_pull = base_sub.add_parser(
        "pull",
        help="Resolve and pull (or build locally) a base image from `base-images`.",
    )
    p_pull.add_argument("name", help="Base image name (or `<name>:<tag>`).")
    p_pull.add_argument(
        "--rebuild",
        action="store_true",
        help="Build locally from the `base-images` Dockerfile even if registry_ref is set.",
    )
    p_pull.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing `base-images` branch before resolving.",
    )
    p_pull.set_defaults(handler=handle_base_pull)

    p_base.set_defaults(handler=lambda _args, _client: _print_help(p_base))


def _print_help(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 0


def _apply_registry_overrides(args: argparse.Namespace, client: PokeyClient) -> None:
    client.registry.repo_url = args.repo
    client.registry.branch = args.branch


def handle_base_sync(args: argparse.Namespace, client: PokeyClient) -> int:
    _apply_registry_overrides(args, client)
    cache_dir = client.base_sync(force=args.force)
    print(f"Synced base-images catalog to {cache_dir}")
    return 0


def handle_base_list(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Render formatted table of available base images.
    _apply_registry_overrides(args, client)
    client.base_list(tag_filter=args.tag_filter)
    return 0


def handle_base_info(args: argparse.Namespace, client: PokeyClient) -> int:
    # TODO: Pretty-print BaseImageSpec fields.
    _apply_registry_overrides(args, client)
    client.base_info(args.name)
    return 0


def handle_base_pull(args: argparse.Namespace, client: PokeyClient) -> int:
    _apply_registry_overrides(args, client)
    image_ref = client.base_pull(
        args.name,
        rebuild=args.rebuild,
        sync_first=not args.no_sync,
    )
    print(f"Base image ready: {image_ref}")
    return 0
