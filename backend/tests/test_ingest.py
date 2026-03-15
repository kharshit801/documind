"""Tests for POST /ingest.

OpenAI embeddings and Pinecone upsert are mocked — no network calls.
"""

from __future__ import annotations

import io
from typing import List
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class _FakeEmbeddings:
    """Stand-in for OpenAIEmbeddings that returns deterministic vectors."""

    def __init__(self, *args, **kwargs):
        pass

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 8 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 8


@pytest.fixture()
def patched_ingestion(monkeypatch):
    """Patch the embedding + Pinecone calls in app.services.ingestion."""
    from app.services import ingestion as ingestion_module

    fake_index = MagicMock()
    fake_index.upsert = MagicMock(return_value={"upserted_count": 0})

    monkeypatch.setattr(ingestion_module, "OpenAIEmbeddings", _FakeEmbeddings)
    monkeypatch.setattr(ingestion_module, "get_index", lambda: fake_index)
    return fake_index


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ingest_txt_success(client, patched_ingestion):
    payload = b"DocuMind makes RAG easy.\n" * 50
    files = {"file": ("notes.txt", io.BytesIO(payload), "text/plain")}
    res = client.post("/ingest", files=files, data={"namespace": "unit"})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["chunks_ingested"] >= 1
    assert body["namespace"] == "unit"
    assert body["filename"] == "notes.txt"
    assert patched_ingestion.upsert.called


def test_ingest_md_success(client, patched_ingestion):
    payload = b"# DocuMind\n\nRetrieval Augmented Generation in production.\n"
    files = {"file": ("readme.md", io.BytesIO(payload), "text/markdown")}
    res = client.post("/ingest", files=files)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["chunks_ingested"] >= 1
    assert body["namespace"] == "default"


def test_ingest_unsupported_type_returns_400(client, patched_ingestion):
    files = {
        "file": ("image.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png"),
    }
    res = client.post("/ingest", files=files)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]
    assert not patched_ingestion.upsert.called


def test_ingest_too_large_returns_413(client, patched_ingestion, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)

    big_payload = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB limit
    files = {"file": ("big.txt", io.BytesIO(big_payload), "text/plain")}
    res = client.post("/ingest", files=files)

    assert res.status_code == 413
    assert "File too large" in res.json()["detail"]
    assert not patched_ingestion.upsert.called


def test_ingest_empty_file_returns_400(client, patched_ingestion):
    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    res = client.post("/ingest", files=files)
    assert res.status_code == 400
    assert not patched_ingestion.upsert.called


def test_ingest_text_only_whitespace_returns_400(client, patched_ingestion):
    files = {"file": ("blank.txt", io.BytesIO(b"   \n\n  \t  "), "text/plain")}
    res = client.post("/ingest", files=files)
    assert res.status_code == 400
    assert not patched_ingestion.upsert.called
