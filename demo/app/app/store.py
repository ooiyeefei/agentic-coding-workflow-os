from __future__ import annotations

from dataclasses import asdict, dataclass
from secrets import token_urlsafe
from uuid import uuid4


@dataclass(slots=True)
class Note:
    id: str
    text: str


class InMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}
        self._notes_by_user: dict[str, list[Note]] = {}

    def create_session(self, user_email: str) -> str:
        session_id = token_urlsafe(24)
        self._sessions[session_id] = user_email
        self._notes_by_user.setdefault(user_email, [])
        return session_id

    def get_user(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        return self._sessions.get(session_id)

    def clear_session(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)

    def list_notes(self, user_email: str) -> list[dict[str, str]]:
        notes = self._notes_by_user.setdefault(user_email, [])
        return [asdict(note) for note in notes]

    def create_note(self, user_email: str, text: str) -> dict[str, str]:
        note = Note(id=uuid4().hex[:8], text=text)
        self._notes_by_user.setdefault(user_email, []).insert(0, note)
        return asdict(note)

    def delete_note(self, user_email: str, note_id: str) -> bool:
        notes = self._notes_by_user.setdefault(user_email, [])
        remaining = [note for note in notes if note.id != note_id]
        if len(remaining) == len(notes):
            return False
        self._notes_by_user[user_email] = remaining
        return True
