from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel

from .engine import StorageEngine, slugify
from .sources import SourceRepository
from .campaigns import CampaignRepository
from .sessions import SessionRepository
from .configs import ConfigRepository
from .doctor import DoctorService

from ..schemas import Source, Campaign, Exercise, Candidate, Attempt, Insight, PracticeSession

class DojoStore:
    def __init__(self, dojo_dir: str | Path | None = None):
        self.engine = StorageEngine(dojo_dir)
        self.sources = SourceRepository(self.engine)
        self.campaigns = CampaignRepository(self.engine)
        self.sessions = SessionRepository(self.engine)
        self.configs = ConfigRepository(self.engine)
        self.doctor = DoctorService(self.engine)

    @property
    def dojo_dir(self) -> Path:
        return self.engine.dojo_dir

    @property
    def logger(self):
        return self.engine.logger

    @property
    def index(self):
        return self.engine.index

    def audit(self, message: str):
        """One recovery point per command boundary (ADR 011); no-op when clean."""
        self.engine.audit(message)

    # Low-level delegation (in case callers access it directly)
    def sync_index(self):
        self.engine.sync_index()

    def write_lock(self):
        return self.engine.write_lock()

    def read_text(self, rel_path: str) -> str:
        return self.engine.read_text(rel_path)

    def write_text(self, rel_path: str, content: str):
        self.engine.write_text(rel_path, content)

    def delete_file(self, rel_path: str):
        self.engine.delete_file(rel_path)

    def read_markdown_file(self, rel_path: str, schema_cls: Type[Any], body_field: str) -> Any:
        return self.engine.read_markdown_file(rel_path, schema_cls, body_field)

    def write_markdown_file(self, rel_path: str, obj: BaseModel, body_field: str):
        self.engine.write_markdown_file(rel_path, obj, body_field)

    def _read_config(self) -> dict[str, Any]:
        return self.configs._read_config()

    def _write_config(self, config: dict[str, Any]):
        self.configs._write_config(config)

    # Source operations facade
    def list_sources(self) -> List[Source]:
        return self.sources.list()

    def get_source(self, id: str) -> Optional[Source]:
        return self.sources.get(id)

    def save_source(self, source: Source):
        self.sources.save(source)

    def delete_source(self, id: str):
        self.sources.delete(id)

    # Campaign operations facade
    def list_campaigns(self) -> List[Campaign]:
        return self.campaigns.list()

    def get_campaign(self, id: str) -> Optional[Campaign]:
        return self.campaigns.get(id)

    def save_campaign(self, campaign: Campaign):
        self.campaigns.save(campaign)

    def archive_campaign(self, id: str):
        self.campaigns.archive(id)

    # Exercise operations facade
    def list_exercises(self, campaign_id: str, filters: dict[str, Any] = None) -> List[Exercise]:
        return self.campaigns.list_exercises(campaign_id, filters)

    def get_exercise(self, campaign_id: str, id: str) -> Optional[Exercise]:
        return self.campaigns.get_exercise(campaign_id, id)

    def save_exercise(self, campaign_id: str, exercise: Exercise):
        self.campaigns.save_exercise(campaign_id, exercise)

    def delete_exercise(self, campaign_id: str, id: str):
        self.campaigns.delete_exercise(campaign_id, id)

    # Candidate operations facade
    def list_candidates(self, campaign_id: str) -> List[Candidate]:
        return self.campaigns.list_candidates(campaign_id)

    def get_candidate(self, campaign_id: str, id: str) -> Optional[Candidate]:
        return self.campaigns.get_candidate(campaign_id, id)

    def save_candidate(self, campaign_id: str, candidate: Candidate):
        self.campaigns.save_candidate(campaign_id, candidate)

    def delete_candidate(self, campaign_id: str, id: str):
        self.campaigns.delete_candidate(campaign_id, id)

    # Attempt operations facade
    def list_attempts(self, campaign_id: str) -> List[Attempt]:
        return self.campaigns.list_attempts(campaign_id)

    def get_attempt(self, campaign_id: str, id: str) -> Optional[Attempt]:
        return self.campaigns.get_attempt(campaign_id, id)

    def save_attempt(self, campaign_id: str, attempt: Attempt):
        self.campaigns.save_attempt(campaign_id, attempt)

    def delete_attempt(self, campaign_id: str, id: str):
        self.campaigns.delete_attempt(campaign_id, id)

    # Insight operations facade
    def list_insights(self, campaign_id: str, filters: dict[str, Any] = None) -> List[Insight]:
        return self.campaigns.list_insights(campaign_id, filters)

    def get_insight(self, campaign_id: str, id: str) -> Optional[Insight]:
        return self.campaigns.get_insight(campaign_id, id)

    def save_insight(self, campaign_id: str, insight: Insight):
        self.campaigns.save_insight(campaign_id, insight)

    def delete_insight(self, campaign_id: str, id: str):
        self.campaigns.delete_insight(campaign_id, id)

    # Practice Session operations facade
    def get_active_session(self) -> Optional[PracticeSession]:
        return self.sessions.get_active()

    def save_active_session(self, session: PracticeSession):
        self.sessions.save_active(session)

    def delete_active_session(self):
        self.sessions.delete_active()

    def get_archived_session(self, id: str) -> Optional[PracticeSession]:
        return self.sessions.get_archived(id)

    def save_archived_session(self, session: PracticeSession):
        self.sessions.save_archived(session)

    # Config operations facade
    def get_config(self, key: str) -> str | None:
        return self.configs.get(key)

    def set_config(self, key: str, value: str):
        self.configs.set(key, value)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self.configs.get_value(key, default)

    def set_config_value(self, key: str, value: Any):
        self.configs.set_value(key, value)

    # AI Connector operations facade
    def list_connectors(self) -> List[Dict[str, Any]]:
        return self.configs.list_connectors()

    def get_connector(self, name: str) -> Optional[Dict[str, Any]]:
        return self.configs.get_connector(name)

    def save_connector(self, name: str, data: Dict[str, Any]):
        self.configs.save_connector(name, data)

    def delete_connector(self, name: str):
        self.configs.delete_connector(name)

    # Doctor operations facade
    def run_doctor(self) -> dict[str, list[str]]:
        return self.doctor.run()
