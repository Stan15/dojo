"""SKILL.md is the agent-facing surface and a context-economy invariant (I6):
it rides in every driving conversation, so its size is budgeted and its
content must track the real command surface — a stale skill misleads every
agent that loads it."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent / "src" / "dojo" / "skills" / "SKILL.md"


def body_lines() -> list[str]:
    text = SKILL.read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    return [l for l in body.splitlines() if l.strip()]


def test_skill_fits_its_context_budget():
    assert len(body_lines()) <= 60, (
        f"SKILL.md body is {len(body_lines())} non-empty lines; the budget is 60 (I6). "
        "Cut before adding — every line taxes every conversation."
    )


def test_skill_teaches_the_task_protocol_and_core_verbs():
    text = SKILL.read_text(encoding="utf-8")
    for needle in (
        "task show", "task submit", "--json", "dojo daily", "dojo why",
        "campaign plan", "--from-task", "dojo capture", "inbox confirm",
        "topic-boost", "campaign boost", "skip --reason", "dojo reflect",
    ):
        assert needle in text, f"SKILL.md no longer mentions {needle!r}"


def test_every_dojo_command_in_skill_exists():
    """Anti-staleness: each `dojo <verb>` the skill names must be a real
    command — the deleted-architecture skill must never come back."""
    text = SKILL.read_text(encoding="utf-8")
    verbs = set(re.findall(r"`?dojo ([a-z-]+)", text))
    help_out = subprocess.run(
        [sys.executable, "-m", "dojo.cli", "--help"],
        capture_output=True, text=True,
    ).stdout
    for verb in verbs:
        assert verb in help_out, f"SKILL.md references nonexistent command: dojo {verb}"
