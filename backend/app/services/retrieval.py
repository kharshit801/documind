"""Retrieval: similarity search over the Pinecone index."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from langchain_openai import OpenAIEmbeddings

from app.config import get_settings
from app.services.pinecone_client import get_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """A single chunk returned by Pinecone, normalized for downstream use."""

    text: str
    source: str
    chunk_index: int
    score: float


def _build_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    if not s.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAIEmbeddings(model=s.EMBEDDING_MODEL, api_key=s.OPENAI_API_KEY)


def similarity_search(
    *,
    question: str,
    namespace: str = "default",
    top_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    """Embed `question` and return the top-k matching chunks from Pinecone.

    Returns an empty list if the namespace is empty or no matches exist.
    """
    if not question or not question.strip():
        raise ValueError("question must be non-empty")

    settings = get_settings()
    k = top_k or settings.TOP_K_RESULTS

    embeddings = _build_embeddings()
    try:
        query_vec = embeddings.embed_query(question)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Embedding query failed: {exc}") from exc

    index = get_index()
    try:
        result = index.query(
            vector=query_vec,
            top_k=k,
            namespace=namespace,
            include_metadata=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Pinecone query failed: {exc}") from exc

    # The Pinecone SDK returns either a dict-like or an object with `.matches`
    # depending on version. Normalize both paths.
    matches = getattr(result, "matches", None)
    if matches is None and isinstance(result, dict):
        matches = result.get("matches", [])
    matches = matches or []

    chunks: List[RetrievedChunk] = []
    for m in matches:
        metadata = _get(m, "metadata") or {}
        text = metadata.get("text") or ""
        if not text:
            # Skip vectors lacking inline text; nothing useful for the LLM.
            continue
        chunks.append(
            RetrievedChunk(
                text=text,
                source=str(metadata.get("source", "unknown")),
                chunk_index=int(metadata.get("chunk_index", -1)),
                score=float(_get(m, "score") or 0.0),
            )
        )

    logger.info(
        "Retrieved %d chunks (namespace=%s, top_k=%d)", len(chunks), namespace, k
    )
    return chunks


def _get(obj, key: str):
    """Safely access a key/attr on either a dict-like or an object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
