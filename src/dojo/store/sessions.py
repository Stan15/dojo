from typing import List, Optional
from .base import BaseRepository
from ..schemas import PracticeSession

class SessionRepository(BaseRepository):
    def get_active(self) -> Optional[PracticeSession]:
        rel_path = "active_session.json"
        filepath = self.engine.dojo_dir / rel_path
        if not filepath.exists():
            return None
        try:
            return PracticeSession.model_validate_json(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            self.engine.logger.error(f"Error reading active session: {e}")
            return None

    def save_active(self, session: PracticeSession):
        rel_path = "active_session.json"
        with self.engine.write_lock():
            self.engine.write_text(rel_path, session.model_dump_json(indent=2))

    def delete_active(self):
        rel_path = "active_session.json"
        with self.engine.write_lock():
            self.engine.delete_file(rel_path)

    def get_archived(self, id: str) -> Optional[PracticeSession]:
        rel_path = f"archive/sessions/sess_{id}.json"
        filepath = self.engine.dojo_dir / rel_path
        if not filepath.exists():
            return None
        try:
            return PracticeSession.model_validate_json(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            self.engine.logger.error(f"Error reading archived session {id}: {e}")
            return None

    def list_archived(self) -> List[PracticeSession]:
        arch_dir = self.engine.dojo_dir / "archive" / "sessions"
        sessions = []
        if arch_dir.exists():
            for p in sorted(arch_dir.glob("sess_*.json")):
                try:
                    sessions.append(PracticeSession.model_validate_json(p.read_text(encoding="utf-8")))
                except Exception as e:
                    self.engine.logger.error(f"Skipping unreadable archived session {p.name}: {e}")
        return sessions

    def save_archived(self, session: PracticeSession):
        rel_path = f"archive/sessions/sess_{session.id}.json"
        with self.engine.write_lock():
            self.engine.write_text(rel_path, session.model_dump_json(indent=2))
