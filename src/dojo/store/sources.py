from typing import List, Optional
from .base import BaseRepository
from ..schemas import Source

class SourceRepository(BaseRepository):
    def list(self) -> List[Source]:
        matches = self.engine.query_index("source")
        return [self.engine.read_markdown_file(m["path"], Source, "content") for m in matches]

    def get(self, id: str) -> Optional[Source]:
        rel_path = f"sources/{id}.md"
        filepath = self.engine.dojo_dir / rel_path
        if not filepath.exists():
            return None
        try:
            return self.engine.read_markdown_file(rel_path, Source, "content")
        except Exception as e:
            self.engine.logger.error(f"Error reading source {id}: {e}")
            return None

    def save(self, source: Source):
        rel_path = f"sources/{source.id}.md"
        with self.engine.write_lock():
            self.engine.write_markdown_file(rel_path, source, "content")
            self.engine.sync_index()
            self.engine.commit_git(f"Saved Source: {source.title}")

    def delete(self, id: str):
        rel_path = f"sources/{id}.md"
        with self.engine.write_lock():
            self.engine.delete_file(rel_path)
            self.engine.sync_index()
            self.engine.commit_git(f"Deleted Source: {id}")
