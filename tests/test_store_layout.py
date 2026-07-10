"""ADR 018 — vault-grade campaign layout.

Pins: campaign.md frontmatter carries scalars only (no plan/topics/journal);
the aggregate round-trips through the five-file layout; the plan-authority
state machine still walks the (relocated) journal; legacy v1 shapes read
clean and migrate on save / via doctor; dead snapshot fields are stripped
from historical entries (delete-over-retain — git is the archive).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from dojo.schemas import AttackPlanPhase, Campaign, CriteriaEntry
from dojo.store import DojoStore
from dojo.store.engine import parse_markdown, serialize_markdown
from dojo.tasks import authority

CAMP_ID = "vault"


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def _campaign(**over) -> Campaign:
    base = dict(
        id=CAMP_ID, name="Vault", mission="Read cleanly in Obsidian.",
        attack_plan=[AttackPlanPhase(
            phase=1, topics=["v.t"], criteria=CriteriaEntry(min_attempts=3, min_accuracy=0.7),
        )],
        topics=[{"path": "v.t", "kind": "skill", "summary": "the topic"}],
        pedagogical_journal=[
            {"timestamp": "2026-07-10T03:00:00+00:00", "action": "CREATE",
             "trigger": "creation", "hypothesis": "init", "status": "resolved",
             "plan_snapshot": [{"phase": 1, "topics": ["v.t"],
                                "criteria": {"min_attempts": 3, "min_accuracy": 0.7}}]},
            {"timestamp": "2026-07-10T04:00:00+00:00", "action": "REFLECT",
             "trigger": "reflection over 5 attempts (task tsk_x)",
             "hypothesis": "no change", "status": "applied",
             "insights_changed": {"created": 1, "updated": 0, "resolved": 0}},
        ],
        syllabus_markdown="# Vault\n\nThe syllabus body.",
    )
    base.update(over)
    return Campaign(**base)


class TestVaultLayout:
    def test_frontmatter_carries_scalars_only(self, tmp_path: Path):
        store = DojoStore(tmp_path / "dojo")
        store.campaigns.save(_campaign())
        md = (store.dojo_dir / f"campaigns/camp_{CAMP_ID}/campaign.md").read_text()
        meta, body = parse_markdown(md)
        assert "attack_plan" not in meta and "topics" not in meta
        assert "pedagogical_journal" not in meta
        assert meta["mission"] == "Read cleanly in Obsidian."
        assert "The syllabus body." in body

    def test_five_file_roundtrip(self, tmp_path: Path):
        store = DojoStore(tmp_path / "dojo")
        saved = _campaign()
        store.campaigns.save(saved)
        camp_dir = store.dojo_dir / f"campaigns/camp_{CAMP_ID}"
        assert (camp_dir / "topics.yaml").exists()
        assert (camp_dir / ".journal.yaml").exists()
        assert (camp_dir / "journal.md").exists()
        loaded = store.campaigns.get(CAMP_ID)
        assert [p.model_dump() for p in loaded.attack_plan] == [p.model_dump() for p in saved.attack_plan]
        assert loaded.topics == saved.topics
        assert loaded.pedagogical_journal == saved.pedagogical_journal
        assert loaded.syllabus_markdown == saved.syllabus_markdown

    def test_journal_prose_is_human_and_current(self, tmp_path: Path):
        store = DojoStore(tmp_path / "dojo")
        store.campaigns.save(_campaign())
        prose = (store.dojo_dir / f"campaigns/camp_{CAMP_ID}/journal.md").read_text()
        assert prose.startswith("# Journal — Vault")
        assert "REFLECT" in prose and "no change" in prose
        assert "1 new" in prose, "insight counts render for the reader"
        assert "plan_snapshot" not in prose, "machine payloads stay out of prose"

    def test_authority_state_machine_survives_relocation(self, tmp_path: Path):
        store = DojoStore(tmp_path / "dojo")
        camp = _campaign()
        camp.pedagogical_journal.append(authority.journal_entry(
            authority.PLAN_PROPOSED, reason="split phase", task_id="tsk_y",
            plan_snapshot=camp.attack_plan, proposed=camp.attack_plan,
        ))
        store.campaigns.save(camp)
        loaded = store.campaigns.get(CAMP_ID)
        assert authority.confirmed_plan_baseline(loaded), "CREATE snapshot intact"
        assert authority.pending_proposal(loaded) is not None

    def test_dead_snapshot_fields_stripped_on_save(self, tmp_path: Path):
        store = DojoStore(tmp_path / "dojo")
        camp = _campaign()
        camp.pedagogical_journal.append({
            "timestamp": "2026-07-10T05:00:00+00:00", "action": "PHASE_ADVANCE",
            "trigger": "Passed Phase 0 criteria (5 attempts, 80.0% accuracy)",
            "hypothesis": "mastery", "status": "resolved",
            "plan_snapshot": [{"phase": 1}], "syllabus_snapshot": "# huge",
            "hypotheses_snapshot": [], "performance_snapshot": {"attempts": 5},
        })
        store.campaigns.save(camp)
        entries = yaml.safe_load(
            (store.dojo_dir / f"campaigns/camp_{CAMP_ID}/.journal.yaml").read_text()
        )
        advance = next(e for e in entries if e["action"] == "PHASE_ADVANCE")
        for dead in ("plan_snapshot", "syllabus_snapshot", "hypotheses_snapshot", "performance_snapshot"):
            assert dead not in advance
        create = next(e for e in entries if e["action"] == "CREATE")
        assert "plan_snapshot" in create, "authority baseline snapshots survive"


def _write_legacy_store(root: Path) -> DojoStore:
    """A v1-shaped campaign: everything in campaign.md frontmatter plus a
    changelog.md whose frontmatter journal (the old read winner) differs."""
    store = DojoStore(root / "dojo")
    camp_dir = store.dojo_dir / f"campaigns/camp_{CAMP_ID}"
    camp_dir.mkdir(parents=True, exist_ok=True)
    camp = _campaign()
    data = camp.model_dump(mode="json")
    body = data.pop("syllabus_markdown")
    (camp_dir / "campaign.md").write_text(serialize_markdown(data, body))
    journal = camp.pedagogical_journal + [{
        "timestamp": "2026-07-10T06:00:00+00:00", "action": "REFLECT",
        "trigger": "reflection over 3 attempts (task tsk_z)",
        "hypothesis": "changelog copy wins", "status": "applied",
    }]
    (camp_dir / "changelog.md").write_text(
        serialize_markdown({"journal_entries": journal}, "# Campaign Changelog: Vault\n")
    )
    store.engine.sync_index()
    return store


class TestLegacyMigration:
    def test_legacy_shape_reads_clean(self, tmp_path: Path):
        store = _write_legacy_store(tmp_path)
        camp = store.campaigns.get(CAMP_ID)
        assert camp is not None
        assert camp.pedagogical_journal[-1]["hypothesis"] == "changelog copy wins"
        assert camp.topics and camp.attack_plan

    def test_migrate_layout_rewrites_and_is_idempotent(self, tmp_path: Path):
        store = _write_legacy_store(tmp_path)
        assert store.campaigns.migrate_layout() == 1
        camp_dir = store.dojo_dir / f"campaigns/camp_{CAMP_ID}"
        assert not (camp_dir / "changelog.md").exists()
        meta, _ = parse_markdown((camp_dir / "campaign.md").read_text())
        assert "pedagogical_journal" not in meta and "topics" not in meta
        camp = store.campaigns.get(CAMP_ID)
        assert camp.pedagogical_journal[-1]["hypothesis"] == "changelog copy wins"
        assert store.campaigns.migrate_layout() == 0, "second pass finds nothing"
