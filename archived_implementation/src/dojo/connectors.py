from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from . import db
from . import logger

try:
    import termios
except ImportError:
    termios = None

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

    # Try direct JSON parsing first
    try:
        return "json", json.loads(stripped), None
    except json.JSONDecodeError:
        pass

    # Try finding JSON within markdown code blocks or text
    import re
    pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    match = pattern.search(stripped)
    if match:
        try:
            return "json", json.loads(match.group(1).strip()), None
        except json.JSONDecodeError:
            pass

    # Fallback: find the first '{' and last '}'
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace:last_brace+1]
        try:
            return "json", json.loads(candidate), None
        except json.JSONDecodeError as exc:
            return "text", None, f"stdout was not JSON: {exc.msg}"

    return "text", None, "stdout was not JSON"


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


# Log parsing/tailing helpers deleted


class ProgressManager:
    def __init__(self, tty_enabled: bool, stream_enabled: bool, task_name: str):
        self.tty_enabled = tty_enabled
        self.enabled = tty_enabled or stream_enabled
        self.task_name = task_name
        self.cycle_thread = None
        self.cycle_stop_event = threading.Event()
        self.status = None
        self.old_termios = None

        # Claude-style semi-humoric, context-aware phrases without ellipses
        if "campaign" in task_name:
            self.phrases = [
                "Consulting the silicon oracle",
                "Scaffolding your future brain states",
                "Interleaving concepts for maximum retention",
                "Curating the finest pedagogical path",
                "Architecting the knowledge graph",
                "Polishing the learning curve",
            ]
        elif "exercise" in task_name or "generate" in task_name:
            self.phrases = [
                "Brewing custom practice challenges",
                "Calibrating ZPD difficulty knobs",
                "Drafting slightly-above-average hints",
                "Generating cognitive friction",
                "Polishing the feedback loop",
            ]
        elif "consolidate" in task_name or "profile" in task_name:
            self.phrases = [
                "Calculating retention decay curves",
                "Hunting down your memory weak spots",
                "Consulting Ebbinghaus's ghost",
                "Updating your mental map",
                "Consolidating memory traces",
            ]
        else:
            self.phrases = [
                "Consulting the silicon oracle",
                "Reticulating pedagogical splines",
                "Contacting the learning engine",
                "Doing the heavy thinking",
            ]

        if self.enabled:
            if self.tty_enabled:
                try:
                    from rich.console import Console
                    self.console = Console(stderr=True)
                    self.status = self.console.status(f"[bold green]{self.phrases[0]}[/]")
                    self.status.start()
                except Exception:
                    self.tty_enabled = False

            if not self.tty_enabled:
                sys.stderr.write(f"\r\x1b[K{self.phrases[0]}")
                sys.stderr.flush()

            self.start_cycling()

    def update(self, text: str) -> None:
        if not self.enabled:
            return
        if self.tty_enabled and self.status:
            self.status.update(text)
        else:
            sys.stderr.write(f"\r\x1b[K{text}")
            sys.stderr.flush()

    def start_cycling(self) -> None:
        self.cycle_stop_event.clear()

        # Hide cursor and disable terminal echo / line buffering during LLM execution
        if self.tty_enabled:
            sys.stderr.write("\x1b[?25l")
            sys.stderr.flush()

            if termios and sys.stdin.isatty():
                try:
                    fd = sys.stdin.fileno()
                    self.old_termios = termios.tcgetattr(fd)
                    new_termios = termios.tcgetattr(fd)
                    new_termios[3] = new_termios[3] & ~termios.ECHO & ~termios.ICANON
                    termios.tcsetattr(fd, termios.TCSANOW, new_termios)
                except Exception:
                    self.old_termios = None

        def cycle_worker():
            import random
            last_phrase = self.phrases[0]
            phrase = self.phrases[0]
            dots = 0
            while not self.cycle_stop_event.is_set():
                # Every 8 iterations (4 seconds), change phrase
                if dots > 0 and dots % 8 == 0:
                    if len(self.phrases) > 1:
                        choices = [p for p in self.phrases if p != last_phrase]
                        phrase = random.choice(choices)
                    else:
                        phrase = self.phrases[0]
                    last_phrase = phrase

                num_dots = (dots % 3) + 1
                dot_str = "." * num_dots
                if self.tty_enabled:
                    display_text = f"[bold green]{phrase}[/][bold cyan]{dot_str}[/]"
                else:
                    display_text = f"{phrase}{dot_str}"

                self.update(display_text)
                dots += 1

                # Sleep in 100ms chunks to respond quickly to stop event
                for _ in range(5):
                    time.sleep(0.1)
                    if self.cycle_stop_event.is_set():
                        return

        self.cycle_thread = threading.Thread(target=cycle_worker, daemon=True)
        self.cycle_thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self.cycle_stop_event.set()
        if self.cycle_thread:
            try:
                self.cycle_thread.join(timeout=0.1)
            except Exception:
                pass
            self.cycle_thread = None

        # Show cursor and restore terminal settings
        if self.tty_enabled:
            sys.stderr.write("\x1b[?25h")
            sys.stderr.flush()

            if self.old_termios and termios and sys.stdin.isatty():
                try:
                    fd = sys.stdin.fileno()
                    termios.tcsetattr(fd, termios.TCSANOW, self.old_termios)
                    termios.tcflush(sys.stdin, termios.TCIFLUSH)
                except Exception:
                    pass
                self.old_termios = None

        if self.tty_enabled and self.status:
            self.status.stop()
        else:
            sys.stderr.write("\r\x1b[K")
            sys.stderr.flush()


def invoke_command_connector(db_path: str | Path | None, request: dict[str, Any], *, connector_name: str | None = None) -> CommandConnectorResult:
    log = logger.get_logger(db_path, "connectors")
    task = request.get("task", "unknown")
    connector = _resolve_connector(db_path, connector_name)
    if connector is None:
        name = f"AI connector {connector_name!r}" if connector_name else "no default AI connector"
        err_msg = f"{name} configured"
        log.warning(f"Failed to resolve connector for task '{task}': {err_msg}")
        return _failure(request=request, error=err_msg)

    conn_name = connector.get("name", "unknown")
    if connector.get("kind") != "command":
        err_msg = f"unsupported AI connector kind: {connector.get('kind')}"
        log.warning(f"Connector '{conn_name}' error for task '{task}': {err_msg}")
        return _failure(request=request, connector=connector, error=err_msg)

    argv = connector.get("argv") or []
    if not argv:
        err_msg = "configured command argv is empty"
        log.warning(f"Connector '{conn_name}' error for task '{task}': {err_msg}")
        return _failure(request=request, connector=connector, error=err_msg)

    input_mode = connector.get("input_mode") or "stdin-prompt"
    output_mode = connector.get("output_mode") or "stdout-json-or-text"
    timeout_seconds = int(connector.get("timeout_seconds") or 120)

    log.info(f"Invoking connector '{conn_name}' for task '{task}' (mode={input_mode}, argv={argv})")
    start = time.monotonic()

    stream_updates = (os.environ.get("DOJO_STREAM_UPDATES") == "1") or ("--verbose" in sys.argv) or ("-v" in sys.argv)
    is_json_mode = "--json" in sys.argv
    tty_enabled = sys.stderr.isatty() and not is_json_mode and not stream_updates

    progress = ProgressManager(tty_enabled, stream_updates, task)

    try:
        try:
            with tempfile.TemporaryDirectory(prefix="dojo-task-") as tmpdir:
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                request_file_path = None
                if input_mode == "request-json-file":
                    request_file_path = Path(tmpdir) / "request.json"
                    env["DOJO_TASK_REQUEST_FILE"] = str(request_file_path)
                stdin_text = _stdin_for_mode(input_mode, request, request_file_path)

                proc = subprocess.Popen(
                    argv,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    bufsize=0,
                )

                stdout_chunks = []
                stderr_chunks = []

                def read_stdout():
                    try:
                        while True:
                            chunk = proc.stdout.read(1024)
                            if not chunk:
                                break
                            stdout_chunks.append(chunk)
                    except Exception:
                        pass
                    finally:
                        proc.stdout.close()

                def read_stderr():
                    try:
                        while True:
                            char_bytes = proc.stderr.read(1)
                            if not char_bytes:
                                break
                            stderr_chunks.append(char_bytes)

                            if not tty_enabled or stream_updates:
                                sys.stderr.write(char_bytes.decode("utf-8", errors="replace"))
                                sys.stderr.flush()
                    except Exception:
                        pass
                    finally:
                        proc.stderr.close()

                t_stdout = threading.Thread(target=read_stdout, daemon=True)
                t_stderr = threading.Thread(target=read_stderr, daemon=True)
                t_stdout.start()
                t_stderr.start()

                if stdin_text is not None:
                    try:
                        proc.stdin.write(stdin_text.encode("utf-8"))
                    except (OSError, ValueError):
                        pass
                try:
                    proc.stdin.close()
                except (OSError, ValueError):
                    pass

                try:
                    exit_code = proc.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        pass
                    t_stdout.join(timeout=2)
                    t_stderr.join(timeout=2)

                    stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                    stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")
                    raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_seconds, output=stdout_str, stderr=stderr_str)

                t_stdout.join()
                t_stderr.join()

                stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")

        finally:
            progress.stop()

        duration = time.monotonic() - start
        parse_status, parsed, warning = _parse_stdout(stdout_str)
        status = "ok" if exit_code == 0 else "failed"

        if status == "ok":
            log.info(f"Connector '{conn_name}' call for task '{task}' succeeded in {duration:.3f}s (parse={parse_status})")
        else:
            stderr_snippet = stderr_str[-200:].strip().replace('\n', ' ')
            log.error(f"Connector '{conn_name}' call for task '{task}' failed with exit code {exit_code} in {duration:.3f}s. Stderr tail: {stderr_snippet}")

        return CommandConnectorResult(
            status=status,
            connector_name=connector["name"],
            input_mode=input_mode,
            output_mode=output_mode,
            request=request,
            raw_stdout=stdout_str,
            raw_stderr=stderr_str,
            stderr_tail=stderr_str[-STDERR_TAIL_CHARS:],
            exit_code=exit_code,
            duration_seconds=duration,
            parse_status=parse_status,
            parsed_stdout=parsed,
            parse_warning=warning,
            error=None if status == "ok" else f"command exited with code {exit_code}",
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        raw_stdout = _text(exc.stdout)
        raw_stderr = _text(exc.stderr)
        stderr_snippet = raw_stderr[-200:].strip().replace('\n', ' ')
        log.error(f"Connector '{conn_name}' call for task '{task}' timed out after {timeout_seconds}s. Stderr tail: {stderr_snippet}")
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
        duration = time.monotonic() - start
        log.exception(f"Connector '{conn_name}' call for task '{task}' encountered system error: {exc}")
        return _failure(request=request, connector=connector, error=str(exc), duration_seconds=duration)
