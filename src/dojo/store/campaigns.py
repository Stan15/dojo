"""Campaign persistence: one directory per campaign, five files (ADR 018).

`campaign.md` holds only scalar identity/config in frontmatter plus the
syllabus body — vault-grade readable. The aggregate's collections live in
sibling files: `plan.yaml` (attack plan — hand-edits win), `topics.yaml`
(topic registry + FSRS state), `.journal.yaml` (the machine event log the
plan-authority state machine walks; dot-hidden from vaults), and
`journal.md` (a regenerated prose projection of the journal, newest-first —
display only, never parsed back).

Legacy shapes (journal/plan/topics in campaign.md frontmatter, journal in
changelog.md frontmatter) are still READ; every save writes the new layout
and deletes changelog.md. `dojo doctor` migrates a whole store in one pass.
"""

from typing import Any, List, Optional
import shutil

import yaml

from .base import BaseRepository
from .engine import parse_markdown
from ..schemas import Campaign, AttackPlanPhase

# Projected out of campaign.md frontmatter (ADR 018).
PROJECTED_FIELDS = ("attack_plan", "topics", "pedagogical_journal")

# Journal fields no surface reads (ADR 018 investigation) — stripped from
# every entry on save, historical ones included (delete-over-retain: git is
# the archive). plan_snapshot is functional ONLY on plan-authority actions.
_DEAD_ENTRY_FIELDS = ("syllabus_snapshot", "hypotheses_snapshot", "performance_snapshot")
_SNAPSHOT_ACTIONS = ("CREATE", "PLAN_CONFIRMED", "PLAN_APPLIED", "PLAN_PROPOSED", "PLAN_REVERTED")


def _lean_entry(entry: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in entry.items() if k not in _DEAD_ENTRY_FIELDS}
    if out.get("action") not in _SNAPSHOT_ACTIONS:
        out.pop("plan_snapshot", None)
    return out


def _journal_prose(campaign: Campaign) -> str:
    """The human journal (newest-first). A projection: regenerated every
    save, edits are not folded back — plan.yaml/topics.yaml are the
    hand-editable canonical files, the journal is system-authored."""
    lines = [f"# Journal — {campaign.name}", ""]
    for e in reversed(campaign.pedagogical_journal):
        ts = (e.get("timestamp") or "")[:16].replace("T", " ")
        lines.append(f"## {ts} · {e.get('action', '?')}")
        if e.get("trigger"):
            lines.append(f"- trigger: {e['trigger']}")
        if e.get("hypothesis"):
            lines.append(f"- note: {e['hypothesis']}")
        if e.get("status") and e.get("status") != "applied":
            lines.append(f"- status: {e['status']}")
        ch = e.get("insights_changed")
        if ch:
            lines.append(
                f"- insights: {ch.get('created', 0)} new · "
                f"{ch.get('updated', 0)} updated · {ch.get('resolved', 0)} resolved"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class CampaignRepository(BaseRepository):
    """The campaign aggregate: campaign.md + plan.yaml + topics.yaml +
    .journal.yaml + journal.md (ADR 018).

    Campaign-scoped children (exercises/candidates/attempts/insights) live in
    their own CampaignScopedRepository instances — see store/base.py.
    """

    def list(self) -> List[Campaign]:
        """All campaigns, newest first, fully hydrated (plan + journal)."""
        recs = self.engine.query_index("campaign")
        recs = sorted(recs, key=lambda x: x["data"].get("created_at", ""), reverse=True)
        campaigns = []
        for r in recs:
            # path shape: campaigns/camp_<id>/campaign.md
            parts = r["path"].split("/")
            if len(parts) >= 2 and parts[1].startswith("camp_"):
                camp = self.get(parts[1][5:])
                if camp:
                    campaigns.append(camp)
        return campaigns

    def get(self, id: str) -> Optional[Campaign]:
        """One campaign by id, hydrated from its projections: plan.yaml
        (hand-edits win), topics.yaml, .journal.yaml. Legacy shapes —
        frontmatter collections, changelog.md `journal_entries` — are still
        understood so a v1 store reads clean before its first migration
        save. None when missing or unreadable."""
        rel_path = f"campaigns/camp_{id}/campaign.md"
        if not (self.engine.dojo_dir / rel_path).exists():
            return None
        try:
            camp = self.engine.read_markdown_file(rel_path, Campaign, "syllabus_markdown")
            camp_dir = (self.engine.dojo_dir / rel_path).parent

            plan_file = camp_dir / "plan.yaml"
            if plan_file.exists():
                plan_data = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or []
                camp.attack_plan = [AttackPlanPhase.model_validate(p) for p in plan_data]

            topics_file = camp_dir / "topics.yaml"
            if topics_file.exists():
                camp.topics = yaml.safe_load(topics_file.read_text(encoding="utf-8")) or []

            journal_file = camp_dir / ".journal.yaml"
            changelog_file = camp_dir / "changelog.md"  # legacy (pre-ADR 018)
            if journal_file.exists():
                camp.pedagogical_journal = (
                    yaml.safe_load(journal_file.read_text(encoding="utf-8")) or []
                )
            elif changelog_file.exists():
                meta, _ = parse_markdown(changelog_file.read_text(encoding="utf-8"))
                camp.pedagogical_journal = meta.get("journal_entries") or []

            return camp
        except Exception as e:
            self.engine.logger.error(f"Error reading campaign {id}: {e}")
            return None

    def save(self, campaign: Campaign):
        """Writes the five-file layout atomically under the write lock and
        deletes the legacy changelog.md. Historical journal entries are
        leaned in the same stroke (dead snapshot fields stripped)."""
        camp_dir_rel = f"campaigns/camp_{campaign.id}"
        campaign.pedagogical_journal = [
            _lean_entry(e) for e in campaign.pedagogical_journal
        ]

        with self.engine.write_lock():
            self.engine.write_markdown_file(
                f"{camp_dir_rel}/campaign.md", campaign, "syllabus_markdown",
                exclude=PROJECTED_FIELDS,
            )

            plan_dicts = [p.model_dump(exclude_defaults=True, exclude_none=True) for p in campaign.attack_plan]
            self.engine.write_text(
                f"{camp_dir_rel}/plan.yaml",
                yaml.safe_dump(plan_dicts, sort_keys=False, allow_unicode=True),
            )
            self.engine.write_text(
                f"{camp_dir_rel}/topics.yaml",
                yaml.safe_dump(campaign.topics, sort_keys=False, allow_unicode=True),
            )
            self.engine.write_text(
                f"{camp_dir_rel}/.journal.yaml",
                yaml.safe_dump(campaign.pedagogical_journal, sort_keys=False, allow_unicode=True),
            )
            self.engine.write_text(f"{camp_dir_rel}/journal.md", _journal_prose(campaign))
            self.engine.delete_file(f"{camp_dir_rel}/changelog.md")

            self.engine.sync_index()

    def migrate_layout(self) -> int:
        """One-pass ADR 018 migration: re-saves every campaign still carrying
        a legacy shape (changelog.md present, or projected collections in
        campaign.md frontmatter). Returns how many were migrated. Idempotent —
        a vault-layout campaign is left untouched."""
        migrated = 0
        campaigns_dir = self.engine.dojo_dir / "campaigns"
        if not campaigns_dir.exists():
            return 0
        for camp_dir in sorted(campaigns_dir.iterdir()):
            if not camp_dir.is_dir() or not camp_dir.name.startswith("camp_"):
                continue
            md = camp_dir / "campaign.md"
            if not md.exists():
                continue
            legacy = (camp_dir / "changelog.md").exists()
            if not legacy:
                meta, _ = parse_markdown(md.read_text(encoding="utf-8"))
                legacy = any(k in meta for k in PROJECTED_FIELDS)
            if not legacy:
                continue
            camp = self.get(camp_dir.name[5:])
            if camp is not None:
                self.save(camp)
                migrated += 1
        return migrated

    def archive(self, id: str):
        """Moves the whole campaign directory (children included) to
        `archive/campaigns/`, replacing any earlier archive of the same id.
        Archived campaigns disappear from `list`/`get`."""
        src_dir = self.engine.dojo_dir / "campaigns" / f"camp_{id}"
        dest_dir = self.engine.dojo_dir / "archive" / "campaigns" / f"camp_{id}"
        if src_dir.exists():
            with self.engine.write_lock():
                dest_dir.parent.mkdir(parents=True, exist_ok=True)
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                src_dir.rename(dest_dir)
                self.engine.sync_index()
