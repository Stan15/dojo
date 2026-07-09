"""Store conformance suite — the executable form of the ADR 011 storage contract.

Every Store backend must pass every test in this file. A new backend (e.g.
postgres) ships by adding its fixture param to BACKENDS and passing; the domain
layer never changes. Markdown-specific physics (file renames, git audit) live in
TestMarkdownBackendPhysics at the bottom.

Contract pinned here:
  1. Entities round-trip losslessly (save → get → equal), including unicode,
     multiline bodies, and set-vs-omitted optionals.
  2. References between entities are IDs, never storage paths (ADR 011; fixes the
     stale-`active_session.json` / phantom-filename bug, see INSIGHTS 2026-07-07).
  3. Unknown frontmatter added by a human survives a read-modify-write cycle.
  4. Filters respect schema defaults: an omitted field matches its default value.
  5. Identity is the `id` field, not the file location (rename-stable lookup).
  6. Writes do not auto-commit; `audit()` creates exactly one recovery point
     covering everything since the last one.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dojo.schemas import (
    Attempt,
    AttackPlanPhase,
    Campaign,
    Candidate,
    CriteriaEntry,
    Exercise,
    Insight,
    Source,
    Task,
)
from dojo.store import DojoStore

BACKENDS = ["markdown"]

CAMP_ID = "test-campaign"


@pytest.fixture(params=BACKENDS)
def store(request, tmp_path: Path) -> DojoStore:
    if request.param == "markdown":
        return DojoStore(tmp_path / "dojo")
    raise NotImplementedError(request.param)


def _git_commit_count(dojo_dir: Path) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=dojo_dir, capture_output=True, text=True,
    )
    return int(out.stdout.strip()) if out.returncode == 0 else 0


# ------------------------------------------------------------------
# Representative entities: unicode, multiline bodies, optionals both
# set and omitted. These are the round-trip fixtures.
# ------------------------------------------------------------------

def make_source() -> Source:
    return Source(
        id="src_9f2c",
        title="Métro § notes — 「東京」",
        kind="text",
        mission="Pass the TEF exam",
        content="# Heading\n\nBody with *markdown*, unicode — é, and\n\nblank lines.\n\n```py\ncode()\n```",
    )


def make_campaign() -> Campaign:
    return Campaign(
        id=CAMP_ID,
        name="French TEF",
        mission="Reach NCLC 7 by October",
        strategy_profile={"difficulty": "intermediate", "scaffolding": "medium"},
        attack_plan=[
            AttackPlanPhase(
                phase=1,
                topics=["french.oral.part_a"],
                criteria=CriteriaEntry(min_attempts=5, min_accuracy=0.6),
                focus="calibration",
            )
        ],
        pedagogical_journal=[{"timestamp": "2026-07-07T00:00:00+00:00", "action": "CREATE",
                              "trigger": "campaign created", "status": "active",
                              "hypothesis": "baseline"}],
        syllabus_markdown="## Phase 1\n\nOral comprehension — dialogues.",
    )


def make_exercise(*, archived: bool = False) -> Exercise:
    return Exercise(
        id="ex_a1b2",
        topic_path="french.oral.part_a",
        difficulty="intermediate",
        archived=archived,
        answer="Réponse — «exacte»",
        rubric="- mentions liaison\n- correct tense",
        prompt="Traduisez :\n\n> He would have gone.\n",
    )


def make_candidate() -> Candidate:
    return Candidate(
        id="cand_c3d4",
        topic_path="french.oral.part_b",
        difficulty="beginner",
        prompt="Décrivez la photo.",
    )


def make_attempt() -> Attempt:
    return Attempt(
        id="att_e5f6",
        session_id="sess_1234",
        exercise_id="ex_a1b2",
        campaign_id=CAMP_ID,
        score=0.7,
        latency_seconds=42.5,
        origin="extension",  # appetite-mode marker (dojo more) must round-trip
        feedback="felt rushed",
        prompt="Traduisez :\n\n> He would have gone.\n",
        user_answer="Il serait allé.\n\nAvec hésitation.",
    )


def make_task() -> Task:
    return Task(
        id="tsk_j9k0",
        kind="exercise.generate",
        campaign_id=CAMP_ID,
        context={"n_items": 3, "topic_path": "french.oral.part_a", "mode": "grounded"},
        payload_bytes=4096,
        prompt="You are drafting practice exercises for one learner.\n\n## MISSION\nReach NCLC 7.",
    )


def make_insight() -> Insight:
    return Insight(
        id="ins_g7h8",
        key="conditional.past.aux_choice",
        sources=["att_e5f6"],
        topic_path="french.oral.part_a",
        description="Learner picks *avoir* over *être* for motion verbs in past conditional.",
    )


# ------------------------------------------------------------------
# 1 + 2 — lossless round-trips, ID-based references
# ------------------------------------------------------------------

class TestRoundTrip:
    def test_source(self, store: DojoStore):
        src = make_source()
        store.sources.save(src)
        assert store.sources.get(src.id).model_dump() == src.model_dump()

    def test_campaign_with_plan_and_journal(self, store: DojoStore):
        camp = make_campaign()
        store.campaigns.save(camp)
        got = store.campaigns.get(camp.id)
        assert got.model_dump() == camp.model_dump()

    def test_exercise(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        ex = make_exercise()
        store.exercises.save(CAMP_ID, ex)
        assert store.exercises.get(CAMP_ID, ex.id).model_dump() == ex.model_dump()

    def test_candidate(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        cand = make_candidate()
        store.candidates.save(CAMP_ID, cand)
        assert store.candidates.get(CAMP_ID, cand.id).model_dump() == cand.model_dump()

    def test_attempt(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        att = make_attempt()
        store.attempts.save(CAMP_ID, att)
        assert store.attempts.get(CAMP_ID, att.id).model_dump() == att.model_dump()

    def test_insight(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        ins = make_insight()
        store.insights.save(CAMP_ID, ins)
        assert store.insights.get(CAMP_ID, ins.id).model_dump() == ins.model_dump()

    def test_task(self, store: DojoStore):
        tsk = make_task()
        store.tasks.save(tsk)
        assert store.tasks.get(tsk.id).model_dump() == tsk.model_dump()

    def test_task_status_filter(self, store: DojoStore):
        tsk = make_task()
        store.tasks.save(tsk)
        assert [t.id for t in store.tasks.list(filters={"status": "pending"})] == [tsk.id]
        tsk.status = "fulfilled"
        store.tasks.save(tsk)
        assert store.tasks.list(filters={"status": "pending"}) == []

    def test_rapid_attempts_on_same_exercise_all_survive(self, store: DojoStore):
        """Minted filenames must be unique by ID, never by clock: five attempts
        on one exercise within a second used to silently overwrite each other
        (caught by the daily-heartbeat tests, 2026-07-09)."""
        store.campaigns.save(make_campaign())
        for i in range(5):
            att = make_attempt()
            att.id = f"att_rapid{i}"
            store.attempts.save(CAMP_ID, att)
        assert len(store.attempts.list(CAMP_ID)) == 5

    def test_update_in_place_keeps_single_record(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        ex = make_exercise()
        store.exercises.save(CAMP_ID, ex)
        ex.difficulty = "advanced"
        store.exercises.save(CAMP_ID, ex)
        exercises = store.exercises.list(CAMP_ID)
        assert len(exercises) == 1
        assert exercises[0].difficulty == "advanced"


class TestIdReferences:
    def test_attempt_references_are_ids_not_paths(self, store: DojoStore):
        att = make_attempt()
        for ref in (att.session_id, att.exercise_id, att.campaign_id):
            assert "/" not in ref and not ref.endswith((".md", ".json")), (
                f"reference leaked a storage path: {ref!r}"
            )

    def test_attempt_refs_survive_round_trip(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        att = make_attempt()
        store.attempts.save(CAMP_ID, att)
        got = store.attempts.get(CAMP_ID, att.id)
        assert got.exercise_id == "ex_a1b2"
        assert got.session_id == "sess_1234"
        assert got.campaign_id == CAMP_ID


# ------------------------------------------------------------------
# 4 — filter semantics respect schema defaults
# ------------------------------------------------------------------

class TestFilters:
    def test_omitted_field_matches_its_default(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        store.exercises.save(CAMP_ID, make_exercise(archived=False))
        active = store.exercises.list(CAMP_ID, filters={"archived": False})
        assert [e.id for e in active] == ["ex_a1b2"]
        assert store.exercises.list(CAMP_ID, filters={"archived": True}) == []

    def test_set_field_matches_exactly(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        ex = make_exercise(archived=True)
        store.exercises.save(CAMP_ID, ex)
        assert store.exercises.list(CAMP_ID, filters={"archived": True})[0].id == ex.id
        assert store.exercises.list(CAMP_ID, filters={"archived": False}) == []


# ------------------------------------------------------------------
# 6 — audit: no auto-commit per write; one recovery point per audit()
# ------------------------------------------------------------------

class TestAudit:
    def test_writes_do_not_commit_and_audit_batches(self, store: DojoStore):
        baseline = _git_commit_count(store.dojo_dir)
        store.campaigns.save(make_campaign())
        store.exercises.save(CAMP_ID, make_exercise())
        store.candidates.save(CAMP_ID, make_candidate())
        assert _git_commit_count(store.dojo_dir) == baseline, (
            "entity writes must not auto-commit (ADR 011: one commit per command)"
        )
        store.audit("dojo test: batch of three writes")
        assert _git_commit_count(store.dojo_dir) == baseline + 1

    def test_audit_with_clean_tree_is_a_noop(self, store: DojoStore):
        store.campaigns.save(make_campaign())
        store.audit("first")
        n = _git_commit_count(store.dojo_dir)
        store.audit("second — nothing changed")
        assert _git_commit_count(store.dojo_dir) == n


# ------------------------------------------------------------------
# Markdown-backend physics: human edits and file renames
# ------------------------------------------------------------------

class TestMarkdownBackendPhysics:
    @pytest.fixture
    def md_store(self, tmp_path: Path) -> DojoStore:
        return DojoStore(tmp_path / "dojo")

    def _exercise_file(self, md_store: DojoStore) -> Path:
        files = list((md_store.dojo_dir / "campaigns" / f"camp_{CAMP_ID}" / "exercises").glob("*.md"))
        assert len(files) == 1
        return files[0]

    def test_unknown_frontmatter_survives_rewrite(self, md_store: DojoStore):
        md_store.campaigns.save(make_campaign())
        ex = make_exercise()
        md_store.exercises.save(CAMP_ID, ex)
        path = self._exercise_file(md_store)
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---")
        path.write_text(
            content.replace("---\n", "---\nmy_note: keep me please\n", 1),
            encoding="utf-8",
        )

        got = md_store.exercises.get(CAMP_ID, ex.id)
        got.difficulty = "advanced"
        md_store.exercises.save(CAMP_ID, got)

        final = self._exercise_file(md_store).read_text(encoding="utf-8")
        assert "my_note: keep me please" in final, "human-added frontmatter was destroyed"
        assert "difficulty: advanced" in final

    def test_lookup_survives_file_rename(self, md_store: DojoStore):
        md_store.campaigns.save(make_campaign())
        ex = make_exercise()
        md_store.exercises.save(CAMP_ID, ex)
        path = self._exercise_file(md_store)
        path.rename(path.with_name("renamed-by-a-human.md"))

        got = md_store.exercises.get(CAMP_ID, ex.id)
        assert got is not None and got.id == ex.id, "identity must be the id field, not the filename"

    def test_cli_command_creates_exactly_one_recovery_point(self, tmp_path: Path):
        """ADR 011: audit batching is per CLI command — the dispatch choke point
        in cli.main(), not per entity write."""
        from dojo.cli import main

        dojo_dir = tmp_path / "dojo"
        assert main(["--db", str(dojo_dir), "config", "set", "daily.packet_size", "5"]) == 0
        after_first = _git_commit_count(dojo_dir)
        # birth commit (store initialized) + exactly one for the command
        assert after_first == 2, "one successful mutating command → exactly one commit beyond birth"

        assert main(["--db", str(dojo_dir), "config", "set", "daily.packet_size", "8"]) == 0
        assert _git_commit_count(dojo_dir) == after_first + 1

    def test_source_lookup_survives_file_rename(self, md_store: DojoStore):
        src = make_source()
        md_store.sources.save(src)
        src_file = md_store.dojo_dir / "sources" / f"{src.id}.md"
        assert src_file.exists()
        src_file.rename(src_file.with_name("my-renamed-notes.md"))

        got = md_store.sources.get(src.id)
        assert got is not None and got.id == src.id

    def test_doctor_surfaces_unaudited_changes(self, md_store: DojoStore):
        """ADR 011: a failing audit setup must become visible, not stay swallowed."""
        md_store.campaigns.save(make_campaign())
        results = md_store.doctor.run()
        assert any("uncommitted" in e for e in results["Version control audit"])

        md_store.audit("recovery point")
        results = md_store.doctor.run()
        assert results["Version control audit"] == []

    def test_doctor_flags_content_without_git(self, md_store: DojoStore):
        import shutil

        md_store.campaigns.save(make_campaign())
        md_store.audit("recovery point")
        shutil.rmtree(md_store.dojo_dir / ".git")
        results = md_store.doctor.run()
        assert any("no git repository" in e.lower() for e in results["Version control audit"])
