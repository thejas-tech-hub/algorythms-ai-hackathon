"""Tests for local curriculum retrieval."""

from __future__ import annotations

import pytest

from app.data.candidate_loader import load_curriculum
from app.models.retrieval import CurriculumRetrievalResult
from app.services.curriculum_retrieval import CurriculumRetriever, LocalCurriculumRetriever


@pytest.fixture()
def retriever() -> LocalCurriculumRetriever:
    return LocalCurriculumRetriever()


def test_curriculum_loader_reads_31_day_source_of_truth() -> None:
    curriculum = load_curriculum()

    assert len(curriculum) == 31
    assert [topic.day for topic in curriculum] == list(range(1, 32))
    assert curriculum[0].title == "VS Code & Python Environment Setup"
    assert curriculum[-1].title == "Capstone Project & Final Demo"


def test_retriever_exposes_replaceable_interface(retriever: LocalCurriculumRetriever) -> None:
    service: CurriculumRetriever = retriever

    result = service.retrieve_by_day(10)

    assert isinstance(result, CurriculumRetrievalResult)
    assert result is not None
    assert result.day == 10


def test_documents_represent_each_curriculum_day(retriever: LocalCurriculumRetriever) -> None:
    documents = retriever.documents

    assert len(documents) == 31
    assert documents[9].day == 10
    assert documents[9].title == "The Retrieval & Matching Engine"
    assert documents[9].type == "SHIP_IT"
    assert "ChromaDB" in documents[9].tools
    assert any("semantic retrieval" in objective for objective in documents[9].objectives)


def test_retrieve_by_day_returns_structured_exact_match(retriever: LocalCurriculumRetriever) -> None:
    result = retriever.retrieve_by_day(16)

    assert result is not None
    assert result.day == 16
    assert result.title == "Chatbot Backend & API Integration"
    assert "FastAPI" in result.tools
    assert result.objectives
    assert result.relevance.match_type == "day"
    assert result.relevance.matched_fields == {"day": ["16"]}


def test_retrieve_by_missing_day_returns_none(retriever: LocalCurriculumRetriever) -> None:
    assert retriever.retrieve_by_day(99) is None


def test_retrieve_by_title_prioritizes_matching_topic(retriever: LocalCurriculumRetriever) -> None:
    results = retriever.retrieve_by_title("Prompt Engineering", limit=3)

    assert results
    assert results[0].day == 12
    assert results[0].title == "Prompt Engineering Fundamentals"
    assert results[0].relevance.match_type == "title"
    assert "title" in results[0].relevance.matched_fields


def test_retrieve_by_tool_returns_all_exact_tool_matches_in_day_order(
    retriever: LocalCurriculumRetriever,
) -> None:
    results = retriever.retrieve_by_tool("ChromaDB", limit=10)

    assert [result.day for result in results] == [8, 9, 10]
    assert all("ChromaDB" in result.tools for result in results)
    assert all(result.relevance.match_type == "tool" for result in results)


def test_retrieve_by_tool_is_case_insensitive(retriever: LocalCurriculumRetriever) -> None:
    results = retriever.retrieve_by_tool("fastapi", limit=10)

    assert [result.day for result in results] == [3, 16, 18, 20, 24, 26, 27, 28, 30, 31]


def test_semantic_concept_search_handles_deployment_language(
    retriever: LocalCurriculumRetriever,
) -> None:
    results = retriever.search("container orchestration deployment", limit=3)

    assert results
    assert results[0].day == 28
    assert "Docker" in results[0].tools
    assert "Kubernetes" in results[0].tools
    assert results[0].relevance.match_type == "semantic"
    assert {"docker", "kubernetes"}.issubset(set(results[0].relevance.matched_terms))


def test_semantic_concept_search_handles_grounded_rag_language(
    retriever: LocalCurriculumRetriever,
) -> None:
    results = retriever.search("grounded answers from retrieved context", limit=5)

    assert results
    assert results[0].day == 11
    assert "RAG" in results[0].title
    assert "retrieval" in results[0].relevance.matched_terms


def test_search_day_number_finds_day_without_dedicated_method(
    retriever: LocalCurriculumRetriever,
) -> None:
    results = retriever.search("day 23", limit=3)

    assert results
    assert results[0].day == 23
    assert results[0].relevance.matched_fields["day"] == ["23"]


def test_empty_queries_return_no_results(retriever: LocalCurriculumRetriever) -> None:
    assert retriever.search("") == []
    assert retriever.retrieve_by_title("   ") == []
    assert retriever.retrieve_by_tool("") == []


def test_limit_must_be_positive(retriever: LocalCurriculumRetriever) -> None:
    with pytest.raises(ValueError, match="limit"):
        retriever.search("RAG", limit=0)


def test_unknown_query_returns_no_results(retriever: LocalCurriculumRetriever) -> None:
    assert retriever.search("zzzz qqqq impossibleword") == []
