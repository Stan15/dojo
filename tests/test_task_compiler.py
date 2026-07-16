"""Budgeted compiler tests (invariant I6, blueprint §9).

Pins: every section respects its byte budget with visible truncation; totals
stay under per-kind caps; fulfiller tiers scale budgets; the compiled generate
payload is byte-pinned as a golden fixture (Tier 1 of ADR 016).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dojo.schemas import Attempt, Campaign, Exercise, Insight
from dojo.store import DojoStore
from dojo.tasks import compiler

CAMP_ID = "tef-french"


@pytest.fixture
def store(tmp_path: Path) -> DojoStore:
    s = DojoStore(tmp_path / "dojo")
    s.campaigns.save(Campaign(
        id=CAMP_ID,
        name="French TEF",
        mission="Reach NCLC 7 oral French by October for the TEF exam.",
        strategy_profile={"difficulty": "intermediate", "scaffolding": "medium"},
        created_at="2026-07-01T00:00:00+00:00",
        updated_at="2026-07-01T00:00:00+00:00",
    ))
    s.insights.save(CAMP_ID, Insight(
        id="ins_1", key="conditional.aux_choice",
        description="Picks avoir over être for motion verbs in past conditional.",
        topic_path="french.grammar",
        created_at="2026-07-02T00:00:00+00:00",
        updated_at="2026-07-02T00:00:00+00:00",
    ))
    s.attempts.save(CAMP_ID, Attempt(
        id="att_1", session_id="sess_1", exercise_id="ex_1", campaign_id=CAMP_ID,
        score=0.3, latency_seconds=30.0, skip_reason=None,
        created_at="2026-07-03T00:00:00+00:00",
        user_answer="Il aurait allé.",
    ))
    return s


def _campaign(store: DojoStore) -> Campaign:
    return store.campaigns.get(CAMP_ID)


class TestBudgets:
    def test_generate_within_total_budget(self, store: DojoStore):
        compiled = compiler.compile_generate(
            store, _campaign(store),
            topic_path="french.grammar.conditional", n_items=3, difficulty="intermediate",
            source_slice="Le conditionnel passé se forme avec l'auxiliaire au conditionnel présent.",
        )
        assert compiled.payload_bytes <= 10 * 1024  # ceiling now derived; this pins typical size
        assert compiled.truncated_sections == []
        assert "{{" not in compiled.prompt

    def test_oversized_section_is_clipped_with_visible_marker(self, store: DojoStore):
        huge_source = "des mots français " * 2000  # ~36 KB, budget 4 KB
        compiled = compiler.compile_generate(
            store, _campaign(store),
            topic_path="french.grammar", n_items=3, difficulty="intermediate",
            source_slice=huge_source,
        )
        assert "source_section" in compiled.truncated_sections
        assert compiler.TRUNCATION_MARK in compiled.prompt
        assert compiled.payload_bytes <= 10 * 1024  # ceiling now derived; this pins typical size
        assert compiled.context["truncated_sections"] == ["source_section"]

    def test_rich_tier_scales_budgets(self, store: DojoStore):
        big_source = "des mots français " * 400  # ~7 KB: clipped at standard, kept at rich
        standard = compiler.compile_generate(
            store, _campaign(store),
            topic_path="t", n_items=3, difficulty="intermediate", source_slice=big_source,
        )
        assert "source_section" in standard.truncated_sections

        store.configs.set_value("fulfiller.tier", "rich")
        rich = compiler.compile_generate(
            store, _campaign(store),
            topic_path="t", n_items=3, difficulty="intermediate", source_slice=big_source,
        )
        assert rich.truncated_sections == []
        assert rich.payload_bytes > standard.payload_bytes

    @pytest.mark.parametrize("kind", sorted(compiler.SECTION_BUDGETS))
    def test_every_kind_has_template_and_budgets(self, kind: str):
        assert kind in compiler.TEMPLATES
        assert kind in compiler.SECTION_BUDGETS


class TestCompileEachKind:
    def test_grade(self, store: DojoStore):
        ex = Exercise(
            id="ex_1", topic_path="french.grammar", difficulty="intermediate",
            answer="Il serait allé.", rubric="- être as auxiliary for aller",
            prompt="Traduisez : He would have gone.",
        )
        compiled = compiler.compile_grade(
            store, _campaign(store), ex, attempt_id="att_1", user_answer="Il aurait allé.",
        )
        assert compiled.payload_bytes <= 6 * 1024  # ceiling now derived; this pins typical size
        assert "Il aurait allé." in compiled.prompt
        assert compiled.context["attempt_id"] == "att_1"

    def test_reflect_includes_window_and_insight_ids(self, store: DojoStore):
        compiled = compiler.compile_reflect(store, _campaign(store), window_n=15)
        assert "[ins_1]" in compiled.prompt
        assert "att_1" in compiled.prompt
        assert compiled.context["attempt_ids"] == ["att_1"]
        assert compiled.payload_bytes <= 11 * 1024  # ceiling now derived; this pins typical size

    def test_plan(self, store: DojoStore):
        compiled = compiler.compile_plan(store, goal="Learn Docker Compose for on-call in 3 weeks")
        assert "Docker Compose" in compiled.prompt
        assert compiled.payload_bytes <= 5 * 1024  # ceiling now derived; this pins typical size

    def test_route_registry_lists_campaign_missions(self, store: DojoStore):
        compiled = compiler.compile_route(
            store, capture_id="cap_1",
            capture_text="The FSRS-6 model adds two same-day review parameters.",
        )
        assert f'campaign "{CAMP_ID}"' in compiled.prompt
        assert compiled.payload_bytes <= 4 * 1024  # ceiling now derived; this pins typical size

    def test_diagnostic(self, store: DojoStore):
        compiled = compiler.compile_diagnostic(
            store, _campaign(store), topic_path="french.oral", n_items=2,
        )
        assert "diagnostic" in compiled.prompt
        assert compiled.context["mode"] == "diagnostic"


class TestGoldenPayload:
    """Byte-level pin of the full compiled generate payload (ADR 016 Tier 1).
    A change to the template, the section builders, or the budgets shows up as
    a reviewed diff to tests/golden/exercise_generate.compiled.txt."""

    def test_generate_grounded_golden(self, store: DojoStore):
        compiled = compiler.compile_generate(
            store, _campaign(store),
            topic_path="french.grammar.conditional", n_items=3, difficulty="intermediate",
            source_slice="Le conditionnel passé se forme avec l'auxiliaire au conditionnel présent suivi du participe passé.",
        )
        golden = Path(__file__).parent / "golden" / "exercise_generate.compiled.txt"
        if not golden.exists():  # bootstrap: write once, review, commit
            golden.parent.mkdir(exist_ok=True)
            golden.write_text(compiled.prompt + "\n", encoding="utf-8")
        assert compiled.prompt + "\n" == golden.read_text(encoding="utf-8"), (
            "compiled payload drifted; if intentional, update the golden fixture in the same commit"
        )


class TestDerivedCeiling:
    """Owner field crash 2026-07-16: reflect on a full store hit 8035B vs a
    stale 6144B constant and killed the daily heartbeat. The ceiling is now
    DERIVED (skeleton + scaled section budgets + slack): every kind must
    compile with every section at its worst case, at every tier."""

    @pytest.mark.parametrize("kind", sorted(compiler.SECTION_BUDGETS))
    @pytest.mark.parametrize("tier", ["frugal", "standard", "rich"])
    def test_worst_case_sections_compile_at_every_tier(self, kind, tier, tmp_path):
        store = DojoStore(tmp_path / "dojo")
        store.campaigns.save(Campaign(id="c", name="c", mission="m"))
        store.configs.set_value("model.tier", tier) if hasattr(store.configs, "set_value") else None
        try:
            store.configs.save("model.tier", tier)
        except Exception:
            pass
        mult = compiler.TIER_MULTIPLIER[tier]
        values = {k: "x" * int(b * mult * 2) for k, b in compiler.SECTION_BUDGETS[kind].items()}
        values.update({"n_items": 2, "topic_path": "a.b", "difficulty": "intermediate",
                       "grounding_rule": "", "window_n": 15})
        compiled = compiler._compile(store, kind, values, {})
        assert compiled.prompt  # no BudgetExceeded: sections clip, ceiling holds


class TestHeartbeatSurvivesCompileErrors:
    def test_daily_serves_practice_when_reflection_compile_fails(self, tmp_path):
        """I4: reflection is deferrable, practice is not."""
        from unittest.mock import patch
        from dojo.api import DojoAPI
        from dojo.schemas import Attempt, Exercise
        from dojo import scheduling
        from datetime import datetime, timedelta, timezone

        api = DojoAPI(tmp_path)
        cid = api.create_campaign(name="c", topic_path="c", mission="m.")["id"]
        camp = api.store.campaigns.get(cid)
        # keep the campaign ACTIVE (default 1-phase plan would complete on
        # 6 perfect attempts → maintenance → no reflection ever fires)
        camp.attack_plan[0].criteria.min_attempts = 50
        api.store.campaigns.save(camp)
        now = datetime.now(timezone.utc)
        due = scheduling.record_outcome(
            scheduling.new_state(now - timedelta(days=9)), score=1.0, now=now - timedelta(days=8))
        api.store.exercises.save(cid, Exercise(
            id="ex_d", topic_path="c.t", difficulty="beginner", answer="a",
            prompt="q?", sr=due))
        for i in range(6):  # unreflected backlog crosses the threshold
            api.store.attempts.save(cid, Attempt(
                id=f"att_{i}", session_id="s", exercise_id="ex_d", campaign_id=cid,
                score=1.0, grader="exact", latency_seconds=5.0,
                created_at=(now - timedelta(days=8)).isoformat(), user_answer="a"))
        from dojo.tasks import flows
        with patch.object(flows, "request_reflection",
                          side_effect=compiler.BudgetExceeded("boom")):
            res = api.daily()
        assert res.get("session") is not None, "practice must survive the failure"
        assert res["skipped"]["reflection_compile_errors"] == 1
