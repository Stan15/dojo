"""Repository bases and the campaign-scoped generic repository.

Exercises, candidates, attempts, and insights share identical storage physics —
a directory of markdown files under a campaign, looked up by frontmatter `id`
(never by filename: ADR 011). They differ only in schema, subdirectory, how a
new file is named, and sort order, so they are four *configurations* of one
repository, not four implementations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Generic, List, Optional, TypeVar

from pydantic import BaseModel

from .engine import StorageEngine, _match_filter, slugify

E = TypeVar("E", bound=BaseModel)


class BaseRepository:
    def __init__(self, engine: StorageEngine):
        self.engine = engine


def sequenced_filename(repo: "CampaignScopedRepository", campaign_id: str, entity: Any) -> str:
    """YYYY-MM-DD_NNNN_slug.md — sortable, human-scannable listing order."""
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = len(repo.list(campaign_id))
    return f"{date_prefix}_{existing + 1:04d}_{slugify(entity.id)}.md"


def attempt_filename(repo: "CampaignScopedRepository", campaign_id: str, entity: Any) -> str:
    """att_TIMESTAMP_exercise-id.md — evidence files read chronologically."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"att_{timestamp}_{entity.exercise_id}.md"


def slug_filename(repo: "CampaignScopedRepository", campaign_id: str, entity: Any) -> str:
    return f"{slugify(entity.id)}.md"


class CampaignScopedRepository(BaseRepository, Generic[E]):
    def __init__(
        self,
        engine: StorageEngine,
        *,
        entity_type: str,
        schema_cls: type[E],
        subdir: str,
        new_filename: Callable[["CampaignScopedRepository", str, E], str],
        sort_key: Callable[[E], Any],
    ):
        super().__init__(engine)
        self.entity_type = entity_type
        self.schema_cls = schema_cls
        self.subdir = subdir
        self.new_filename = new_filename
        self.sort_key = sort_key
        body_field = getattr(schema_cls, "_body_field", None)
        if not body_field:
            raise ValueError(f"{schema_cls.__name__} must declare _body_field")
        self.body_field: str = body_field

    def _prefix(self, campaign_id: str) -> str:
        return f"campaigns/camp_{campaign_id}/{self.subdir}"

    def _find_path(self, campaign_id: str, id: str) -> Optional[str]:
        """Identity is the frontmatter `id`; sync first so external renames and
        deletions can never serve a stale path."""
        self.engine.sync_index()
        prefix = self._prefix(campaign_id)
        for rel_path, info in self.engine.index["files"].items():
            if info.get("type") == self.entity_type and rel_path.startswith(prefix):
                if info.get("data", {}).get("id") == id:
                    return rel_path
        return None

    def list(self, campaign_id: str, filters: dict[str, Any] | None = None) -> List[E]:
        self.engine.sync_index()
        prefix = self._prefix(campaign_id)
        results: List[E] = []
        for rel_path, info in self.engine.index["files"].items():
            if info.get("type") == self.entity_type and rel_path.startswith(prefix):
                if _match_filter(info.get("data", {}), filters, self.entity_type):
                    try:
                        results.append(
                            self.engine.read_markdown_file(rel_path, self.schema_cls, self.body_field)
                        )
                    except Exception as e:
                        self.engine.logger.error(
                            f"Skipping unreadable {self.entity_type} at {rel_path}: {e}"
                        )
        return sorted(results, key=self.sort_key)

    def get(self, campaign_id: str, id: str) -> Optional[E]:
        rel_path = self._find_path(campaign_id, id)
        if not rel_path:
            return None
        try:
            return self.engine.read_markdown_file(rel_path, self.schema_cls, self.body_field)
        except Exception as e:
            self.engine.logger.error(f"Error reading {self.entity_type} {id}: {e}")
            return None

    def save(self, campaign_id: str, entity: E):
        rel_path = self._find_path(campaign_id, entity.id) or (
            f"{self._prefix(campaign_id)}/{self.new_filename(self, campaign_id, entity)}"
        )
        with self.engine.write_lock():
            self.engine.write_markdown_file(rel_path, entity, self.body_field)
            self.engine.sync_index()

    def delete(self, campaign_id: str, id: str):
        rel_path = self._find_path(campaign_id, id)
        if not rel_path:
            return
        with self.engine.write_lock():
            self.engine.delete_file(rel_path)
            self.engine.sync_index()
