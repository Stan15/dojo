from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from . import db

VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def _db_path(args: argparse.Namespace) -> Path | None:
    return Path(args.db) if getattr(args, "db", None) else None


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True))


def _validate_name(name: str) -> None:
    if not VALID_NAME.fullmatch(name):
        raise SystemExit("invalid AI connector name: use 1-64 letters, numbers, hyphen, or underscore, starting with a letter")


def _render(connector: dict[str, Any], *, next_action: str | None = None) -> dict[str, Any]:
    rendered = dict(connector)
    if next_action:
        rendered["next"] = next_action
    return rendered


def cmd_connect_ai_command(args: argparse.Namespace) -> int:
    _validate_name(args.name)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    elif args.command:
        raw = list(args.command)
        external: list[str] = []
        idx = 0
        while idx < len(raw):
            token = raw[idx]
            if token == "--":
                external = raw[idx + 1 :]
                break
            if token == "--default":
                args.default = True
                idx += 1
                continue
            if token == "--replace":
                args.replace = True
                idx += 1
                continue
            if token in {"--input", "--output", "--timeout"}:
                if idx + 1 >= len(raw):
                    raise SystemExit(f"{token} requires a value")
                value = raw[idx + 1]
                if token == "--input":
                    args.input = value
                elif token == "--output":
                    args.output = value
                else:
                    args.timeout = int(value)
                idx += 2
                continue
            external = raw[idx:]
            break
        args.command = external
    if not args.command:
        raise SystemExit("command connector requires argv after --")
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            connector = db.save_ai_connector(
                conn,
                name=args.name,
                argv=args.command,
                input_mode=args.input,
                output_mode=args.output,
                timeout_seconds=args.timeout,
                is_default=args.default,
                replace=args.replace,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


def cmd_connect_ai_list(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        _print_json(db.list_ai_connectors(conn))
    return 0


def cmd_connect_ai_show(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        connector = db.get_ai_connector(conn, args.name)
    if connector is None:
        raise SystemExit(f"unknown AI connector: {args.name}")
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


def cmd_connect_ai_use(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            connector = db.set_default_ai_connector(conn, args.name)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json(_render(connector, next_action=f"dojo connect ai test {connector['name']}"))
    return 0


def cmd_connect_ai_remove(args: argparse.Namespace) -> int:
    db.init_db(_db_path(args))
    with db.connect(_db_path(args)) as conn:
        try:
            removed = db.remove_ai_connector(conn, args.name, force=args.force)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    _print_json({"removed": removed["name"], "was_default": removed["is_default"]})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dojo")
    parser.add_argument("--db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    connect = sub.add_parser("connect")
    connect_sub = connect.add_subparsers(dest="connect_command", required=True)
    ai = connect_sub.add_parser("ai")
    ai_sub = ai.add_subparsers(dest="ai_command", required=True)

    p_command = ai_sub.add_parser("command")
    p_command.add_argument("name")
    p_command.add_argument("--default", action="store_true")
    p_command.add_argument("--input", default="stdin-prompt", choices=["stdin-prompt", "stdin-json", "request-json-file"])
    p_command.add_argument("--output", default="stdout-json-or-text", choices=["stdout-json-or-text"])
    p_command.add_argument("--timeout", type=int, default=120)
    p_command.add_argument("--replace", action="store_true")
    p_command.add_argument("command", nargs=argparse.REMAINDER)
    p_command.set_defaults(func=cmd_connect_ai_command)

    p_list = ai_sub.add_parser("list")
    p_list.set_defaults(func=cmd_connect_ai_list)
    p_show = ai_sub.add_parser("show")
    p_show.add_argument("name")
    p_show.set_defaults(func=cmd_connect_ai_show)
    p_use = ai_sub.add_parser("use")
    p_use.add_argument("name")
    p_use.set_defaults(func=cmd_connect_ai_use)
    p_default = ai_sub.add_parser("default", help="deprecated alias for use")
    p_default.add_argument("name")
    p_default.set_defaults(func=cmd_connect_ai_use)
    p_remove = ai_sub.add_parser("remove")
    p_remove.add_argument("name")
    p_remove.add_argument("--force", action="store_true")
    p_remove.set_defaults(func=cmd_connect_ai_remove)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
