"""Shared test fixtures for the backend test suite.

The unit tests intentionally avoid live calls to OpenAI and Pinecone. We seed
placeholder credentials here and provide the standard ``client`` fixture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure tests can `import app...` without needing PYTHONPATH gymnastics.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Seed placeholder credentials BEFORE importing the app, so that any
# Settings() construction during import succeeds without real keys.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "documind-test")
os.environ.setdefault("APP_ENV", "development")


@pytest.fixture()
def client():
    """A fresh FastAPI TestClient with cached settings reset.

    Returns a sync TestClient (httpx-backed) so tests can use a simple
    request-response style without juggling event loops.
    """
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    return TestClient(app)
