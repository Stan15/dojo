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
            "name": "Essential Knots",
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
        assert "'-' to skip" in out, "the accidental Enter got a hint"
        assert not api.store.campaigns.list(), "declined — nothing created"

    def test_real_answer_after_accidental_enter_still_lands(self, tmp_path: Path):
        api = self._plan_api(tmp_path)
        # empty (accident) → real answer → re-plan drains → decline both creates
        self.run_plan_flow(api, ["", "climbing mostly", "n"])
        replans = [t for t in api.store.tasks.list() if t.kind == "campaign.plan"]
        assert len(replans) == 2, "the answer triggered the re-plan"
        assert "climbing mostly" in replans[-1].prompt or "climbing mostly" in replans[0].prompt


class TestRefinementBack:
    """Owner field report 2026-07-17: '/back' typed at a refinement question
    was shipped to the model as the literal answer — and there was no way to
    revisit an earlier question at all."""

    def _plan_api(self, tmp_path: Path, questions: list[str]) -> DojoAPI:
        api = DojoAPI(tmp_path)
        proposal = {
            "mission": "Cook affordable meals reliably.",
            "name": "Home Cooking",
            "topics": [{"path": "cooking.rice", "kind": "skill", "summary": "doneness"}],
            "phases": [{"topics": ["cooking.rice"],
                        "criteria": {"min_attempts": 5, "min_accuracy": 0.0},
                        "focus": "calibration"}],
            "refinement_questions": questions,
        }
        api.store.configs.set_value("model.command", scripted_fulfiller(tmp_path, proposal))
        return api

    def _run(self, api, answers):
        it = iter(answers)
        from dojo.cli import _emit_plan_task, _materialize_core
        with patch.object(interactive, "_input", lambda prompt: next(it)):
            interactive.plan_flow(
                api, goal="learn to cook", level=None, context=None,
                emit_plan_task=lambda g, n: _emit_plan_task(api.store, g, n),
                materialize=lambda tid: _materialize_core(api, tid, None),
            )

    def test_back_revisits_and_the_control_token_never_reaches_the_model(
        self, tmp_path: Path, capsys
    ):
        api = self._plan_api(tmp_path, ["What cuisine?", "When does it matter?"])
        # q1 'paris' → q2 '/back' → q1 again (replaces with 'tokyo') → q2 → decline
        self._run(api, ["paris", "/back", "tokyo", "weekly", "n"])
        out = capsys.readouterr().out
        assert "previously: paris" in out, "revisiting shows the answer being replaced"
        replans = [t for t in api.store.tasks.list() if t.kind == "campaign.plan"]
        assert len(replans) == 2, "the answers triggered exactly one re-plan"
        assert all("/back" not in t.prompt for t in replans), "control tokens are never answers"
        assert any("tokyo" in t.prompt and "weekly" in t.prompt for t in replans)
        assert all("paris" not in t.prompt for t in replans), "the replaced answer is gone"

    def test_back_at_the_first_question_reasks(self, tmp_path: Path, capsys):
        api = self._plan_api(tmp_path, ["What cuisine?"])
        self._run(api, ["/back", "-", "n"])
        out = capsys.readouterr().out
        assert "first question" in out
        replans = [t for t in api.store.tasks.list() if t.kind == "campaign.plan"]
        assert len(replans) == 1, "everything skipped — no re-plan"


class TestDrainUsesTheSubmissionBudget:
    """Owner field report 2026-07-17: one rejected submission killed the whole
    learn flow with two retries unspent, no reason a human could act on, and
    no next step."""

    GOOD = {
        "mission": "Cook affordable meals reliably.",
        "name": "Home Cooking",
        "topics": [{"path": "cooking.rice", "kind": "skill", "summary": "doneness"}],
        "phases": [{"topics": ["cooking.rice"],
                    "criteria": {"min_attempts": 5, "min_accuracy": 0.0}}],
        "refinement_questions": [],
    }
    # The exact field crash: phase criteria missing min_accuracy.
    BAD = {**GOOD, "phases": [{"topics": ["cooking.rice"], "criteria": {"min_attempts": 5}}]}

    def _flaky_fulfiller(self, tmp_path: Path) -> str:
        """Rejects on the first call, succeeds on the second — sampling noise."""
        marker = tmp_path / "tried_once"
        script = tmp_path / "flaky.py"
        script.write_text(
            "import sys, os, json\n"
            "sys.stdin.read()\n"
            f"marker = {str(marker)!r}\n"
            "if os.path.exists(marker):\n"
            f"    print({json.dumps(self.GOOD)!r})\n"
            "else:\n"
            "    open(marker, 'w').close()\n"
            f"    print({json.dumps(self.BAD)!r})\n",
            encoding="utf-8",
        )
        return f"python {script}"

    def _plan_ref(self, api) -> dict:
        from dojo.cli import _emit_plan_task
        return _emit_plan_task(api.store, "learn to cook", "")

    def test_a_rejection_is_retried_within_the_budget(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        api.store.configs.set_value("model.command", self._flaky_fulfiller(tmp_path))
        ref = self._plan_ref(api)
        assert interactive.drain_tasks(api, [ref]) is True
        out = capsys.readouterr().out
        assert "retrying" in out
        task = api.store.tasks.get(ref["id"])
        assert task.status == "fulfilled" and task.submissions == 2

    def test_exhausted_budget_fails_with_reason_and_next_step(self, tmp_path: Path, capsys):
        api = DojoAPI(tmp_path)
        api.store.configs.set_value("model.command", scripted_fulfiller(tmp_path, self.BAD))
        ref = self._plan_ref(api)
        assert interactive.drain_tasks(api, [ref]) is False
        out = capsys.readouterr().out
        task = api.store.tasks.get(ref["id"])
        assert task.status == "failed" and task.submissions == task.max_submissions
        assert "phases[0].criteria.min_accuracy" in out, "the precise reason, human-readable"
        assert f"dojo task show {ref['id']} --trace" in out, "a next step, not a dead end"


class TestPlanCreatedCampaignStartsInCalibration:
    """Owner field report 2026-07-17: 'Start practicing it now?' → 'Nothing to
    practice yet.' A plan-created campaign was never recognized as being in
    calibration: its first generation compiled as ungated practice items that
    landed as candidates, invisible to the session builder."""

    PROPOSAL = {
        "mission": "Cook affordable meals reliably.",
        "name": "Home Cooking",
        "topics": [
            {"path": "cooking.rice", "kind": "skill", "summary": "doneness"},
            {"path": "cooking.safety", "kind": "recall", "summary": "storage"},
        ],
        "phases": [
            {"topics": ["cooking.rice"],
             "criteria": {"min_attempts": 5, "min_accuracy": 0.6},  # normalizer zeroes this
             "focus": "calibration"},
            {"topics": ["cooking.rice", "cooking.safety"],
             "criteria": {"min_attempts": 8, "min_accuracy": 0.7}},
        ],
        "refinement_questions": [],
    }

    def _materialized(self, tmp_path: Path) -> tuple[DojoAPI, str]:
        import json as _json
        from dojo.cli import _emit_plan_task, _materialize_core
        from dojo.tasks import service as task_service
        api = DojoAPI(tmp_path)
        ref = _emit_plan_task(api.store, "learn to cook", "")
        outcome = task_service.submit(api.store, ref["id"], _json.dumps(self.PROPOSAL))
        assert outcome.ok, outcome.errors
        return api, _materialize_core(api, ref["id"], None)["id"]

    def test_materialize_stamps_diagnostic_mode_and_an_ungated_phase_one(self, tmp_path: Path):
        api, cid = self._materialized(tmp_path)
        camp = api.store.campaigns.get(cid)
        assert camp.strategy_profile["mode"] == "diagnostic", "same stamp as the direct door"
        assert camp.attack_plan[0].criteria.min_accuracy == 0.0, "normalized at the boundary"
        assert camp.attack_plan[1].criteria.min_accuracy == 0.7

    def test_materialize_uses_the_plans_generated_name_not_the_goal(self, tmp_path: Path):
        """Owner field report 2026-07-18: 'Campaign created:' showed the whole
        slugged prompt. apply_plan dropped PlanResult.name from _applied, so
        the materializer's goal fallback ALWAYS won — through the real
        emit→submit→materialize path, the AI label must reach the campaign."""
        api, cid = self._materialized(tmp_path)
        camp = api.store.campaigns.get(cid)
        assert camp.name == "Home Cooking", "the plan's name, never the raw goal"
        assert "learn to cook" not in camp.name
        assert "learn-to-cook" not in cid, "id derives from the label, not the prompt"

    def test_virgin_start_requests_calibration_not_practice(self, tmp_path: Path):
        api, cid = self._materialized(tmp_path)
        res = api.start_practice_session(campaign_id=cid, reset=True)
        assert res["session"] is None
        task = api.store.tasks.get(res["tasks"][0]["id"])
        assert task.kind == "exercise.diagnostic", (
            "no evidence at all means calibrate first — never ungated practice items"
        )

    def test_warm_start_replenishment_auto_promotes(self, tmp_path: Path):
        """Past calibration, start-path stock must be practicable immediately —
        the same recorded I2 policy daily replenishment uses (J1)."""
        from dojo.schemas import Attempt, Exercise
        api, cid = self._materialized(tmp_path)
        camp = api.store.campaigns.get(cid)
        camp.strategy_profile["mode"] = "practice"
        camp.active_phase_index = 1
        api.store.campaigns.save(camp)
        api.store.exercises.save(cid, Exercise(
            id="ex_done", topic_path="cooking.rice", difficulty="beginner",
            answer="x", prompt="old",
        ))
        api.store.attempts.save(cid, Attempt(
            id="att_1", session_id="s1", exercise_id="ex_done", campaign_id=cid,
            score=1.0, latency_seconds=5.0, user_answer="x",
        ))
        res = api.start_practice_session(campaign_id=cid, reset=True)
        gen = [api.store.tasks.get(t["id"]) for t in res.get("tasks", [])]
        gen = [t for t in gen if t.kind == "exercise.generate"]
        assert gen, "thin stock emits replenishment"
        assert gen[0].context.get("auto_promote") is True, (
            "start-path stock lands practicable, never as invisible candidates"
        )


class TestPracticeLoopCommandDiscipline:
    """Owner field reports 2026-07-17: '/exit' was submitted and scored
    '✓ correct'; a refused /back marched the counter to '5 of 2'; junk must
    never become calibration evidence (calibration measures, never grades)."""

    def _session_api(self, tmp_path: Path) -> tuple[DojoAPI, dict]:
        from dojo.schemas import PracticeSession
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Juggling", topic_path="juggling",
                                  mission="Cascade three balls.")["id"]
        for i in range(2):
            api.store.exercises.save(cid, Exercise(
                id=f"ex_d{i}", topic_path="juggling", difficulty="beginner",
                quality="diagnostic", prompt=f"diagnostic question {i}?",
            ))
        session = PracticeSession(id="sess_t", exercise_ids=["ex_d0", "ex_d1"])
        api.store.sessions.save_active(session)
        return api, session.model_dump(), cid

    def test_commands_and_junk_never_become_answers_and_the_counter_holds(
        self, tmp_path: Path, capsys
    ):
        api, session, cid = self._session_api(tmp_path)
        answers = iter([
            "/back",                    # refused (nothing before) — re-asks
            "/oops",                    # unknown command — re-asks
            "...",                      # calibration junk — refused, re-asks
            "juggled a bit as a kid",   # real response — full score, 'noted'
            "/exit",                    # alias of /quit — pauses
        ])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            interactive.practice_loop(api, session)
        out = capsys.readouterr().out
        assert "3 of 2" not in out, "re-asks must never inflate the position counter"
        assert "unknown command" in out
        assert "doesn't look like an answer" in out
        assert "noted — calibration" in out
        assert "✓ correct" not in out, "calibration never claims correctness"
        assert "Paused" in out, "/exit works like /quit"
        attempts = api.store.attempts.list(cid)
        assert len(attempts) == 1, "commands and junk recorded nothing"
        assert attempts[0].user_answer == "juggled a bit as a kid"
        assert attempts[0].score == 1.0, "a real response earns full score"


class TestBackChainsThroughHistory:
    """Owner field report 2026-07-17: repeating /back cycled between the same
    two questions — the amend-review prompt swallowed '/back' as the new
    answer. Each additional /back must reach one question further back."""

    def test_repeated_back_walks_to_earlier_answers(self, tmp_path: Path, capsys):
        from dojo.schemas import PracticeSession
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="Chem", topic_path="chem", mission="m")["id"]
        for i in range(3):
            api.store.exercises.save(cid, Exercise(
                id=f"ex_r{i}", topic_path="chem", difficulty="beginner",
                answer=f"secret{i}", rubric="- exactness", prompt=f"question {i}?",
            ))
        session = PracticeSession(id="sess_b", exercise_ids=["ex_r0", "ex_r1", "ex_r2"])
        api.store.sessions.save_active(session)
        answers = iter([
            "a0", "a1",            # two answers land (pending grades)
            "/back",               # at q3: review q2's answer
            "/back",               # chain: review q1's answer (NOT a new answer)
            "a0-fixed",            # amend the first answer
            "a2",                  # answer q3; session completes
        ])
        with patch.object(interactive, "_input", lambda prompt: next(answers)):
            interactive.practice_loop(api, session.model_dump())
        by_ex = {a.exercise_id: a for a in api.store.attempts.list(cid)}
        assert by_ex["ex_r0"].user_answer == "a0-fixed", "the chained /back reached q1"
        assert by_ex["ex_r1"].user_answer == "a1", "q2's answer stayed as it was"


class TestCampaignRename:
    """STATE 7f ride-along: paragraph-named campaigns are fixable in place —
    the id and history stay, only the label moves."""

    def test_rename_changes_label_only_and_refuses_collisions(self, tmp_path: Path):
        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="how to umm do that thing with balls",
                                  topic_path="juggling", mission="m")["id"]
        api.create_campaign(name="French", topic_path="french", mission="m2")
        res = api.rename_campaign(cid, "Juggling")
        camp = api.store.campaigns.get(cid)
        assert camp.name == "Juggling" and camp.id == cid == res["id"]
        with pytest.raises(ValueError, match="already belongs"):
            api.rename_campaign(cid, "french")  # case-insensitive collision
        with pytest.raises(ValueError, match="empty"):
            api.rename_campaign(cid, "   ")


class TestDisplayModeIsAppWide:
    """Owner directive 2026-07-17: the screen/transcript choice is one
    app-wide contract — every practice-bearing command accepts the flags."""

    @pytest.mark.parametrize("argv", [
        ["daily", "--screen"],
        ["more", "--screen"],
        ["learn", "juggle", "--screen"],
        ["more", "--transcript"],
        ["campaign", "plan", "juggle", "--screen"],
    ])
    def test_practice_commands_accept_display_flags(self, argv):
        from dojo.cli import build_parser
        args = build_parser().parse_args(argv)  # SystemExit would fail the test
        assert getattr(args, "screen", False) or getattr(args, "transcript", False)


class TestConfirmShowsItsOptions:
    """Owner field report 2026-07-17: rich parsed '[y/N]' as a markup tag and
    silently stripped it — default-no prompts showed no options at all."""

    def test_default_no_prompt_carries_visible_options(self, tmp_path: Path):
        prompts: list[str] = []

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return ""

        from rich.text import Text
        with patch.object(interactive, "_input", fake_input):
            assert interactive.confirm("Remove dojo?", default=False) is False
        rendered = Text.from_markup(prompts[0]).plain
        assert "[y/N]" in rendered, "the options must survive markup rendering"


class TestFirstSessionAfterCreate:
    """Owner field report 2026-07-13: 'Start practicing now?' right after
    campaign creation resumed an unrelated mid-flight session. The consent
    is about the NEW campaign — the first session must practice it."""

    def test_first_session_practices_the_new_campaign_not_the_stale_session(
        self, tmp_path: Path, capsys
    ):
        api = DojoAPI(tmp_path)
        # Campaign A: an in-progress session with prompts remaining.
        cid_a = api.create_campaign(name="Memory", topic_path="memory", mission="Recall.")["id"]
        for i in range(2):
            api.store.exercises.save(cid_a, Exercise(
                id=f"ex_a{i}", topic_path="memory.core", difficulty="beginner",
                answer="x", prompt=f"old question {i}",
            ))
        from dojo.schemas import PracticeSession
        api.store.sessions.save_active(PracticeSession(
            id="sess_stale", exercise_ids=["ex_a0", "ex_a1"],
        ))
        # Campaign B: freshly created, its calibration question in stock.
        cid_b = api.create_campaign(name="Arabic", topic_path="arabic", mission="Read MSA.")["id"]
        api.store.exercises.save(cid_b, Exercise(
            id="ex_diag", topic_path="arabic", difficulty="intermediate",
            quality="diagnostic", prompt="Have you seen Arabic script before?",
        ))

        with patch.object(interactive, "_input", lambda prompt: "not really"):
            rc = interactive.first_session_flow(api, cid_b)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Have you seen Arabic script before?" in out
        assert "old question" not in out, "the stale session must not resume here"
        assert "pausing your other in-progress session" in out
        assert [a.exercise_id for a in api.store.attempts.list(cid_b)] == ["ex_diag"]
        assert api.store.attempts.list(cid_a) == [], "campaign A untouched"
        active = api.store.sessions.get_active()
        assert active is None or active.id != "sess_stale"
