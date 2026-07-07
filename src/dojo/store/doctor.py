from typing import Any
import re
import yaml
from pathlib import Path
from pydantic import BaseModel
from .base import BaseRepository
from .engine import parse_markdown, serialize_markdown
from ..schemas import (
    Source,
    Campaign,
    Exercise,
    Candidate,
    Attempt,
    Insight,
    PracticeSession,
    AttackPlanPhase,
    Task,
)

class DoctorService(BaseRepository):
    def run(self) -> dict[str, list[str]]:
        """Runs a diagnostic check on the Dojo store repository directory structure and contents.
        Returns a dictionary mapping check names to list of validation error messages.
        """
        results = {
            "Root directory layout": [],
            "Ingested sources": [],
            "Campaigns structure": [],
            "Archived campaigns and sessions": [],
            "Task queue": [],
            "Version control audit": [],
        }
        if not self.engine.dojo_dir.exists():
            return results

        results["Version control audit"].extend(self._check_audit_health())

        # 1. Check root directory layout
        allowed_root_dirs = {"campaigns", "sources", "tasks", "archive", ".git"}
        allowed_root_files = {".index.json", "dojo.lock", "config.yaml", ".gitignore", "dojo.log", "active_session.json"}

        for p in self.engine.dojo_dir.iterdir():
            name = p.name
            if p.is_dir():
                if name not in allowed_root_dirs:
                    results["Root directory layout"].append(f"Unexpected directory at root: {name}")
            else:
                if name not in allowed_root_files:
                    results["Root directory layout"].append(f"Unexpected file at root: {name}")

        # 2. Check sources
        sources_dir = self.engine.dojo_dir / "sources"
        if sources_dir.exists():
            for p in sources_dir.iterdir():
                if p.is_dir():
                    results["Ingested sources"].append(f"Unexpected directory in sources/: {p.name}")
                elif not p.name.endswith(".md"):
                    results["Ingested sources"].append(f"Unexpected non-markdown file in sources/: {p.name}")
                else:
                    try:
                        self.engine.read_markdown_file(f"sources/{p.name}", Source, "content")
                    except Exception as e:
                        results["Ingested sources"].append(f"Invalid source file '{p.name}': {e}")

        # 2b. Check tasks
        tasks_dir = self.engine.dojo_dir / "tasks"
        if tasks_dir.exists():
            for p in tasks_dir.iterdir():
                if p.is_dir():
                    results["Task queue"].append(f"Unexpected directory in tasks/: {p.name}")
                elif not p.name.endswith(".md"):
                    results["Task queue"].append(f"Unexpected non-markdown file in tasks/: {p.name}")
                else:
                    try:
                        self.engine.read_markdown_file(f"tasks/{p.name}", Task, "prompt")
                    except Exception as e:
                        results["Task queue"].append(f"Invalid task file '{p.name}': {e}")

        # 3. Check campaigns
        campaigns_dir = self.engine.dojo_dir / "campaigns"
        if campaigns_dir.exists():
            for p in campaigns_dir.iterdir():
                if not p.is_dir():
                    results["Campaigns structure"].append(f"Unexpected file in campaigns/: {p.name}")
                elif not p.name.startswith("camp_"):
                    results["Campaigns structure"].append(f"Unexpected directory in campaigns/ (must start with 'camp_'): {p.name}")
                else:
                    results["Campaigns structure"].extend(self._validate_campaign_directory(p))

        # 4. Check archive
        archive_dir = self.engine.dojo_dir / "archive"
        if archive_dir.exists():
            for p in archive_dir.iterdir():
                if p.name == "campaigns" and p.is_dir():
                    for cp in p.iterdir():
                        if not cp.is_dir():
                            results["Archived campaigns and sessions"].append(f"Unexpected file in archive/campaigns/: {cp.name}")
                        elif not cp.name.startswith("camp_"):
                            results["Archived campaigns and sessions"].append(f"Unexpected directory in archive/campaigns/: {cp.name}")
                        else:
                            results["Archived campaigns and sessions"].extend(self._validate_campaign_directory(cp, is_archived=True))
                elif p.name == "sessions" and p.is_dir():
                    for sp in p.iterdir():
                        if sp.is_dir():
                            results["Archived campaigns and sessions"].append(f"Unexpected directory in archive/sessions/: {sp.name}")
                        elif not (sp.name.startswith("sess_") and sp.name.endswith(".json")):
                            results["Archived campaigns and sessions"].append(f"Unexpected file in archive/sessions/: {sp.name}")
                        else:
                            try:
                                content = sp.read_text(encoding="utf-8")
                                PracticeSession.model_validate_json(content)
                            except Exception as e:
                                results["Archived campaigns and sessions"].append(f"Invalid archived session file '{sp.name}': {e}")
                else:
                    results["Archived campaigns and sessions"].append(f"Unexpected item in archive/: {p.name}")

        return results

    def _check_audit_health(self) -> list[str]:
        """Audit commits are best-effort at command boundaries (ADR 011); this is
        where a silently failing git setup becomes visible instead of lost."""
        import subprocess

        errors = []
        if not (self.engine.dojo_dir / ".git").exists():
            # Doctor also gates installs on arbitrary/fresh directories, where a
            # missing repo is expected. It is only a problem once learning data
            # exists that isn't being protected by recovery points.
            has_content = any(
                (self.engine.dojo_dir / d).exists() and any((self.engine.dojo_dir / d).iterdir())
                for d in ("campaigns", "sources")
            )
            if has_content:
                errors.append(
                    "Store has content but no git repository — recovery points are not being recorded."
                )
            return errors
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.engine.dojo_dir, capture_output=True, text=True, timeout=10,
            )
            if status.returncode != 0:
                errors.append(f"git status failed: {status.stderr.strip()[:200]}")
            elif status.stdout.strip():
                dirty = len(status.stdout.strip().splitlines())
                errors.append(
                    f"{dirty} uncommitted change(s) in the store — a previous command's "
                    "audit commit likely failed (check git author config)."
                )
        except Exception as e:
            errors.append(f"git unavailable: {e}")
        return errors

    def _validate_campaign_directory(self, camp_dir: Path, is_archived: bool = False) -> list[str]:
        errors = []
        camp_id = camp_dir.name[5:]
        rel_prefix = f"archive/campaigns/{camp_dir.name}" if is_archived else f"campaigns/{camp_dir.name}"

        allowed_camp_files = {"campaign.md", "plan.yaml", "changelog.md"}
        allowed_camp_dirs = {"exercises", "candidates", "attempts", "insights"}

        for p in camp_dir.iterdir():
            name = p.name
            if p.is_dir():
                if name not in allowed_camp_dirs:
                    errors.append(f"Unexpected directory in {rel_prefix}/: {name}")
                else:
                    errors.extend(self._validate_camp_sub_directory(p, camp_id, name, is_archived))
            else:
                if name not in allowed_camp_files:
                    errors.append(f"Unexpected file in {rel_prefix}/: {name}")
                elif name == "campaign.md":
                    try:
                        self.engine.read_markdown_file(f"{rel_prefix}/campaign.md", Campaign, "syllabus_markdown")
                    except Exception as e:
                        errors.append(f"Invalid campaign file '{rel_prefix}/campaign.md': {e}")
                elif name == "plan.yaml":
                    try:
                        plan_data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
                        for idx, phase in enumerate(plan_data):
                            AttackPlanPhase.model_validate(phase)
                    except Exception as e:
                        errors.append(f"Invalid plan file '{rel_prefix}/plan.yaml': {e}")
                elif name == "changelog.md":
                    try:
                        meta, _ = parse_markdown(p.read_text(encoding="utf-8"))
                    except Exception as e:
                        errors.append(f"Invalid changelog file '{rel_prefix}/changelog.md': {e}")

        if not (camp_dir / "campaign.md").exists():
            errors.append(f"Missing required 'campaign.md' in {rel_prefix}/")

        return errors

    def _validate_camp_sub_directory(self, sub_dir: Path, camp_id: str, sub_name: str, is_archived: bool) -> list[str]:
        errors = []
        rel_prefix = f"archive/campaigns/camp_{camp_id}/{sub_name}" if is_archived else f"campaigns/camp_{camp_id}/{sub_name}"

        schema_map = {
            "exercises": Exercise,
            "candidates": Candidate,
            "attempts": Attempt,
            "insights": Insight,
        }

        schema_cls = schema_map[sub_name]
        body_field = schema_cls._body_field

        for p in sub_dir.iterdir():
            if p.is_dir():
                errors.append(f"Unexpected directory in {rel_prefix}/: {p.name}")
            elif not p.name.endswith(".md"):
                errors.append(f"Unexpected file in {rel_prefix}/: {p.name}")
            else:
                try:
                    rel_path = f"{rel_prefix}/{p.name}"
                    self.engine.read_markdown_file(rel_path, schema_cls, body_field)
                except Exception as e:
                    errors.append(f"Invalid file '{rel_path}': {e}")

        return errors
