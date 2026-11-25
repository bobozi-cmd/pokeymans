"""CLI command: `pokey doctor`."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from pokeymans.client import PokeyClient


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="Check host readiness for Docker, CPU perf/flamegraphs, and NVIDIA nsys/ncu.",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Treat missing NVIDIA GPU / container toolkit as failures.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output diagnostics as JSON.",
    )
    parser.set_defaults(handler=handle_doctor)


def handle_doctor(args: argparse.Namespace, client: PokeyClient) -> int:
    results = client.doctor(check_gpu=args.gpu)
    if args.as_json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        header = f"{'CHECK':<28} {'STATUS':<8} {'DETAIL'}"
        print(header)
        print("-" * len(header))
        for item in results:
            tag = item.status.upper()
            print(f"{item.name:<28} {tag:<8} {item.detail}")
            if item.remediation:
                print(f"  -> Fix: {item.remediation}")

    return 1 if any(r.status == "fail" for r in results) else 0
