from typing import List, Optional
from .base import BaseRepository
from ..schemas import Source


class SourceRepository(BaseRepository):
    def _path_for(self, id: str) -> Optional[str]:
        """Resolve a source's file by its id — identity is the id field, not the
        filename (ADR 011), so a human renaming the file must not break lookup."""
        self.engine.sync_index()
        for rel_path, info in self.engine.index["files"].items():
            if info.get("type") == "source" and info.get("data", {}).get("id") == id:
                return rel_path
        return None

    def list(self) -> List[Source]:
        matches = self.engine.query_index("source")
        return [self.engine.read_markdown_file(m["path"], Source, "content") for m in matches]

    def get(self, id: str) -> Optional[Source]:
        rel_path = self._path_for(id)
        if not rel_path:
            return None
        try:
            return self.engine.read_markdown_file(rel_path, Source, "content")
        except Exception as e:
            self.engine.logger.error(f"Error reading source {id}: {e}")
            return None

    def save(self, source: Source):
        rel_path = self._path_for(source.id) or f"sources/{source.id}.md"
        with self.engine.write_lock():
            self.engine.write_markdown_file(rel_path, source, "content")
            self.engine.sync_index()

    def delete(self, id: str):
        rel_path = self._path_for(id)
        if not rel_path:
            return
        with self.engine.write_lock():
            self.engine.delete_file(rel_path)
            self.engine.sync_index()
