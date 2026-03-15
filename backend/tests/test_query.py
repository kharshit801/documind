"""Tests for POST /query.

Both retrieval (Pinecone) and the LLM call are mocked.
"""

from __future__ import annotations

from typing import List

import pytest


@pytest.fixture()
def patched_retrieval_and_llm(monkeypatch):
    """Patch retrieval + LLM so /query is fully self-contained."""
    from app.services import llm as llm_module
    from app.services import retrieval as retrieval_module
    from app.services.retrieval import RetrievedChunk

    sample_chunks: List[RetrievedChunk] = [
        RetrievedChunk(
            text="The refund policy allows returns within 30 days.",
            source="policy.pdf",
            chunk_index=3,
            score=0.91,
        ),
        RetrievedChunk(
            text="Refunds are issued to the original payment method.",
            source="policy.pdf",
            chunk_index=4,
            score=0.85,
        ),
    ]

    def fake_similarity_search(*, question, namespace="default", top_k=None):
        assert question
        return sample_chunks

    class _FakeChain:
        def invoke(self, payload):
            assert "context" in payload and "question" in payload
            return (
                "The refund policy allows returns within 30 days, "
                "issued to the original payment method (policy.pdf)."
            )

    monkeypatch.setattr(retrieval_module, "similarity_search", fake_similarity_search)
    # llm_module imports `similarity_search` by name, so patch there too.
    monkeypatch.setattr(llm_module, "similarity_search", fake_similarity_search)
    monkeypatch.setattr(llm_module, "_build_chain", lambda: _FakeChain())
    return sample_chunks


@pytest.fixture()
def patched_empty_retrieval(monkeypatch):
    from app.services import llm as llm_module

    monkeypatch.setattr(llm_module, "similarity_search", lambda **_: [])

    def _no_chain():
        raise AssertionError("LLM should not be called when retrieval is empty")

    monkeypatch.setattr(llm_module, "_build_chain", _no_chain)


def test_query_success(client, patched_retrieval_and_llm):
    res = client.post(
        "/query",
        json={"question": "What is the refund policy?", "namespace": "default"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "answer" in body
    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["sources"], list) and len(body["sources"]) >= 1
    s0 = body["sources"][0]
    assert s0["filename"] == "policy.pdf"
    assert s0["chunk_index"] == 3
    assert s0["score"] == pytest.approx(0.91)


def test_query_respects_top_k(client, patched_retrieval_and_llm):
    res = client.post(
        "/query",
        json={"question": "Refunds?", "namespace": "default", "top_k": 2},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["sources"]) == 2


def test_query_empty_question_validation_error(client):
    res = client.post("/query", json={"question": "", "namespace": "default"})
    assert res.status_code == 422


def test_query_missing_question_validation_error(client):
    res = client.post("/query", json={"namespace": "default"})
    assert res.status_code == 422


def test_query_no_matches_returns_fallback(client, patched_empty_retrieval):
    res = client.post("/query", json={"question": "Anything?"})
    assert res.status_code == 200
    body = res.json()
    assert body["sources"] == []
    assert "don't have enough information" in body["answer"]
