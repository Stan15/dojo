"""Campaign persistence: one directory per campaign, three files.

`campaign.md` (frontmatter + syllabus body) is canonical; `plan.yaml` and
`changelog.md` are readable projections of the attack plan and pedagogical
journal, rebuilt on every save and folded back in on read.
"""

from typing import List, Optional
import shutil

import yaml

from .base import BaseRepository
from .engine import parse_markdown, serialize_markdown
from ..schemas import Campaign, AttackPlanPhase


class CampaignRepository(BaseRepository):
    """The campaign aggregate: campaign.md + plan.yaml + changelog.md.

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
        """One campaign by id, with `attack_plan` re-read from plan.yaml and
        `pedagogical_journal` from changelog.md when those files exist (a
        user's hand-edit to either projection wins). None when missing or
        unreadable."""
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

            changelog_file = camp_dir / "changelog.md"
            if changelog_file.exists():
                meta, _ = parse_markdown(changelog_file.read_text(encoding="utf-8"))
                camp.pedagogical_journal = meta.get("journal_entries") or []

            return camp
        except Exception as e:
            self.engine.logger.error(f"Error reading campaign {id}: {e}")
            return None

    def save(self, campaign: Campaign):
        """Writes all three files atomically under the write lock: campaign.md,
        regenerated plan.yaml, and changelog.md (journal newest-first)."""
        camp_dir_rel = f"campaigns/camp_{campaign.id}"

        with self.engine.write_lock():
            self.engine.write_markdown_file(f"{camp_dir_rel}/campaign.md", campaign, "syllabus_markdown")

            plan_dicts = [p.model_dump(exclude_defaults=True, exclude_none=True) for p in campaign.attack_plan]
            self.engine.write_text(
                f"{camp_dir_rel}/plan.yaml",
                yaml.safe_dump(plan_dicts, sort_keys=False, allow_unicode=True),
            )

            lines = [f"# Campaign Changelog: {campaign.name}\n"]
            for entry in reversed(campaign.pedagogical_journal):
                lines.append(f"## {entry.get('timestamp')} - {entry.get('action')}")
                lines.append(f"* **Trigger**: {entry.get('trigger')}")
                lines.append(f"* **Hypothesis**: {entry.get('hypothesis')}")
                lines.append(f"* **Status**: {entry.get('status')}")
                if entry.get("run_trace"):
                    lines.append(f"* **Run Trace**: [{entry.get('run_trace')}]({entry.get('run_trace')})")
                lines.append("")
            changelog_content = serialize_markdown(
                {"journal_entries": campaign.pedagogical_journal}, "\n".join(lines)
            )
            self.engine.write_text(f"{camp_dir_rel}/changelog.md", changelog_content)

            self.engine.sync_index()

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
