"""Practice-session persistence: at most ONE active session (a single
`active_session.json` at the store root — practice is intentionally
single-threaded), completed sessions archived as JSON under
`archive/sessions/`. Sessions are ephemeral workflow state, not learning
evidence, so they're JSON rather than contract markdown (ADR 011 covers
entities; sessions are exempt)."""

from typing import List, Optional
from .base import BaseRepository
from ..schemas import PracticeSession

class SessionRepository(BaseRepository):
    """See module docstring; all reads log-and-return-None on corruption."""

    def get_active(self) -> Optional[PracticeSession]:
        """The one active session, or None (missing or unreadable file)."""
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
        """Overwrites the active-session slot with this session."""
        rel_path = "active_session.json"
        with self.engine.write_lock():
            self.engine.write_text(rel_path, session.model_dump_json(indent=2))

    def delete_active(self):
        """Clears the active-session slot (session completed or reset)."""
        rel_path = "active_session.json"
        with self.engine.write_lock():
            self.engine.delete_file(rel_path)

    def get_archived(self, id: str) -> Optional[PracticeSession]:
        """One archived session by id, or None."""
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
        """All archived sessions, filename order (≈ creation order);
        unreadable files logged and skipped."""
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
        """Writes (or rewrites) the session's archive file."""
        rel_path = f"archive/sessions/sess_{session.id}.json"
        with self.engine.write_lock():
            self.engine.write_text(rel_path, session.model_dump_json(indent=2))
