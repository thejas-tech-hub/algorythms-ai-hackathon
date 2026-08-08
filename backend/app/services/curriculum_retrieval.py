"""Local retrieval over the 31-day curriculum.

The service exposes a small protocol that an interview planner can depend on.
The local implementation keeps the hackathon app easy to run today, while the
protocol can later be implemented by ChromaDB or another vector store.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Protocol, Sequence

from app.data.candidate_loader import CurriculumTopic
from app.data.repositories import CurriculumRepository
from app.models.retrieval import (
    CurriculumRetrievalDocument,
    CurriculumRetrievalResult,
    CurriculumRelevance,
)


class CurriculumRetriever(Protocol):
    """Replaceable interface for curriculum retrieval backends."""

    def retrieve_by_day(self, day: int) -> CurriculumRetrievalResult | None:
        """Return one exact curriculum day, if present."""

    def retrieve_by_title(self, query: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days whose title/topic matches the query."""

    def retrieve_by_tool(self, tool: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days that use the requested tool."""

    def search(self, query: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days matching a free-form semantic/concept query."""


@dataclass(frozen=True)
class _IndexedDocument:
    document: CurriculumRetrievalDocument
    field_terms: dict[str, Counter[str]]
    terms: Counter[str]
    title_text: str
    tool_texts: tuple[str, ...]


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_DAY_RE = re.compile(r"\b(?:day\s*)?([1-9]|[12][0-9]|3[01])\b", re.IGNORECASE)

_STOPWORDS = {
    "a",
    "about",
    "across",
    "add",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "based",
    "be",
    "before",
    "between",
    "build",
    "by",
    "can",
    "complete",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "over",
    "the",
    "through",
    "to",
    "using",
    "with",
}

_NO_STEM = {"bitsandbytes", "kubernetes", "pandas", "requests"}

_FIELD_WEIGHTS = {
    "day": 6.0,
    "title": 4.0,
    "tools": 3.0,
    "type": 1.5,
    "objectives": 1.0,
}

_CONCEPT_ALIASES = {
    "agent": ["agentic", "langchain", "tools", "reasoning", "workflow"],
    "agentic": ["agent", "langchain", "mcp", "tools", "orchestration"],
    "api": ["fastapi", "backend", "endpoint", "server"],
    "backend": ["fastapi", "api", "server", "sqlite"],
    "benchmark": ["evaluation", "testing", "metrics", "dataset"],
    "cache": ["caching", "performance", "latency", "cost"],
    "chat": ["chatbot", "conversation", "messages"],
    "concept": ["semantic", "topic", "objective"],
    "container": ["docker", "kubernetes", "deployment"],
    "containerization": ["docker", "kubernetes", "deployment"],
    "cost": ["token", "performance", "optimization", "caching"],
    "data": ["structured", "unstructured", "knowledge", "dataset"],
    "database": ["sqlite", "sql", "chromadb", "pinecone"],
    "deploy": ["deployment", "docker", "kubernetes", "production", "hosting"],
    "deployment": ["docker", "kubernetes", "production", "hosting"],
    "embedding": ["embeddings", "vector", "semantic", "similarity"],
    "embeddings": ["embedding", "vector", "semantic", "similarity"],
    "evaluation": ["testing", "benchmark", "metrics", "quality"],
    "frontend": ["react", "vite", "streamlit", "ui"],
    "function": ["function calling", "structured outputs", "tools", "schema"],
    "grounded": ["rag", "retrieval", "context", "citations"],
    "guardrail": ["security", "privacy", "validation", "prompt injection", "jailbreak"],
    "guardrails": ["security", "privacy", "validation", "prompt injection", "jailbreak"],
    "knowledge": ["knowledge base", "retrieval", "rag", "context"],
    "memory": ["conversation", "history", "context", "token"],
    "monitoring": ["observability", "logging", "metrics", "prometheus", "grafana"],
    "observability": ["monitoring", "logging", "metrics", "prometheus", "grafana"],
    "orchestration": ["kubernetes", "deployment", "workflow"],
    "privacy": ["security", "guardrails", "authentication", "validation"],
    "rag": ["retrieval", "grounded", "context", "knowledge", "llm"],
    "retrieval": ["rag", "semantic", "search", "context", "knowledge"],
    "search": ["retrieval", "semantic", "vector", "matching"],
    "security": ["privacy", "guardrails", "authentication", "validation"],
    "semantic": ["embedding", "embeddings", "vector", "similarity", "retrieval"],
    "streaming": ["server-sent", "sse", "tokens", "responses"],
    "structured": ["pandas", "sqlite", "sql", "pydantic", "schema"],
    "testing": ["evaluation", "benchmark", "quality", "metrics"],
    "tool": ["tools", "function", "agent"],
    "tools": ["tool", "function", "agent", "mcp"],
    "unstructured": ["pdf", "ocr", "scrape", "text extraction"],
    "vector": ["embeddings", "semantic", "similarity", "chromadb", "pinecone"],
}


class LocalCurriculumRetriever:
    """Lightweight local retrieval over curriculum day documents."""

    def __init__(
        self,
        repository: CurriculumRepository | None = None,
        topics: Sequence[CurriculumTopic] | None = None,
    ) -> None:
        source = list(topics) if topics is not None else (repository or CurriculumRepository()).list_all()
        self._documents = [self._to_document(topic) for topic in source]
        self._documents.sort(key=lambda document: document.day)

        duplicate_days = [
            day for day, count in Counter(document.day for document in self._documents).items() if count > 1
        ]
        if duplicate_days:
            raise ValueError(f"curriculum contains duplicate day values: {duplicate_days}")

        self._by_day = {document.day: document for document in self._documents}
        self._index = [self._index_document(document) for document in self._documents]
        self._idf = self._build_idf(self._index)

    @property
    def documents(self) -> list[CurriculumRetrievalDocument]:
        """Return curriculum day documents in day order."""
        return [document.model_copy(deep=True) for document in self._documents]

    def retrieve_by_day(self, day: int) -> CurriculumRetrievalResult | None:
        """Return one exact curriculum day, if present."""
        document = self._by_day.get(day)
        if document is None:
            return None
        return self._to_result(
            document=document,
            relevance=CurriculumRelevance(
                score=1.0,
                match_type="day",
                matched_terms=[str(day)],
                matched_fields={"day": [str(day)]},
                explanation=f"Exact curriculum day match for day {day}.",
            ),
        )

    def retrieve_by_title(self, query: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days whose title/topic matches the query."""
        return self._rank(query=query, limit=limit, fields=("title",), match_type="title")

    def retrieve_by_tool(self, tool: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days that use the requested tool."""
        query = tool.strip()
        if not query:
            return []
        self._validate_limit(limit)

        normalized_tool = _normalize_text(query)
        exact_matches: list[CurriculumRetrievalResult] = []
        for indexed in self._index:
            matching_tools = [
                source_tool
                for source_tool, normalized in zip(indexed.document.tools, indexed.tool_texts)
                if normalized_tool == normalized
            ]
            if not matching_tools:
                continue
            exact_matches.append(
                self._to_result(
                    indexed.document,
                    CurriculumRelevance(
                        score=1.0,
                        match_type="tool",
                        matched_terms=matching_tools,
                        matched_fields={"tools": matching_tools},
                        explanation=f"Exact tool match for {query}.",
                    ),
                )
            )

        if exact_matches:
            return exact_matches[:limit]
        return self._rank(query=query, limit=limit, fields=("tools",), match_type="tool")

    def search(self, query: str, limit: int = 5) -> list[CurriculumRetrievalResult]:
        """Return curriculum days matching a free-form semantic/concept query."""
        return self._rank(query=query, limit=limit, fields=None, match_type="semantic")

    def _rank(
        self,
        query: str,
        limit: int,
        fields: tuple[str, ...] | None,
        match_type: str,
    ) -> list[CurriculumRetrievalResult]:
        self._validate_limit(limit)
        query = query.strip()
        if not query:
            return []

        query_terms = _expanded_query_terms(query)
        if not query_terms:
            return []

        requested_day = _extract_day(query)
        scored: list[tuple[float, CurriculumRetrievalResult]] = []
        for indexed in self._index:
            score = 0.0
            matched_terms: set[str] = set()
            matched_fields: dict[str, set[str]] = defaultdict(set)

            fields_to_score = fields or tuple(indexed.field_terms)
            for term, query_weight in query_terms.items():
                for field in fields_to_score:
                    term_count = indexed.field_terms.get(field, Counter()).get(term, 0)
                    if term_count <= 0:
                        continue
                    score += query_weight * term_count * self._idf.get(term, 1.0)
                    matched_terms.add(term)
                    matched_fields[field].add(term)

            if requested_day == indexed.document.day and (fields is None or "day" in fields):
                score += 20.0
                matched_terms.add(str(requested_day))
                matched_fields["day"].add(str(requested_day))

            normalized_query = _normalize_text(query)
            if fields is None or "title" in fields:
                if normalized_query and normalized_query in indexed.title_text:
                    score += 8.0
                    matched_fields["title"].add(normalized_query)

            if score <= 0:
                continue

            result = self._to_result(
                indexed.document,
                CurriculumRelevance(
                    score=round(score, 4),
                    match_type=match_type,
                    matched_terms=sorted(matched_terms),
                    matched_fields={
                        field: sorted(terms)
                        for field, terms in sorted(matched_fields.items())
                        if terms
                    },
                    explanation=_explain_match(match_type, matched_fields),
                ),
            )
            scored.append((score, result))

        scored.sort(key=lambda item: (-item[0], item[1].day))
        return [result for _, result in scored[:limit]]

    def _index_document(self, document: CurriculumRetrievalDocument) -> _IndexedDocument:
        field_terms = {
            "day": Counter([str(document.day)]),
            "title": Counter(_tokenize(document.title)),
            "type": Counter(_tokenize(document.type)),
            "tools": Counter(_tokenize(" ".join(document.tools))),
            "objectives": Counter(_tokenize(" ".join(document.objectives))),
        }
        weighted_terms: Counter[str] = Counter()
        for field, terms in field_terms.items():
            weight = _FIELD_WEIGHTS[field]
            for term, count in terms.items():
                weighted_terms[term] += count * weight

        weighted_field_terms = {
            field: Counter({term: count * _FIELD_WEIGHTS[field] for term, count in terms.items()})
            for field, terms in field_terms.items()
        }
        return _IndexedDocument(
            document=document,
            field_terms=weighted_field_terms,
            terms=weighted_terms,
            title_text=_normalize_text(document.title),
            tool_texts=tuple(_normalize_text(tool) for tool in document.tools),
        )

    @staticmethod
    def _build_idf(index: Sequence[_IndexedDocument]) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for indexed in index:
            document_frequency.update(indexed.terms.keys())

        document_count = len(index)
        return {
            term: math.log((document_count + 1) / (frequency + 1)) + 1
            for term, frequency in document_frequency.items()
        }

    @staticmethod
    def _to_document(topic: CurriculumTopic) -> CurriculumRetrievalDocument:
        if topic.day is None:
            raise ValueError(f"curriculum topic '{topic.topic_id}' is missing a day")
        if not topic.title:
            raise ValueError(f"curriculum day {topic.day} is missing a title")
        return CurriculumRetrievalDocument(
            day=topic.day,
            title=topic.title,
            type=topic.type or "",
            tools=list(topic.tools),
            objectives=list(topic.objectives),
        )

    @staticmethod
    def _to_result(
        document: CurriculumRetrievalDocument,
        relevance: CurriculumRelevance,
    ) -> CurriculumRetrievalResult:
        return CurriculumRetrievalResult(
            day=document.day,
            title=document.title,
            type=document.type,
            tools=list(document.tools),
            objectives=list(document.objectives),
            relevance=relevance,
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1:
            raise ValueError("limit must be greater than zero")


def _extract_day(query: str) -> int | None:
    match = _DAY_RE.search(query)
    return int(match.group(1)) if match else None


def _expanded_query_terms(query: str) -> dict[str, float]:
    tokens = _tokenize(query)
    terms: dict[str, float] = {token: 1.0 for token in tokens}
    normalized_query = _normalize_text(query)

    alias_values: list[str] = []
    for alias, expansions in _CONCEPT_ALIASES.items():
        alias_tokens = _tokenize(alias)
        alias_matches = alias in normalized_query or any(token in tokens for token in alias_tokens)
        if alias_matches:
            alias_values.extend(expansions)

    for expansion in alias_values:
        for token in _tokenize(expansion):
            terms[token] = max(terms.get(token, 0.0), 0.45)

    return terms


def _tokenize(text: str) -> list[str]:
    return [
        _stem(token)
        for token in _TOKEN_RE.findall(text.casefold())
        if token not in _STOPWORDS
    ]


def _stem(token: str) -> str:
    if token in _NO_STEM:
        return token
    if len(token) > 5 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _normalize_text(text: str) -> str:
    return " ".join(_tokenize(text))


def _explain_match(match_type: str, matched_fields: dict[str, set[str]]) -> str:
    fields = ", ".join(sorted(matched_fields)) or "curriculum text"
    if match_type == "day":
        return "Exact day lookup."
    if match_type == "title":
        return f"Matched topic/title terms in {fields}."
    if match_type == "tool":
        return f"Matched tool terms in {fields}."
    return f"Matched semantic and concept terms in {fields}."
