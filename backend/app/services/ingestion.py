"""Document ingestion pipeline: chunk -> embed -> upsert to Pinecone."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, List

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.services.pinecone_client import get_index

logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 100


def _build_splitter() -> RecursiveCharacterTextSplitter:
    s = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=s.CHUNK_SIZE,
        chunk_overlap=s.CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )


def _build_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    if not s.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAIEmbeddings(model=s.EMBEDDING_MODEL, api_key=s.OPENAI_API_KEY)


def _vector_id(filename: str, chunk_index: int, namespace: str) -> str:
    """Deterministic vector ID so re-ingesting the same file replaces vectors
    instead of creating duplicates."""
    raw = f"{namespace}::{filename}::{chunk_index}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()  # noqa: S324
    return f"{filename}-{chunk_index}-{digest[:8]}"


def chunk_text(text: str) -> List[str]:
    """Split raw text into overlapping chunks per app config."""
    if not text or not text.strip():
        return []
    splitter = _build_splitter()
    return splitter.split_text(text)


def ingest_document(
    *,
    text: str,
    source_filename: str,
    namespace: str = "default",
) -> int:
    """Run the full ingestion pipeline for a single document.

    Args:
        text: extracted plain text of the document.
        source_filename: original filename (stored in metadata for citation).
        namespace: Pinecone namespace; lets callers segregate corpora.

    Returns:
        Number of chunks successfully upserted.

    Raises:
        ValueError: if `text` is empty after stripping.
        RuntimeError: on embedding or Pinecone failures (caller should map to 500).
    """
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Document produced no chunks (empty after parsing)")

    logger.info(
        "Ingesting '%s' into namespace='%s': %d chunks",
        source_filename,
        namespace,
        len(chunks),
    )

    embeddings = _build_embeddings()
    try:
        vectors_raw = embeddings.embed_documents(chunks)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    if len(vectors_raw) != len(chunks):
        # Defensive: should never happen but guards against silent corruption.
        raise RuntimeError(
            f"Embedding count mismatch: got {len(vectors_raw)} vectors "
            f"for {len(chunks)} chunks"
        )

    payload: List[Dict[str, Any]] = []
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors_raw)):
        payload.append(
            {
                "id": _vector_id(source_filename, idx, namespace),
                "values": vec,
                "metadata": {
                    "source": source_filename,
                    "chunk_index": idx,
                    "namespace": namespace,
                    "text": chunk,
                    # Useful for debugging/back-tracing if needed:
                    "ingest_id": str(uuid.uuid4()),
                },
            }
        )

    index = get_index()
    upserted = 0
    try:
        for start in range(0, len(payload), UPSERT_BATCH_SIZE):
            batch = payload[start : start + UPSERT_BATCH_SIZE]
            index.upsert(vectors=batch, namespace=namespace)
            upserted += len(batch)
            logger.debug(
                "Upserted batch %d-%d of %d",
                start,
                start + len(batch),
                len(payload),
            )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Pinecone upsert failed: {exc}") from exc

    logger.info("Ingestion complete: %d vectors upserted", upserted)
    return upserted
