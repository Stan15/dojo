#!/usr/bin/env python3
"""README weak-model insights-demo retry (QUESTIONS board standing item).

Recreates the seeded Spanish week from the README demo section and drives
the PRODUCTION reflect pipeline (compile -> emit -> model -> submit, full
task submission budget = one production budget). Bound: <= 2 budgets per
model. Usage:

  python readme_demo_retry.py "<model command>" [budgets]

Prints, per budget: every submission's ok/errors, and on success the
resulting insights exactly as `dojo insights` would show them.
"""
from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))  # repo root src if copied there
sys.path.insert(0, "src")

from dojo.schemas import Attempt, Campaign, Exercise  # noqa: E402
from dojo.store import DojoStore  # noqa: E402
from dojo.tasks import compiler, service  # noqa: E402

CAMP = "conversational-spanish"


def seed(root: Path) -> DojoStore:
    s = DojoStore(root)
    s.campaigns.save(Campaign(
        id=CAMP, name="Conversational Spanish",
        mission="Hold everyday Spanish conversations with confidence.",
        strategy_profile={"difficulty": "beginner", "scaffolding": "medium"},
    ))
    exs = [
        Exercise(id="ex_1", topic_path="spanish.grammar.ser_estar", difficulty="beginner",
                 prompt='Translate: "I am tired today."',
                 answer="Estoy cansado hoy.", rubric="- estar for temporary state"),
        Exercise(id="ex_2", topic_path="spanish.grammar.ser_estar", difficulty="beginner",
                 prompt='Translate: "My sister is sick this week."',
                 answer="Mi hermana está enferma esta semana.", rubric="- estar for a condition"),
        Exercise(id="ex_3", topic_path="spanish.grammar.ser_estar", difficulty="beginner",
                 prompt='Ser or estar? "La sopa ___ fría." Say the sentence and why.',
                 answer="La sopa está fría — a temporary state.", rubric="- estar, temporary"),
        Exercise(id="ex_4", topic_path="spanish.grammar.subjunctive", difficulty="beginner",
                 prompt="Complete: Espero que tú ___ (venir) mañana.",
                 answer="vengas", rubric="- subjunctive after espero que"),
        Exercise(id="ex_5", topic_path="spanish.grammar.subjunctive", difficulty="beginner",
                 prompt="Which mood follows 'ojalá', and why?",
                 answer="Subjunctive — it expresses a wish.", rubric="- subjunctive for wishes"),
        Exercise(id="ex_6", topic_path="spanish.vocab.restaurant", difficulty="beginner",
                 prompt='Say it in Spanish: "the check, please".',
                 answer="La cuenta, por favor.", rubric="- la cuenta"),
    ]
    for ex in exs:
        s.exercises.save(CAMP, ex)
    rows = [
        ("att_1", "ex_1", 0.3, 20.0, "ser estar mixup", "Yo soy cansado hoy", None, "ai"),
        ("att_2", "ex_2", 0.3, 25.0, "ser estar mixup", "Mi hermana es enferma esta semana", None, "ai"),
        ("att_3", "ex_3", 0.3, 30.0, "ser estar mixup",
         "es fria? because the soup is cold right now I think", None, "ai"),
        ("att_4", "ex_4", 0.0, 12.0, None, "", "too_hard", None),
        ("att_5", "ex_5", 0.0, 40.0, None, "no idea, I give up on this one", None, "ai"),
        ("att_6", "ex_6", 1.0, 8.0, None, "La cuenta, por favor", None, "ai"),
    ]
    for aid, exid, score, lat, tag, ans, skip, grader in rows:
        s.attempts.save(CAMP, Attempt(
            id=aid, session_id="s1", exercise_id=exid, campaign_id=CAMP,
            score=score, latency_seconds=lat, error_tag=tag,
            user_answer=ans, skip_reason=skip, grader=grader,
        ))
    return s


def one_budget(model_cmd: str, tag: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        s = seed(Path(td) / "store")
        camp = s.campaigns.get(CAMP)
        compiled = compiler.compile_reflect(s, camp)
        task = service.emit(s, compiled)
        while True:
            proc = subprocess.run(
                shlex.split(model_cmd), input=task.prompt,
                capture_output=True, text=True, timeout=600,
            )
            outcome = service.submit(s, task.id, proc.stdout)
            fresh = s.tasks.get(task.id)
            print(f"  [{tag}] submit {fresh.submissions}/{fresh.max_submissions}: "
                  f"ok={outcome.ok} status={outcome.status} errors={outcome.errors[:2]}")
            if outcome.ok:
                print(f"  [{tag}] RAW ACCEPTED OUTPUT:\n{proc.stdout.strip()[:2000]}")
                for ins in s.insights.list(CAMP):
                    print(f"    insight {ins.id} {ins.key}: {ins.description}")
                return True
            if outcome.status != "pending":
                return False


def main() -> int:
    model_cmd = sys.argv[1]
    budgets = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    wins = 0
    for b in range(budgets):
        print(f"budget {b + 1}/{budgets} — {model_cmd}")
        wins += one_budget(model_cmd, f"b{b + 1}")
    print(f"RESULT: {wins}/{budgets} budgets landed a valid reflect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
