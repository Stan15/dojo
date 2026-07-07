from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
import yaml
from pydantic import BaseModel

from ..logger import get_logger, DEFAULT_DOJO_DIR
from ..schemas import (
    Source,
    Campaign,
    Exercise,
    Candidate,
    Attempt,
    Insight,
    PracticeSession,
    AttackPlanPhase,
)

T = TypeVar("T", bound=BaseModel)


# ==========================================
# File Lock and Git Utilities
# ==========================================

@contextmanager
def lock_directory(dojo_dir: Path):
    """Acquires an exclusive Unix file lock on dojo.lock in the Dojo root."""
    lock_file = dojo_dir / "dojo.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_file, "w")
    try:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def init_git(dojo_dir: Path):
    """Initializes git in the Dojo root directory if not present."""
    git_dir = dojo_dir / ".git"
    if not git_dir.exists():
        try:
            subprocess.run(["git", "init", "-q"], cwd=dojo_dir, check=True)
            gitignore = dojo_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text("dojo.lock\n.index.json\ndojo.log\n*.tmp\n", encoding="utf-8")
        except Exception:
            pass


def commit_git(dojo_dir: Path, message: str):
    """Adds all changes and commits them in the background if there are modifications."""
    try:
        if not (dojo_dir / ".git").exists():
            return
        subprocess.run(["git", "add", "."], cwd=dojo_dir, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=dojo_dir, capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-q", "-m", message], cwd=dojo_dir, check=True)
    except Exception:
        pass


# ==========================================
# Helpers for Markdown parsing / serialization
# ==========================================

def slugify(text: str) -> str:
    """Converts a arbitrary title into a clean filename slug."""
    text = text.lower().strip()
    text = text.replace(".", "-")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def parse_markdown(content: str) -> tuple[dict[str, Any], str]:
    """Parses raw Markdown content, extracting frontmatter YAML block and body content."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        metadata = yaml.safe_load(parts[1]) or {}
        return metadata, parts[2].strip()
    except Exception:
        return {}, content


def serialize_markdown(metadata: dict[str, Any], body: str) -> str:
    """Serializes metadata dict and body content to a standardized frontmatter Markdown format."""
    # Strict omit defaults strategy: strip out nulls, empty collections, and off-booleans
    cleaned = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, bool) and not v:
            continue
        if isinstance(v, (list, dict)) and not v:
            continue
        # Check defaults relative to schema model definition
        default_val = _get_schema_default(metadata.get("_type"), k)
        if default_val is not None and v == default_val:
            continue
        cleaned[k] = v

    # Remove temporary _type parameter used for serialization lookups
    cleaned.pop("_type", None)

    if not cleaned:
        return body

    yaml_str = yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n\n{body}"


def _get_schema_default(entity_type: str | None, key: str) -> Any:
    """Resolves standard schema default values by reflecting Pydantic models."""
    if not entity_type:
        return None
    model_map: dict[str, Type[BaseModel]] = {
        "source": Source,
        "campaign": Campaign,
        "exercise": Exercise,
        "candidate": Candidate,
        "attempt": Attempt,
        "insight": Insight,
    }
    model = model_map.get(entity_type)
    if not model:
        return None
    field = model.model_fields.get(key)
    if field and not field.is_required():
        return field.default
    return None


def _match_filter(data: dict[str, Any], filters: dict[str, Any] | None, entity_type: str | None = None) -> bool:
    """Helper to check if a parsed entity frontmatter matches a given filter dictionary."""
    if not filters:
        return True
    for k, v in filters.items():
        val = data.get(k)
        if val is None:
            # Fall back to schema defaults
            val = _get_schema_default(entity_type, k)
        if val != v:
            return False
    return True


# ==========================================
# Low-level Storage Engine
# ==========================================

class StorageEngine:
    def __init__(self, dojo_dir: str | Path | None = None):
        self.dojo_dir = Path(dojo_dir or DEFAULT_DOJO_DIR).resolve()
        self.index_file = self.dojo_dir / ".index.json"
        self.logger = get_logger(self.dojo_dir)
        self.index: dict[str, Any] = {"files": {}}

        # Ensure directory structures
        self.dojo_dir.mkdir(parents=True, exist_ok=True)
        (self.dojo_dir / "campaigns").mkdir(exist_ok=True)
        (self.dojo_dir / "sources").mkdir(exist_ok=True)
        (self.dojo_dir / "archive" / "campaigns").mkdir(parents=True, exist_ok=True)
        (self.dojo_dir / "archive" / "sessions").mkdir(parents=True, exist_ok=True)

        self.init_git()
        self.load_index()
        self.sync_index()

    def init_git(self):
        """Initializes git in the Dojo root."""
        init_git(self.dojo_dir)

    def commit_git(self, message: str):
        """Adds all changes and commits them."""
        commit_git(self.dojo_dir, message)

    def audit(self, message: str):
        """Creates one recovery point covering everything since the last one.

        Entity writes never auto-commit (ADR 011): callers mark command
        boundaries explicitly — the CLI after each command, API users whenever
        they want a recovery point. No-op when nothing changed.
        """
        with self.write_lock():
            commit_git(self.dojo_dir, message)

    @contextmanager
    def write_lock(self):
        """Acquires lock for execution block."""
        with lock_directory(self.dojo_dir):
            yield

    def read_text(self, rel_path: str) -> str:
        """Reads a file relative to Dojo root."""
        return (self.dojo_dir / rel_path).read_text(encoding="utf-8")

    def write_text(self, rel_path: str, content: str):
        """Writes a file atomically relative to Dojo root."""
        filepath = self.dojo_dir / rel_path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = filepath.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, filepath)
        if hasattr(self, "index") and "files" in self.index and rel_path in self.index["files"]:
            del self.index["files"][rel_path]

    def delete_file(self, rel_path: str):
        """Deletes a file relative to Dojo root if it exists."""
        filepath = self.dojo_dir / rel_path
        if filepath.exists():
            filepath.unlink()
        if hasattr(self, "index") and "files" in self.index and rel_path in self.index["files"]:
            del self.index["files"][rel_path]

    def read_markdown_file(self, rel_path: str, schema_cls: Type[T], body_field: str) -> T:
        """Parses a Markdown file into a Pydantic model."""
        content = self.read_text(rel_path)
        metadata, body = parse_markdown(content)
        data = dict(metadata)
        data[body_field] = body
        # Clean relative Markdown links pointing back to absolute entity references
        return schema_cls.model_validate(data)

    def write_markdown_file(self, rel_path: str, obj: BaseModel, body_field: str):
        """Serializes a Pydantic model into a Markdown file with frontmatter."""
        data = obj.model_dump(mode="json")
        body = data.pop(body_field, "") or ""
        # Store entity type as temporary serializing context parameter
        data["_type"] = self._detect_entity_type(rel_path)
        content = serialize_markdown(data, body)
        self.write_text(rel_path, content)

    def load_index(self):
        """Loads index cache from file if valid."""
        if self.index_file.exists():
            try:
                self.index = json.loads(self.index_file.read_text(encoding="utf-8"))
                if "files" not in self.index:
                    self.index = {"files": {}}
            except Exception:
                self.index = {"files": {}}
        else:
            self.index = {"files": {}}

    def save_index(self):
        """Saves current index cache to file."""
        self.write_text(".index.json", json.dumps(self.index, indent=2))

    def sync_index(self):
        """Performs incremental file scan syncing file metadata cache using mtime."""
        self.load_index()
        dirty = False
        scanned_paths = set()

        # Gather files recursively
        all_files = []
        for root, _, files in os.walk(self.dojo_dir):
            # Ignore hidden dirs like .git
            if "/." in root or root.endswith("/."):
                continue
            for f in files:
                if f.startswith("."):
                    continue
                path = Path(root) / f
                rel = str(path.relative_to(self.dojo_dir))
                if rel in {".index.json", "dojo.lock", "dojo.log", "config.yaml", "active_session.json"} or rel.startswith("connectors/"):
                    continue
                all_files.append((rel, path))

        for rel, path in all_files:
            scanned_paths.add(rel)
            stat = path.stat()
            mtime = stat.st_mtime
            
            # Check cached value
            cached = self.index["files"].get(rel)
            if not cached or cached.get("mtime") != mtime:
                ent_type = self._detect_entity_type(rel)
                if ent_type:
                    try:
                        # Extract frontmatter metadata
                        metadata, _ = parse_markdown(path.read_text(encoding="utf-8"))
                        self.index["files"][rel] = {
                            "mtime": mtime,
                            "type": ent_type,
                            "data": metadata
                        }
                        dirty = True
                    except Exception:
                        pass

        # Prune deleted files
        for rel in list(self.index["files"].keys()):
            if rel not in scanned_paths:
                del self.index["files"][rel]
                dirty = True

        if dirty:
            self.save_index()

    def _detect_entity_type(self, rel_path: str) -> str | None:
        """Determines domain entity classification from relative filepath structure."""
        parts = rel_path.split("/")
        if len(parts) == 2 and parts[0] == "sources":
            return "source"
        if len(parts) >= 3 and parts[0] == "campaigns":
            # campaigns/camp_name/sub/...
            sub = parts[2]
            if len(parts) == 3 and sub == "campaign.md":
                return "campaign"
            if len(parts) == 4:
                mapping = {
                    "exercises": "exercise",
                    "candidates": "candidate",
                    "attempts": "attempt",
                    "insights": "insight"
                }
                return mapping.get(sub)
        if len(parts) >= 4 and parts[0] == "archive" and parts[1] == "campaigns":
            sub = parts[3]
            if len(parts) == 4 and sub == "campaign.md":
                return "campaign"
            if len(parts) == 5:
                mapping = {
                    "exercises": "exercise",
                    "candidates": "candidate",
                    "attempts": "attempt",
                    "insights": "insight"
                }
                return mapping.get(sub)
        return None

    def query_index(self, entity_type: str, filters: dict[str, Any] = None) -> list[dict[str, Any]]:
        """Queries the in-memory metadata index cache for matching files."""
        self.sync_index()
        results = []
        for rel_path, info in self.index["files"].items():
            if info["type"] == entity_type:
                meta = info["data"]
                if _match_filter(meta, filters, entity_type):
                    results.append({
                        "path": rel_path,
                        "data": meta
                    })
        return results
