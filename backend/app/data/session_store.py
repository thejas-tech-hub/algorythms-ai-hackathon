"""Minimal in-memory state store for data associated with a session key."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class SessionStore:
    """Keep short-lived session data without coupling it to FastAPI.

    This deliberately stores generic mappings only; application services own all
    business rules and decide which values belong in a session.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def get(self, session_id: str) -> dict[str, Any] | None:
        """Return a defensive copy of data for *session_id*, if it exists."""
        state = self._sessions.get(session_id)
        return deepcopy(state) if state is not None else None

    def set(self, session_id: str, state: dict[str, Any]) -> None:
        """Store a defensive copy of the caller-provided session state."""
        self._sessions[session_id] = deepcopy(state)

    def delete(self, session_id: str) -> None:
        """Discard session data when it exists."""
        self._sessions.pop(session_id, None)
