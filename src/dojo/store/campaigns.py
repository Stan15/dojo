from typing import List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .base import BaseRepository
from .engine import slugify, parse_markdown, serialize_markdown, _match_filter
from ..schemas import Campaign, Exercise, Candidate, Attempt, Insight, AttackPlanPhase

class CampaignRepository(BaseRepository):
    # ==========================================
    # Campaigns
    # ==========================================
    def list(self) -> List[Campaign]:
        recs = self.engine.query_index("campaign")
        recs = sorted(recs, key=lambda x: x["data"].get("created_at", ""), reverse=True)
        campaigns = []
        for r in recs:
            # recs maps to paths campaigns/camp_{id}/campaign.md. Let's parse campaign_id from path.
            # path is e.g. "campaigns/camp_tef/campaign.md". camp_tef is index 1. Suffix after camp_ is id.
            parts = r["path"].split("/")
            if len(parts) >= 2 and parts[1].startswith("camp_"):
                camp_id = parts[1][5:]
                camp = self.get(camp_id)
                if camp:
                    campaigns.append(camp)
        return campaigns

    def get(self, id: str) -> Optional[Campaign]:
        rel_path = f"campaigns/camp_{id}/campaign.md"
        if not (self.engine.dojo_dir / rel_path).exists():
            return None
        try:
            camp = self.engine.read_markdown_file(rel_path, Campaign, "syllabus_markdown")
            camp_dir = (self.engine.dojo_dir / rel_path).parent

            # plan.yaml
            plan_file = camp_dir / "plan.yaml"
            if plan_file.exists():
                plan_data = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or []
                camp.attack_plan = [AttackPlanPhase.model_validate(p) for p in plan_data]

            # changelog.md
            changelog_file = camp_dir / "changelog.md"
            if changelog_file.exists():
                meta, _ = parse_markdown(changelog_file.read_text(encoding="utf-8"))
                camp.pedagogical_journal = meta.get("journal_entries") or []

            return camp
        except Exception as e:
            self.engine.logger.error(f"Error reading campaign {id}: {e}")
            return None

    def save(self, campaign: Campaign):
        camp_dir_rel = f"campaigns/camp_{campaign.id}"
        campaign_md_rel = f"{camp_dir_rel}/campaign.md"
        plan_yaml_rel = f"{camp_dir_rel}/plan.yaml"
        changelog_md_rel = f"{camp_dir_rel}/changelog.md"

        with self.engine.write_lock():
            # 1. Save campaign.md
            self.engine.write_markdown_file(campaign_md_rel, campaign, "syllabus_markdown")

            # 2. Save plan.yaml
            plan_dicts = [p.model_dump(exclude_defaults=True, exclude_none=True) for p in campaign.attack_plan]
            self.engine.write_text(plan_yaml_rel, yaml.safe_dump(plan_dicts, sort_keys=False, allow_unicode=True))

            # 3. Save changelog.md (structured journal entries in frontmatter + human outline)
            lines = [f"# Campaign Changelog: {campaign.name}\n"]
            for entry in reversed(campaign.pedagogical_journal):
                lines.append(f"## {entry.get('timestamp')} - {entry.get('action')}")
                lines.append(f"* **Trigger**: {entry.get('trigger')}")
                lines.append(f"* **Hypothesis**: {entry.get('hypothesis')}")
                lines.append(f"* **Status**: {entry.get('status')}")
                if entry.get("run_trace"):
                    lines.append(f"* **Run Trace**: [{entry.get('run_trace')}]({entry.get('run_trace')})")
                lines.append("")
            changelog_body = "\n".join(lines)
            changelog_meta = {"journal_entries": campaign.pedagogical_journal}
            changelog_content = serialize_markdown(changelog_meta, changelog_body)
            self.engine.write_text(changelog_md_rel, changelog_content)

            self.engine.sync_index()

    def archive(self, id: str):
        src_dir = self.engine.dojo_dir / "campaigns" / f"camp_{id}"
        dest_dir = self.engine.dojo_dir / "archive" / "campaigns" / f"camp_{id}"
        if src_dir.exists():
            with self.engine.write_lock():
                dest_dir.parent.mkdir(parents=True, exist_ok=True)
                if dest_dir.exists():
                    import shutil
                    shutil.rmtree(dest_dir)
                src_dir.rename(dest_dir)
                self.engine.sync_index()

    # ==========================================
    # Exercises
    # ==========================================
    def list_exercises(self, campaign_id: str, filters: dict[str, Any] = None) -> List[Exercise]:
        self.engine.sync_index()
        prefix_path = f"campaigns/camp_{campaign_id}/exercises"
        exercises = []
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "exercise" and rel_path.startswith(prefix_path):
                metadata = file_info.get("data", {})
                if _match_filter(metadata, filters, "exercise"):
                    ex = self.get_exercise(campaign_id, metadata.get("id"))
                    if ex:
                        exercises.append(ex)
        return sorted(exercises, key=lambda x: x.id)

    def get_exercise(self, campaign_id: str, id: str) -> Optional[Exercise]:
        prefix_path = f"campaigns/camp_{campaign_id}/exercises"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "exercise" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if not matching_path or not (self.engine.dojo_dir / matching_path).exists():
            return None
        try:
            return self.engine.read_markdown_file(matching_path, Exercise, "prompt")
        except Exception as e:
            self.engine.logger.error(f"Error reading exercise {id}: {e}")
            return None

    def save_exercise(self, campaign_id: str, exercise: Exercise):
        prefix_path = f"campaigns/camp_{campaign_id}/exercises"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "exercise" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == exercise.id:
                    matching_path = rel_path
                    break

        if not matching_path:
            date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            existing_count = len(self.list_exercises(campaign_id))
            counter_str = f"{existing_count + 1:04d}"
            filename = f"{date_prefix}_{counter_str}_{slugify(exercise.id)}.md"
            matching_path = f"{prefix_path}/{filename}"

        with self.engine.write_lock():
            self.engine.write_markdown_file(matching_path, exercise, "prompt")
            self.engine.sync_index()

    def delete_exercise(self, campaign_id: str, id: str):
        prefix_path = f"campaigns/camp_{campaign_id}/exercises"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "exercise" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if matching_path:
            with self.engine.write_lock():
                self.engine.delete_file(matching_path)
                self.engine.sync_index()

    # ==========================================
    # Candidates
    # ==========================================
    def list_candidates(self, campaign_id: str) -> List[Candidate]:
        self.engine.sync_index()
        prefix_path = f"campaigns/camp_{campaign_id}/candidates"
        candidates = []
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "candidate" and rel_path.startswith(prefix_path):
                metadata = file_info.get("data", {})
                cand = self.get_candidate(campaign_id, metadata.get("id"))
                if cand:
                    candidates.append(cand)
        return sorted(candidates, key=lambda x: x.id)

    def get_candidate(self, campaign_id: str, id: str) -> Optional[Candidate]:
        prefix_path = f"campaigns/camp_{campaign_id}/candidates"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "candidate" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if not matching_path or not (self.engine.dojo_dir / matching_path).exists():
            return None
        try:
            return self.engine.read_markdown_file(matching_path, Candidate, "prompt")
        except Exception as e:
            self.engine.logger.error(f"Error reading candidate {id}: {e}")
            return None

    def save_candidate(self, campaign_id: str, candidate: Candidate):
        prefix_path = f"campaigns/camp_{campaign_id}/candidates"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "candidate" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == candidate.id:
                    matching_path = rel_path
                    break

        if not matching_path:
            date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            existing_count = len(self.list_candidates(campaign_id))
            counter_str = f"{existing_count + 1:04d}"
            filename = f"{date_prefix}_{counter_str}_{slugify(candidate.id)}.md"
            matching_path = f"{prefix_path}/{filename}"

        with self.engine.write_lock():
            self.engine.write_markdown_file(matching_path, candidate, "prompt")
            self.engine.sync_index()

    def delete_candidate(self, campaign_id: str, id: str):
        prefix_path = f"campaigns/camp_{campaign_id}/candidates"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "candidate" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if matching_path:
            with self.engine.write_lock():
                self.engine.delete_file(matching_path)
                self.engine.sync_index()

    # ==========================================
    # Attempts
    # ==========================================
    def list_attempts(self, campaign_id: str) -> List[Attempt]:
        self.engine.sync_index()
        prefix_path = f"campaigns/camp_{campaign_id}/attempts"
        attempts = []
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "attempt" and rel_path.startswith(prefix_path):
                metadata = file_info.get("data", {})
                att = self.get_attempt(campaign_id, metadata.get("id"))
                if att:
                    attempts.append(att)
        return sorted(attempts, key=lambda x: x.created_at)

    def get_attempt(self, campaign_id: str, id: str) -> Optional[Attempt]:
        prefix_path = f"campaigns/camp_{campaign_id}/attempts"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "attempt" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if not matching_path or not (self.engine.dojo_dir / matching_path).exists():
            return None
        try:
            return self.engine.read_markdown_file(matching_path, Attempt, "user_answer")
        except Exception as e:
            self.engine.logger.error(f"Error reading attempt {id}: {e}")
            return None

    def save_attempt(self, campaign_id: str, attempt: Attempt):
        prefix_path = f"campaigns/camp_{campaign_id}/attempts"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "attempt" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == attempt.id:
                    matching_path = rel_path
                    break

        if not matching_path:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"att_{timestamp}_{attempt.exercise_id}.md"
            matching_path = f"{prefix_path}/{filename}"

        with self.engine.write_lock():
            self.engine.write_markdown_file(matching_path, attempt, "user_answer")
            self.engine.sync_index()

    def delete_attempt(self, campaign_id: str, id: str):
        prefix_path = f"campaigns/camp_{campaign_id}/attempts"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "attempt" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if matching_path:
            with self.engine.write_lock():
                self.engine.delete_file(matching_path)
                self.engine.sync_index()

    # ==========================================
    # Insights
    # ==========================================
    def list_insights(self, campaign_id: str, filters: dict[str, Any] = None) -> List[Insight]:
        self.engine.sync_index()
        prefix_path = f"campaigns/camp_{campaign_id}/insights"
        insights = []
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "insight" and rel_path.startswith(prefix_path):
                metadata = file_info.get("data", {})
                if _match_filter(metadata, filters, "insight"):
                    ins = self.get_insight(campaign_id, metadata.get("id"))
                    if ins:
                        insights.append(ins)
        return sorted(insights, key=lambda x: x.created_at)

    def get_insight(self, campaign_id: str, id: str) -> Optional[Insight]:
        prefix_path = f"campaigns/camp_{campaign_id}/insights"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "insight" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if not matching_path or not (self.engine.dojo_dir / matching_path).exists():
            return None
        try:
            return self.engine.read_markdown_file(matching_path, Insight, "description")
        except Exception as e:
            self.engine.logger.error(f"Error reading insight {id}: {e}")
            return None

    def save_insight(self, campaign_id: str, insight: Insight):
        prefix_path = f"campaigns/camp_{campaign_id}/insights"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "insight" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == insight.id:
                    matching_path = rel_path
                    break

        if not matching_path:
            filename = f"{slugify(insight.id)}.md"
            matching_path = f"{prefix_path}/{filename}"

        with self.engine.write_lock():
            self.engine.write_markdown_file(matching_path, insight, "description")
            self.engine.sync_index()

    def delete_insight(self, campaign_id: str, id: str):
        prefix_path = f"campaigns/camp_{campaign_id}/insights"
        self.engine.sync_index()
        matching_path: Optional[str] = None
        for rel_path, file_info in self.engine.index["files"].items():
            if file_info.get("type") == "insight" and rel_path.startswith(prefix_path):
                if file_info.get("data", {}).get("id") == id:
                    matching_path = rel_path
                    break

        if matching_path:
            with self.engine.write_lock():
                self.engine.delete_file(matching_path)
                self.engine.sync_index()
