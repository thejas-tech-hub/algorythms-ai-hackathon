"""
Custom exception hierarchy for the Interview Agent.
Owner: MOHAMMED

Every domain error inherits from InterviewAgentError.
Exception handlers in app/main.py map these to HTTP responses.
"""


class InterviewAgentError(Exception):
    """Base exception for all Interview Agent errors."""

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(self.message)


class CandidateNotFoundError(InterviewAgentError):
    """Raised when a candidate ID does not exist in the dataset."""

    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        super().__init__(f"Candidate '{candidate_id}' not found")


class SessionNotFoundError(InterviewAgentError):
    """Raised when a session ID does not exist."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Interview session '{session_id}' not found")


class SessionExpiredError(InterviewAgentError):
    """Raised when attempting to interact with an ended or expired session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Interview session '{session_id}' has already ended")


class AIEngineError(InterviewAgentError):
    """Raised when the AI/LLM engine encounters an error."""

    def __init__(self, detail: str = "AI engine error") -> None:
        super().__init__(f"AI Engine error: {detail}")
