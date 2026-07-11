"""The benchmark live-stream observer (owner ask 2026-07-11): with an
observer set, run_command reads incrementally and mirrors chunks in real
time; output, error, and timeout semantics stay identical to the blocking
path. No models — scripted subprocesses only.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from dojo.evals.runner import run_command, set_stream_observer


@pytest.fixture(autouse=True)
def _always_clear_observer():
    yield
    set_stream_observer(None)


def _script(body: str) -> str:
    return f"{sys.executable} -u -c \"{body}\""


class TestStreamingRunCommand:
    def test_chunks_reach_observer_and_output_is_identical(self):
        body = (
            "import sys,time;"
            "sys.stdin.read();"
            "print('thinking about it...', flush=True);"
            "time.sleep(0.05);"
            "print('{\\\\\"ok\\\\\": true}', flush=True)"
        )
        cmd = _script(body)
        plain = run_command(cmd, "prompt", timeout=10)

        events = []
        set_stream_observer(events.append)
        streamed = run_command(cmd, "prompt", timeout=10)

        assert streamed == plain
        assert events[0]["kind"] == "call_start"
        chunks = [e["text"] for e in events if e["kind"] == "chunk"]
        assert "".join(chunks) == streamed
        assert len(chunks) >= 2, "output arrived incrementally, not as one blob"

    def test_nonzero_exit_raises_with_stderr(self):
        set_stream_observer(lambda e: None)
        with pytest.raises(RuntimeError, match="boom"):
            run_command(
                _script("import sys; sys.stdin.read(); sys.stderr.write('boom'); sys.exit(3)"),
                "prompt", timeout=10,
            )

    def test_timeout_still_raises_timeout_expired(self):
        set_stream_observer(lambda e: None)
        with pytest.raises(subprocess.TimeoutExpired):
            run_command(
                _script("import sys,time; sys.stdin.read(); time.sleep(30)"),
                "prompt", timeout=1,
            )
