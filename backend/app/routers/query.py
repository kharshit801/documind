"""POST /query — answer a question by RAG over the configured Pinecone index."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.llm import answer_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    namespace: str = Field(default="default", min_length=1, max_length=200)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)


class SourceCitationModel(BaseModel):
    filename: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitationModel]


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"description": "Validation error (e.g. empty question)"},
        500: {"description": "Internal error during retrieval/LLM"},
    },
)
async def query(req: QueryRequest) -> QueryResponse:
    try:
        result = answer_question(
            question=req.question,
            namespace=req.namespace,
            top_k=req.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        logger.exception("Query failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {exc}",
        ) from exc

    return QueryResponse(
        answer=result.answer,
        sources=[
            SourceCitationModel(
                filename=s.filename,
                chunk_index=s.chunk_index,
                score=s.score,
            )
            for s in result.sources
        ],
    )
