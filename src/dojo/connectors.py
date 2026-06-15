from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import db

STDERR_TAIL_CHARS = 4000


@dataclass(frozen=True)
class CommandConnectorResult:
    status: str
    connector_name: str | None
    input_mode: str | None
    output_mode: str | None
    request: dict[str, Any]
    raw_stdout: str
    raw_stderr: str
    stderr_tail: str
    exit_code: int | None
    duration_seconds: float
    parse_status: str
    parsed_stdout: Any | None = None
    parse_warning: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_task_request_prompt(request: dict[str, Any]) -> str:
    task = request.get("task", "task")
    return f"Task: {task}\n\nRequest JSON:\n{json.dumps(request, indent=2, sort_keys=True)}\n"


def _default_connector(conn) -> dict[str, Any] | None:
    for connector in db.list_ai_connectors(conn):
        if connector.get("is_default"):
            return connector
    return None


def _resolve_connector(db_path: str | Path | None, connector_name: str | None) -> dict[str, Any] | None:
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        if connector_name:
            return db.get_ai_connector(conn, connector_name)
        return _default_connector(conn)


def _failure(*, request: dict[str, Any], error: str, connector: dict[str, Any] | None = None, duration_seconds: float = 0.0) -> CommandConnectorResult:
    return CommandConnectorResult(
        status="failed",
        connector_name=connector.get("name") if connector else None,
        input_mode=connector.get("input_mode") if connector else None,
        output_mode=connector.get("output_mode") if connector else None,
        request=request,
        raw_stdout="",
        raw_stderr="",
        stderr_tail="",
        exit_code=None,
        duration_seconds=duration_seconds,
        parse_status="not-run",
        error=error,
    )


def _stdin_for_mode(input_mode: str, request: dict[str, Any], request_file: Path | None) -> str | None:
    if input_mode == "stdin-prompt":
        return render_task_request_prompt(request)
    if input_mode == "stdin-json":
        return json.dumps(request, sort_keys=True)
    if input_mode == "request-json-file":
        if request_file is None:
            raise ValueError("request-json-file mode requires request_file")
        request_file.write_text(json.dumps(request, indent=2, sort_keys=True))
        return None
    raise ValueError(f"unsupported connector input mode: {input_mode}")


def _parse_stdout(stdout: str) -> tuple[str, Any | None, str | None]:
    stripped = stdout.strip()
    if not stripped:
        return "empty", None, "stdout was empty"
    try:
        return "json", json.loads(stripped), None
    except json.JSONDecodeError as exc:
        return "text", None, f"stdout was not JSON: {exc.msg}"


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def invoke_command_connector(db_path: str | Path | None, request: dict[str, Any], *, connector_name: str | None = None) -> CommandConnectorResult:
    connector = _resolve_connector(db_path, connector_name)
    if connector is None:
        name = f"AI connector {connector_name!r}" if connector_name else "no default AI connector"
        return _failure(request=request, error=f"{name} configured")
    if connector.get("kind") != "command":
        return _failure(request=request, connector=connector, error=f"unsupported AI connector kind: {connector.get('kind')}")
    argv = connector.get("argv") or []
    if not argv:
        return _failure(request=request, connector=connector, error="configured command argv is empty")

    input_mode = connector.get("input_mode") or "stdin-prompt"
    output_mode = connector.get("output_mode") or "stdout-json-or-text"
    timeout_seconds = int(connector.get("timeout_seconds") or 120)
    start = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="dojo-task-") as tmpdir:
            env = os.environ.copy()
            request_file_path = None
            if input_mode == "request-json-file":
                request_file_path = Path(tmpdir) / "request.json"
                env["DOJO_TASK_REQUEST_FILE"] = str(request_file_path)
            stdin_text = _stdin_for_mode(input_mode, request, request_file_path)
            completed = subprocess.run(argv, input=stdin_text, text=True, capture_output=True, timeout=timeout_seconds, env=env, check=False)
        duration = time.monotonic() - start
        parse_status, parsed, warning = _parse_stdout(completed.stdout)
        status = "ok" if completed.returncode == 0 else "failed"
        return CommandConnectorResult(
            status=status,
            connector_name=connector["name"],
            input_mode=input_mode,
            output_mode=output_mode,
            request=request,
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            stderr_tail=completed.stderr[-STDERR_TAIL_CHARS:],
            exit_code=completed.returncode,
            duration_seconds=duration,
            parse_status=parse_status,
            parsed_stdout=parsed,
            parse_warning=warning,
            error=None if status == "ok" else f"command exited with code {completed.returncode}",
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        raw_stdout = _text(exc.stdout)
        raw_stderr = _text(exc.stderr)
        return CommandConnectorResult(
            status="timeout",
            connector_name=connector["name"],
            input_mode=input_mode,
            output_mode=output_mode,
            request=request,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            stderr_tail=raw_stderr[-STDERR_TAIL_CHARS:],
            exit_code=None,
            duration_seconds=duration,
            parse_status="not-run",
            error=f"command timed out after {timeout_seconds}s",
        )
    except (OSError, ValueError) as exc:
        return _failure(request=request, connector=connector, error=str(exc), duration_seconds=time.monotonic() - start)
