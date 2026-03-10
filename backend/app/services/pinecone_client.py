"""Lazy Pinecone client + index accessors.

We construct the Pinecone SDK client on first use and cache it for the
lifetime of the process. On Lambda this means at most one cold-start cost
per container, with all subsequent invocations reusing the same connection.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from pinecone import Index, Pinecone

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_pinecone_client() -> "Pinecone":
    """Return a cached Pinecone SDK client."""
    from pinecone import Pinecone

    settings = get_settings()
    if not settings.PINECONE_API_KEY:
        raise RuntimeError(
            "PINECONE_API_KEY is not configured. Set it in .env or the Lambda "
            "environment before calling Pinecone."
        )
    logger.info("Initializing Pinecone client")
    return Pinecone(api_key=settings.PINECONE_API_KEY)


def get_index() -> "Index":
    """Return a handle to the configured Pinecone index.

    The index is expected to already exist (created out-of-band, e.g. via the
    Pinecone console or Terraform). We do NOT auto-create it here so that
    serverless cold-starts stay fast and so that index configuration changes
    require an explicit deployment step.
    """
    settings = get_settings()
    client = get_pinecone_client()
    return client.Index(settings.PINECONE_INDEX_NAME)
