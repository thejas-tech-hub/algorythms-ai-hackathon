"""
Concrete CandidateRepository — reads from JSON files on disk.
Owner: MOHAMMED

Loads candidates.json once at startup, builds an in-memory index
for O(1) lookups by candidate ID.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.candidate import CandidateDetail
from app.core.logging import get_logger

logger = get_logger(__name__)


class JSONCandidateLoader:
    """
    Loads candidate data from a JSON file and provides lookup methods.

    Implements the CandidateRepository protocol defined in repositories.py.
    """

    def __init__(self, candidates_path: Path) -> None:
        self._path = candidates_path
        self._candidates: list[CandidateDetail] = []
        self._index: dict[str, CandidateDetail] = {}
        self._loaded: bool = False

    def load(self) -> None:
        """Read and parse the candidates JSON file into memory."""
        logger.info("Loading candidates from %s", self._path)

        if not self._path.exists():
            logger.error("Candidates file not found: %s", self._path)
            raise FileNotFoundError(f"Candidates file not found: {self._path}")

        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)

        self._candidates = [
            CandidateDetail.model_validate(entry)
            for entry in raw["candidates"]
        ]
        self._index = {c.member.id: c for c in self._candidates}
        self._loaded = True
        logger.info("Loaded %d candidates successfully", len(self._candidates))

    @property
    def is_loaded(self) -> bool:
        """Whether the data file has been loaded into memory."""
        return self._loaded

    def get_all(self) -> list[CandidateDetail]:
        """Return all candidates."""
        return self._candidates

    def get_by_id(self, candidate_id: str) -> CandidateDetail | None:
        """Return a single candidate by ID, or None if not found."""
        return self._index.get(candidate_id)
