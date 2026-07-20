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


class TestCompilerBranches:
    """The compiler, never the model, decides encoding-stage and calibration
    branches (craft rule 5; eval findings 2026-07-18: the model-side struggle
    conditional never fired at any caliber, and the update-first reflect
    example baits update ops from an empty insight store)."""

    def _fresh(self, tmp_path, *, topics=None, strategy=None) -> tuple[DojoStore, Campaign]:
        s = DojoStore(tmp_path / "dojo")
        camp = Campaign(
            id="c1", name="C", mission="Pass the radio exam.",
            topics=topics or [], strategy_profile=strategy or {},
        )
        s.campaigns.save(camp)
        return s, s.campaigns.get("c1")

    def test_first_contact_registered_topic_gets_introduce_rule(self, tmp_path):
        s, camp = self._fresh(
            tmp_path, topics=[{"path": "aviation.phonetic_alphabet", "kind": "skill"}]
        )
        compiled = compiler.compile_generate(
            s, camp, topic_path="aviation.phonetic_alphabet", n_items=2,
            difficulty="beginner",
        )
        assert "FIRST CONTACT" in compiled.prompt
        assert "not new" not in compiled.prompt

    def test_practiced_topic_gets_no_present_guard(self, store: DojoStore):
        store.exercises.save(CAMP_ID, Exercise(
            id="ex_1", topic_path="french.grammar", difficulty="intermediate",
            prompt="Traduisez.",
        ))
        compiled = compiler.compile_generate(
            store, _campaign(store), topic_path="french.grammar",
            n_items=2, difficulty="intermediate",
        )
        assert "not new" in compiled.prompt
        assert "FIRST CONTACT" not in compiled.prompt

    def test_grounded_first_contact_gets_guard_not_introduce(self, tmp_path):
        s, camp = self._fresh(
            tmp_path, topics=[{"path": "anatomy.nerves", "kind": "recall"}]
        )
        compiled = compiler.compile_generate(
            s, camp, topic_path="anatomy.nerves", n_items=2,
            difficulty="beginner", source_slice="The twelve cranial nerves are…",
        )
        assert "FIRST CONTACT" not in compiled.prompt
        assert "not new" in compiled.prompt

    def test_unregistered_topic_with_other_practice_stays_neutral(self, store: DojoStore):
        # att_1 exists but its exercise is unknown → no on-topic practice,
        # topic unregistered: neither branch may claim anything.
        compiled = compiler.compile_generate(
            store, _campaign(store), topic_path="french.oral",
            n_items=2, difficulty="intermediate",
        )
        assert "FIRST CONTACT" not in compiled.prompt
        assert "not new" not in compiled.prompt

    def _seed_struggle(self, s: DojoStore, camp_id: str, scores) -> None:
        s.exercises.save(camp_id, Exercise(
            id="ex_s", topic_path="pruning.fruit_trees", difficulty="intermediate",
            prompt="Which cut first?",
        ))
        for i, sc in enumerate(scores):
            s.attempts.save(camp_id, Attempt(
                id=f"att_s{i}", session_id="s1", exercise_id="ex_s",
                campaign_id=camp_id, score=sc, latency_seconds=90.0,
                grader="ai", user_answer="a guess",
            ))

    def test_repeated_struggle_fires_downward_calibration(self, tmp_path):
        s, camp = self._fresh(tmp_path, strategy={"difficulty": "intermediate",
                                                  "scaffolding": "medium"})
        self._seed_struggle(s, camp.id, [0.3, 0.3, 0.3, 0.3])
        compiled = compiler.compile_generate(
            s, camp, topic_path="pruning.fruit_trees", n_items=3,
            difficulty="intermediate",
        )
        assert "Calibrate DOWN" in compiled.prompt
        assert "one notch above RECENT" not in compiled.prompt

    def test_struggle_suppressed_when_scaffolding_already_high(self, tmp_path):
        s, camp = self._fresh(tmp_path, strategy={"difficulty": "intermediate",
                                                  "scaffolding": "high"})
        self._seed_struggle(s, camp.id, [0.3, 0.3, 0.3])
        compiled = compiler.compile_generate(
            s, camp, topic_path="pruning.fruit_trees", n_items=3,
            difficulty="intermediate",
        )
        assert "Calibrate DOWN" not in compiled.prompt
        assert "one notch above RECENT" in compiled.prompt

    def test_mixed_scores_keep_normal_calibration(self, tmp_path):
        s, camp = self._fresh(tmp_path)
        self._seed_struggle(s, camp.id, [0.3, 0.3, 1.0])
        compiled = compiler.compile_generate(
            s, camp, topic_path="pruning.fruit_trees", n_items=3,
            difficulty="intermediate",
        )
        assert "Calibrate DOWN" not in compiled.prompt

    def test_reflect_empty_insights_leads_with_create_ops(self, tmp_path):
        s, camp = self._fresh(tmp_path)
        compiled = compiler.compile_reflect(s, camp)
        assert "create is the only valid op" in compiled.prompt
        assert '"op": "create"' in compiled.prompt
        assert '"op": "update"' not in compiled.prompt

    def test_route_default_profile_keeps_legacy_rule_text(self, store: DojoStore):
        """RSIMP (2026-07-19): route rule blocks are compiler-selected
        fragments; the DEFAULT profile must compile byte-identical legacy
        text (verified against pre-extraction hashes at landing)."""
        compiled = compiler.compile_goal_route(store, goal="learn to read tide tables")
        assert '"action" is one word' in compiled.prompt
        assert '"confidence" is high or low.' in compiled.prompt
        assert "Never \"stay_inbox\"" in compiled.prompt

    def test_route_lean_profile_states_fewer_rules(self, store: DojoStore):
        store.configs.set_value("fulfiller.route_profile", "lean")
        compiled = compiler.compile_goal_route(store, goal="learn to read tide tables")
        assert '"action" is exactly one of' in compiled.prompt
        assert '"confidence" is high or low.' not in compiled.prompt
        assert "set confidence" not in compiled.prompt
        # cap-bearing lines never move (statement gate): rule 3 still present
        assert "propose_campaign" in compiled.prompt

    def test_route_unknown_profile_falls_back_to_default(self, store: DojoStore):
        store.configs.set_value("fulfiller.route_profile", "bogus")
        compiled = compiler.compile_goal_route(store, goal="learn to read tide tables")
        assert '"action" is one word' in compiled.prompt

    def test_reflect_with_insights_shows_update_example_only(self, store: DojoStore):
        """EXB2 (2026-07-19): with real insights present, the create example
        is suppressed — 12/14 surviving example-bleed copies were the create
        op copied wholesale as a fake new insight. Create shape stays stated
        in the Field rules prose; ops_no_insights keeps its create example."""
        compiled = compiler.compile_reflect(store, _campaign(store))
        assert "create is the only valid op" not in compiled.prompt
        assert '"op": "update"' in compiled.prompt
        assert '"op": "create"' not in compiled.prompt


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
                       "grounding_rule": "", "encounter_rule": "",
                       "calibration_rule": "", "window_n": 15,
                       "ops_example": "", "journal_example": "",
                       "route_soft_rules": "", "route_field_rules": ""})
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


class TestAnchorProfile:
    """QUESTIONS 6i: the deliberation invitation is compiler-appended on
    config opt-in ONLY; the default profile leaves payloads untouched."""

    INVITE = "If two outputs seem defensible, think it through step by step"

    def test_default_neutral_has_no_invitation(self, store: DojoStore):
        compiled = compiler.compile_generate(
            store, _campaign(store), topic_path="t", n_items=3,
            difficulty="intermediate")
        assert self.INVITE not in compiled.prompt

    def test_deliberate_profile_appends_invitation_last(self, store: DojoStore):
        store.configs.set_value("fulfiller.anchor_profile", "deliberate")
        compiled = compiler.compile_generate(
            store, _campaign(store), topic_path="t", n_items=3,
            difficulty="intermediate")
        assert self.INVITE in compiled.prompt
        assert compiled.prompt.rstrip().endswith("Only the last JSON object counts.")


class TestOpsExampleRealId:
    """P9b: with active insights, the update example carries a REAL id from
    the store — never a static literal a model can copy into an invalid op."""

    def test_update_example_uses_first_active_insight_id(self, store: DojoStore):
        compiled = compiler.compile_reflect(store, _campaign(store))
        # the fixture seeds exactly one active insight: ins_1
        assert '"id": "ins_1"' in compiled.prompt
        assert "ins_4c21a9e7" not in compiled.prompt  # no static literal survives
