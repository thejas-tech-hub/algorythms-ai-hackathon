"""
AI/LLM engine interface.
Owner: THEJAS

Abstract interface for all AI/LLM interactions. The interview service
depends on this contract — not on a specific LLM provider. Implement
a concrete subclass for OpenAI, Gemini, Ollama, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.logging import get_logger

logger = get_logger(__name__)


class AIEngine(ABC):
    """
    Abstract interface for AI/LLM interactions.

    All methods are async to support non-blocking LLM API calls.
    Implement a concrete subclass for your chosen LLM provider.
    """

    @abstractmethod
    async def generate_question(
        self,
        candidate_context: dict,
        conversation_history: list[dict],
        difficulty: str,
        topic: str,
    ) -> str:
        """
        Generate an interview question adapted to the candidate.

        Args:
            candidate_context: Candidate profile, missions, and signals.
            conversation_history: Previous messages in the session.
            difficulty: Current difficulty level (foundational → expert).
            topic: The curriculum topic to ask about.

        Returns:
            The generated question text.
        """
        # TODO: Implement with actual LLM call
        ...

    @abstractmethod
    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        expected_context: dict,
    ) -> dict:
        """
        Evaluate a candidate's answer and return structured feedback.

        Args:
            question: The question that was asked.
            answer: The candidate's response.
            expected_context: Ground-truth context for evaluation.

        Returns:
            Dict with keys like 'score', 'feedback', 'follow_up_needed'.
        """
        # TODO: Implement with actual LLM call
        ...

    @abstractmethod
    async def generate_summary(
        self,
        conversation_history: list[dict],
        candidate_context: dict,
    ) -> dict:
        """
        Generate a comprehensive interview summary.

        Args:
            conversation_history: Complete session message history.
            candidate_context: Candidate profile and performance data.

        Returns:
            Dict with keys like 'summary', 'strengths', 'weaknesses',
            'recommendation'.
        """
        # TODO: Implement with actual LLM call
        ...


class NoOpAIEngine(AIEngine):
    """
    Placeholder engine that returns stub responses.

    Used during development until a real LLM provider is configured.
    Logs warnings so developers know this is a placeholder.
    """

    async def generate_question(
        self,
        candidate_context: dict,
        conversation_history: list[dict],
        difficulty: str,
        topic: str,
    ) -> str:
        logger.warning("NoOpAIEngine: generate_question called — returning placeholder")
        return "[TODO] AI-generated question placeholder"

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        expected_context: dict,
    ) -> dict:
        logger.warning("NoOpAIEngine: evaluate_answer called — returning placeholder")
        return {"score": 0, "feedback": "[TODO] AI-generated evaluation placeholder"}

    async def generate_summary(
        self,
        conversation_history: list[dict],
        candidate_context: dict,
    ) -> dict:
        logger.warning("NoOpAIEngine: generate_summary called — returning placeholder")
        return {"summary": "[TODO] AI-generated summary placeholder"}
