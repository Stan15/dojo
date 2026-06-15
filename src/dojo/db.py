from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "dojo" / "dojo.sqlite3"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ai_connectors (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                argv_json TEXT NOT NULL,
                input_mode TEXT NOT NULL,
                output_mode TEXT NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                last_test_status TEXT,
                last_test_at TEXT,
                last_test_summary TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS generation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                request_json TEXT NOT NULL,
                raw_output TEXT NOT NULL,
                status TEXT NOT NULL,
                diagnostics_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def _connector_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "kind": row["kind"],
        "argv": json.loads(row["argv_json"]),
        "input_mode": row["input_mode"],
        "output_mode": row["output_mode"],
        "timeout_seconds": row["timeout_seconds"],
        "is_default": bool(row["is_default"]),
        "last_test_status": row["last_test_status"],
        "last_test_at": row["last_test_at"],
        "last_test_summary": row["last_test_summary"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_ai_connector(
    conn: sqlite3.Connection,
    *,
    name: str,
    argv: list[str],
    kind: str = "command",
    input_mode: str = "stdin-prompt",
    output_mode: str = "stdout-json-or-text",
    timeout_seconds: int = 120,
    is_default: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    if not argv:
        raise ValueError("command connector argv cannot be empty")
    existing = conn.execute("SELECT name FROM ai_connectors WHERE name = ?", (name,)).fetchone()
    if existing and not replace:
        raise ValueError(f"AI connector already exists: {name}; pass --replace to update")
    if is_default:
        conn.execute("UPDATE ai_connectors SET is_default = 0")
    if existing:
        conn.execute(
            """
            UPDATE ai_connectors
            SET kind=?, argv_json=?, input_mode=?, output_mode=?, timeout_seconds=?,
                is_default=?, updated_at=CURRENT_TIMESTAMP
            WHERE name=?
            """,
            (kind, json.dumps(argv), input_mode, output_mode, timeout_seconds, int(is_default), name),
        )
    else:
        conn.execute(
            """
            INSERT INTO ai_connectors
            (name, kind, argv_json, input_mode, output_mode, timeout_seconds, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, kind, json.dumps(argv), input_mode, output_mode, timeout_seconds, int(is_default)),
        )
    conn.commit()
    return get_ai_connector(conn, name)  # type: ignore[return-value]


def get_ai_connector(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM ai_connectors WHERE name = ?", (name,)).fetchone()
    return _connector_from_row(row) if row else None


def list_ai_connectors(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM ai_connectors ORDER BY is_default DESC, name ASC").fetchall()
    return [_connector_from_row(row) for row in rows]


def set_default_ai_connector(conn: sqlite3.Connection, name: str) -> dict[str, Any]:
    if get_ai_connector(conn, name) is None:
        raise ValueError(f"unknown AI connector: {name}")
    conn.execute("UPDATE ai_connectors SET is_default = 0")
    conn.execute("UPDATE ai_connectors SET is_default = 1, updated_at=CURRENT_TIMESTAMP WHERE name = ?", (name,))
    conn.commit()
    return get_ai_connector(conn, name)  # type: ignore[return-value]


def remove_ai_connector(conn: sqlite3.Connection, name: str, *, force: bool = False) -> dict[str, Any]:
    connector = get_ai_connector(conn, name)
    if connector is None:
        raise ValueError(f"unknown AI connector: {name}")
    if connector["is_default"] and not force:
        raise ValueError(f"refusing to remove default connector {name}; pass --force or choose another default first")
    conn.execute("DELETE FROM ai_connectors WHERE name = ?", (name,))
    conn.commit()
    return connector


def record_generation_run(conn: sqlite3.Connection, *, task: str, request: dict[str, Any], raw_output: str, status: str, diagnostics: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO generation_runs (task, request_json, raw_output, status, diagnostics_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (task, json.dumps(request, sort_keys=True), raw_output, status, json.dumps(diagnostics, sort_keys=True)),
    )
    conn.commit()
    return int(cur.lastrowid)
