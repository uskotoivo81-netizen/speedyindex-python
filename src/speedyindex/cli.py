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
    p = argparse.ArgumentParser(prog="speedyindex", description="SpeedyIndex API v2 command-line client: indexing, index checks, Rank Tracker")
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

    s = sub.add_parser("report", help="report of a task: indexed / unindexed URLs")
    s.add_argument("task_id")
    s.add_argument("--engine", default="google")
    s.add_argument("--type", dest="task_type", default="checker", choices=["checker", "indexer"])
    s.add_argument("--full", action="store_true", help="full report: SERP titles and error codes")
    s.add_argument("--unindexed", action="store_true", help="print only unindexed URLs, one per line")

    s = sub.add_parser("tasks", help="list tasks")
    s.add_argument("--engine", default="google")
    s.add_argument("--type", dest="task_type", default="indexer", choices=["checker", "indexer"])
    s.add_argument("--page", type=int, default=0)

    r = sub.add_parser("rank", help="Rank Tracker: Google positions").add_subparsers(dest="rank_cmd", required=True)
    r.add_parser("limits", help="limits, prices and balance")
    s = r.add_parser("locations", help="find a location for a region")
    s.add_argument("q")
    s.add_argument("--gl")
    r.add_parser("projects", help="list projects")
    s = r.add_parser("create", help="create a project")
    s.add_argument("domain")
    s.add_argument("--location", required=True, help="canonical_name from 'rank locations'")
    s.add_argument("--gl", required=True, help="country code, e.g. us")
    s.add_argument("--keywords", help="file with one keyword per line ('-' for stdin)")
    s.add_argument("--depth", type=int, choices=[10, 30, 50, 100])
    s.add_argument("--ref", help="your id: makes the request safe to repeat")
    s = r.add_parser("add-keywords", help="add keywords from a file")
    s.add_argument("project_id")
    s.add_argument("file")
    s = r.add_parser("check", help="run a check")
    s.add_argument("project_id")
    s.add_argument("--wait", action="store_true", help="wait until the check ends")
    s = r.add_parser("positions", help="positions of the latest (or given) check")
    s.add_argument("project_id")
    s.add_argument("--check-id")
    s.add_argument("--changed-only", action="store_true")
    s = r.add_parser("export", help="export positions as CSV or JSON to stdout")
    s.add_argument("project_id")
    s.add_argument("--format", default="csv", choices=["csv", "json"])
    s.add_argument("--check-id")

    s = sub.add_parser("backlinks", help="check donor pages for links to your domains")
    s.add_argument("file")
    s.add_argument("--target", action="append", required=True, help="your domain, repeatable")
    return p


def _rank(client: SpeedyIndex, args: argparse.Namespace) -> None:
    rt = client.rank
    cmd = args.rank_cmd
    if cmd == "limits":
        _print(rt.limits())
    elif cmd == "locations":
        _print(rt.locations(args.q, gl=args.gl))
    elif cmd == "projects":
        _print(list(rt.projects()))
    elif cmd == "create":
        extra = {"depth": args.depth} if args.depth else {}
        keywords = _read_urls(args.keywords) if args.keywords else None
        _print(rt.create_project(args.domain, [{"location": args.location, "gl": args.gl}],
                                 keywords=keywords, ref=args.ref, **extra))
    elif cmd == "add-keywords":
        _print(rt.add_keywords(args.project_id, _read_urls(args.file)))
    elif cmd == "check":
        check = rt.run_check(args.project_id)
        _print(rt.wait(check["id"]) if args.wait else check)
    elif cmd == "positions":
        for row in rt.positions(args.project_id, check_id=args.check_id, changed_only=args.changed_only or None):
            pos = row.get("position") if row.get("found") else "-"
            print(f"{pos}\t{row.get('q')}\t{row.get('url') or ''}")
    elif cmd == "export":
        sys.stdout.buffer.write(rt.export(args.project_id, format=args.format, check_id=args.check_id))


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
            if args.full:
                data = client.full_report(args.task_id, engine=args.engine, task_type=args.task_type)
            else:
                data = client.report(args.task_id, engine=args.engine, task_type=args.task_type)
            if args.unindexed:
                for item in data.get("unindexed_links") or []:
                    print(item.get("url") if isinstance(item, dict) else item)
            else:
                _print(data)
        elif args.command == "tasks":
            _print(client.list_tasks(engine=args.engine, task_type=args.task_type, page=args.page))
        elif args.command == "rank":
            _rank(client, args)
        elif args.command == "backlinks":
            _print(client.create_backlink_check(_read_urls(args.file), args.target))
    except (SpeedyIndexError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
