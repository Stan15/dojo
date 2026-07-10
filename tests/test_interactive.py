"""Interactive layer tests (owner directive 2026-07-08): humans get flows,
agents get envelopes, and the two can never bleed into each other.

The load-bearing guarantee: with --json (or piped/--no-input), NO command can
ever reach an interactive prompt — pinned by patching the single input
chokepoint to explode. The flows themselves are driven with scripted input and
a scripted fulfiller: no models, fully deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo import interactive
from dojo.api import DojoAPI
from dojo.cli import main
from dojo.schemas import Exercise


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def scripted_fulfiller(tmp_path: Path, payload: dict) -> str:
    script = tmp_path / "fulfiller.py"
    script.write_text(
        "import sys\nsys.stdin.read()\n" f"print({json.dumps(payload)!r})\n",
        encoding="utf-8",
    )
    return f"python {script}"


class TestAgentPathNeverBlocks:
    """The iron rule: the agent path must be structurally unable to prompt."""

    @pytest.mark.parametrize("argv", [
        ["daily"],
        ["capture", "some fact", "--why", "reasons"],
        ["inbox"],
        ["campaign", "plan", "learn knots"],
        ["learn", "tie", "better", "knots"],
        ["more"],
        ["stats"],
    ])
    def test_json_mode_never_touches_input(self, tmp_path: Path, argv, capsys):
        def explode(prompt):  # pragma: no cover - failure path
            raise AssertionError(f"agent path reached interactive input: {prompt!r}")

        api = DojoAPI(tmp_path)
        api.create_campaign(name="Knots", topic_path="knots", mission="Tie them.")
        with patch.object(interactive, "_input", explode):
            rc = main(["--db", str(tmp_path), "--json", *argv])
        assert rc == 0
        json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    def test_tripwire_fails_loudly_without_a_terminal(self):
        """Defense in depth: even if a flow slipped through, a piped agent gets
        an instant error, never a hang."""
        with pytest.raises(RuntimeError, match="--json"):
            interactive._input("would block> ")


class TestHumanFlows:
    def test_daily_flow_drives_a_full_session(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Vocab", topic_path="vocab", mission="Retain words.")["id"]
        # same answer for both: the packet chooses its own presentation order
        for i, q in enumerate(["dog = chien? oui/non", "chat = cat? oui/non"]):
            api.store.exercises.save(cid, Exercise(
                id=f"ex_{i}", topic_path="vocab.core", difficulty="beginner",
                answer="oui", prompt=q,
            ))
        answers = iter(["oui", "oui"])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            rc = interactive.daily_flow(api)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Session complete" in out and "✓ correct" in out
        attempts = api.store.attempts.list(cid)
        assert len(attempts) == 2 and all(a.score == 1.0 for a in attempts)

    def test_free_form_grades_settle_in_one_batch_at_the_end(self, tmp_path: Path, capsys):
        """Use-case audit D1: no model stall between questions."""
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Fr", topic_path="fr", mission="Speak.")["id"]
        for i in range(2):
            api.store.exercises.save(cid, Exercise(
                id=f"ex_{i}", topic_path="fr.oral", difficulty="beginner",
                answer=f"la réponse {i}", rubric="- close enough", prompt=f"Q{i}?",
            ))
        grade = {"score": 0.7, "evidence": "près de", "feedback": "Close; mind the article.",
                 "error_tag": None}
        api.store.configs.set_value(
            "fulfiller.command",
            scripted_fulfiller(tmp_path, grade),
        )
        answers = iter(["près de zéro", "près de un"])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            interactive.daily_flow(api)
        out = capsys.readouterr().out
        assert out.count("recorded — scoring at the end") == 2, "no mid-session stalls"
        assert "Scoring 2 answer(s)" in out
        assert all(a.grader == "ai" and a.score == 0.7 for a in api.store.attempts.list(cid))

    def test_learn_flow_extends_on_a_confirmed_near_fit(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Fr", topic_path="fr", mission="Speak French.")["id"]
        route = {"action": "new_topic", "campaign": cid, "topic_path": "fr.writing",
                 "new_name": None, "new_mission": None, "confidence": "high",
                 "reason": "fits the French campaign", "seed": False}
        api.store.configs.set_value("fulfiller.command", scripted_fulfiller(tmp_path, route))
        with patch.object(interactive, "_input", lambda prompt: "y"):
            rc = interactive.learn_flow(
                api, goal="write formal French emails",
                plan_conversation=lambda **kw: pytest.fail("extend must not re-plan"),
            )
        assert rc == 0
        assert "plan extended" in capsys.readouterr().out
        camp = api.store.campaigns.get(cid)
        assert camp.attack_plan[-1].topics == ["fr.writing"]

    def test_capture_flow_confirms_and_files(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Git", topic_path="git", mission="Archaeology.")["id"]
        camp = api.store.campaigns.get(cid)
        camp.topics = [{"path": "git.log", "kind": "recall", "summary": ""}]
        api.store.campaigns.save(camp)

        route = {"action": "attach", "campaign": cid, "topic_path": "git.log",
                 "new_name": None, "new_mission": None, "confidence": "high",
                 "reason": "log fact", "seed": False}
        api.store.configs.set_value("fulfiller.command", scripted_fulfiller(tmp_path, route))
        with patch.object(interactive, "_input", lambda prompt: "y"):
            rc = interactive.capture_flow(
                api, text="log -S counts occurrences", why="archaeology",
                locator="https://blog.example/pickaxe",
            )
        assert rc == 0
        caps = api.store.captures.list()
        assert caps[0].status == "filed"
        source = api.store.sources.get(caps[0].source_id)
        assert source.path == "https://blog.example/pickaxe", "locator provenance survives filing"


class TestWhyForHumans:
    """Owner field report (2026-07-09): interactive daily consumes the session,
    so `dojo why` had no answer the moment curiosity peaks. Now: /why inline
    during practice, and `why` falls back to the most recent completed session."""

    def test_why_falls_back_to_the_completed_session(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Vocab", topic_path="v", mission="Words.")["id"]
        api.store.exercises.save(cid, Exercise(
            id="ex_1", topic_path="v.core", difficulty="beginner",
            answer="oui", prompt="dire oui?"))
        answers = iter(["oui"])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            interactive.daily_flow(api)
        res = api.why()
        assert res["session_status"] == "completed"
        assert res["items"] and "reason" in res["items"][0]

    def test_slash_why_answers_inline_and_keeps_the_question_open(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Vocab", topic_path="v", mission="Words.")["id"]
        api.store.exercises.save(cid, Exercise(
            id="ex_1", topic_path="v.core", difficulty="beginner",
            answer="oui", prompt="dire oui?"))
        answers = iter(["/why", "oui"])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            interactive.daily_flow(api)
        out = capsys.readouterr().out
        assert "never practiced" in out or "due" in out, "the reason printed inline"
        attempts = api.store.attempts.list(cid)
        assert len(attempts) == 1 and attempts[0].user_answer == "oui", \
            "/why consumed nothing; the real answer still landed"


class TestEmptyInputIsNeverDestructive:
    """Owner ruling (2026-07-09, option A): an accidental Enter re-asks a
    refinement question with a hint; '-' is the deliberate skip. Empty input
    never advances, submits, or discards — anywhere."""

    def _plan_api(self, tmp_path: Path) -> DojoAPI:
        api = DojoAPI(tmp_path)
        proposal = {
            "mission": "Tie the six knots that cover 95% of situations.",
            "topics": [{"path": "knots.core", "kind": "skill", "summary": "the six"}],
            "phases": [{"phase": 1, "topics": ["knots.core"],
                        "criteria": {"min_attempts": 5, "min_accuracy": 0.6},
                        "focus": "calibration"}],
            "refinement_questions": ["Boating, climbing, or general use?"],
        }
        api.store.configs.set_value("model.command", scripted_fulfiller(tmp_path, proposal))
        return api

    def run_plan_flow(self, api, answers):
        it = iter(answers)
        from dojo.cli import _emit_plan_task, _materialize_core
        with patch.object(interactive, "_input", lambda prompt: next(it)):
            interactive.plan_flow(
                api, goal="learn knots", level=None, context=None,
                emit_plan_task=lambda g, n: _emit_plan_task(api.store, g, n),
                materialize=lambda tid: _materialize_core(api, tid, None),
            )

    def test_accidental_enter_reasks_and_dash_skips(self, tmp_path: Path, capsys):
        api = self._plan_api(tmp_path)
        # empty (accident) → hint + re-ask → '-' (deliberate skip) → decline create
        self.run_plan_flow(api, ["", "-", "n"])
        out = capsys.readouterr().out
        assert "'-' to skip this question" in out, "the accidental Enter got a hint"
        assert not api.store.campaigns.list(), "declined — nothing created"

    def test_real_answer_after_accidental_enter_still_lands(self, tmp_path: Path):
        api = self._plan_api(tmp_path)
        # empty (accident) → real answer → re-plan drains → decline both creates
        self.run_plan_flow(api, ["", "climbing mostly", "n"])
        replans = [t for t in api.store.tasks.list() if t.kind == "campaign.plan"]
        assert len(replans) == 2, "the answer triggered the re-plan"
        assert "climbing mostly" in replans[-1].prompt or "climbing mostly" in replans[0].prompt
