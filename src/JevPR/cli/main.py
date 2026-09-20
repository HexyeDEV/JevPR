from __future__ import annotations

import argparse

from JevPR.config import settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jevpr")
    parser.add_argument("command", choices=["config", "health"])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "config":
        routing = settings.load_routing_config()
        print(routing.model_dump())
    elif args.command == "health":
        print({"status": "ok"})


if __name__ == "__main__":
    main()