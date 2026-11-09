"""Command-line interface: ``speedyindex <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .client import SpeedyIndex, SpeedyIndexError


def _read_urls(path: str) -> List[str]:
    stream = sys.stdin if path == "-" else open(path, encoding="utf-8")
    with stream:
        return [line.strip() for line in stream if line.strip()]


def _print(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="speedyindex", description="SpeedyIndex API v2 command-line client")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--api-key", help="API key (default: SPEEDYINDEX_API_KEY env var)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("balance", help="show account balance")

    for name, ttype in (("check", "checker"), ("index", "indexer")):
        s = sub.add_parser(name, help=f"create a {ttype} task from a file of URLs (one per line, '-' for stdin)")
        s.add_argument("file")
        s.add_argument("--engine", default="google", choices=["google", "yandex", "bing"])
        s.add_argument("--title")
        s.add_argument("--drip-feed-days", type=int, help="spread submission over N days (2-30)")
        s.set_defaults(task_type=ttype)

    s = sub.add_parser("status", help="status of one or more tasks")
    s.add_argument("task_ids", nargs="+")
    s.add_argument("--engine", default="google")
    s.add_argument("--type", dest="task_type", default="checker", choices=["checker", "indexer"])

    s = sub.add_parser("report", help="full report of a task")
    s.add_argument("task_id")
    s.add_argument("--engine", default="google")
    s.add_argument("--type", dest="task_type", default="checker", choices=["checker", "indexer"])

    s = sub.add_parser("tasks", help="list tasks")
    s.add_argument("--engine", default="google")
    s.add_argument("--page", type=int, default=0)

    s = sub.add_parser("backlinks", help="check donor pages for links to your domains")
    s.add_argument("file")
    s.add_argument("--target", action="append", required=True, help="your domain, repeatable")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = SpeedyIndex(api_key=args.api_key)
        if args.command == "balance":
            _print(client.balance())
        elif args.command in ("check", "index"):
            _print(client.create_task(
                _read_urls(args.file), engine=args.engine, task_type=args.task_type, title=args.title,
                drip_feed=bool(args.drip_feed_days), drip_feed_days=args.drip_feed_days,
            ))
        elif args.command == "status":
            _print(client.task_status(args.task_ids, engine=args.engine, task_type=args.task_type))
        elif args.command == "report":
            _print(client.full_report(args.task_id, engine=args.engine, task_type=args.task_type))
        elif args.command == "tasks":
            _print(client.list_tasks(engine=args.engine, page=args.page))
        elif args.command == "backlinks":
            _print(client.create_backlink_check(_read_urls(args.file), args.target))
    except (SpeedyIndexError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
