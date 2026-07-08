from __future__ import annotations
from pathlib import Path
from typing import Any, Type
from pydantic import BaseModel

from .engine import StorageEngine, slugify
from .base import (
    CampaignScopedRepository,
    RootScopedRepository,
    attempt_filename,
    sequenced_filename,
    slug_filename,
)
from .campaigns import CampaignRepository
from .sessions import SessionRepository
from .configs import ConfigRepository
from .doctor import DoctorService

from ..schemas import Attempt, Candidate, Capture, Exercise, Insight, Source, Task


class DojoStore:
    """The storage root: typed repositories per entity plus command-level audit.

    Access is repository-style (`store.exercises.save(...)`) — this class adds
    no entity logic of its own (ADR 011; the old ~40-method pass-through facade
    was OPEN-PROBLEMS #6).
    """

    def __init__(self, dojo_dir: str | Path | None = None):
        self.engine = StorageEngine(dojo_dir)
        self.sources = RootScopedRepository(
            self.engine, entity_type="source", schema_cls=Source, subdir="sources",
        )
        self.tasks = RootScopedRepository(
            self.engine, entity_type="task", schema_cls=Task, subdir="tasks",
        )
        self.captures = RootScopedRepository(
            self.engine, entity_type="capture", schema_cls=Capture, subdir="inbox",
        )
        self.campaigns = CampaignRepository(self.engine)
        self.sessions = SessionRepository(self.engine)
        self.configs = ConfigRepository(self.engine)
        self.doctor = DoctorService(self.engine)

        self.exercises = CampaignScopedRepository(
            self.engine, entity_type="exercise", schema_cls=Exercise,
            subdir="exercises", new_filename=sequenced_filename,
            sort_key=lambda x: x.id,
        )
        self.candidates = CampaignScopedRepository(
            self.engine, entity_type="candidate", schema_cls=Candidate,
            subdir="candidates", new_filename=sequenced_filename,
            sort_key=lambda x: x.id,
        )
        self.attempts = CampaignScopedRepository(
            self.engine, entity_type="attempt", schema_cls=Attempt,
            subdir="attempts", new_filename=attempt_filename,
            sort_key=lambda x: x.created_at,
        )
        self.insights = CampaignScopedRepository(
            self.engine, entity_type="insight", schema_cls=Insight,
            subdir="insights", new_filename=slug_filename,
            sort_key=lambda x: x.created_at,
        )

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

    # Low-level delegation for adapters and the doctor
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
