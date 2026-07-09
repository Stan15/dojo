"""The Store: git-versioned markdown as the canonical database (ADR 011).

Every entity is one human-readable/editable markdown file (YAML frontmatter +
body); identity is the frontmatter `id`, never the filename, so users can
rename files freely. An in-memory index over frontmatter keeps lookups fast;
`sync_index` reconciles it with external edits before every read path. The
on-disk format is a PUBLIC CONTRACT — changes require a fixture round-trip
test and a blueprint §5 update in the same commit.
"""

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
        """Absolute root of the data directory."""
        return self.engine.dojo_dir

    @property
    def logger(self):
        """The engine's file logger."""
        return self.engine.logger

    @property
    def index(self):
        """The engine's in-memory frontmatter index (read-only use)."""
        return self.engine.index

    def audit(self, message: str):
        """One recovery point per command boundary (ADR 011); no-op when clean."""
        self.engine.audit(message)

    # Low-level delegation for adapters and the doctor
    def sync_index(self):
        """Reconciles the index with on-disk reality (external edits/renames)."""
        self.engine.sync_index()

    def write_lock(self):
        """Process-wide write lock context manager (engine-owned)."""
        return self.engine.write_lock()

    def read_text(self, rel_path: str) -> str:
        """Raw file read, path relative to the dojo dir."""
        return self.engine.read_text(rel_path)

    def write_text(self, rel_path: str, content: str):
        """Raw file write, path relative to the dojo dir."""
        self.engine.write_text(rel_path, content)

    def delete_file(self, rel_path: str):
        """Removes one file (path relative to the dojo dir)."""
        self.engine.delete_file(rel_path)

    def read_markdown_file(self, rel_path: str, schema_cls: Type[Any], body_field: str) -> Any:
        """Parses one frontmatter+body markdown file into `schema_cls`."""
        return self.engine.read_markdown_file(rel_path, schema_cls, body_field)

    def write_markdown_file(self, rel_path: str, obj: BaseModel, body_field: str):
        """Serializes an entity to frontmatter+body markdown at `rel_path`."""
        self.engine.write_markdown_file(rel_path, obj, body_field)
