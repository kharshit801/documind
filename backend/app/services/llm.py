"""LangChain LCEL chain: retrieved context + question -> grounded answer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.retrieval import RetrievedChunk, similarity_search

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the question based ONLY on the "
    "provided context. If the answer is not in the context, say "
    '"I don\'t have enough information to answer that." '
    "Always be concise and cite which document the answer came from."
)

USER_PROMPT = (
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


@dataclass(frozen=True)
class SourceCitation:
    filename: str
    chunk_index: int
    score: float


@dataclass(frozen=True)
class QAResult:
    answer: str
    sources: List[SourceCitation]


def _format_context(chunks: List[RetrievedChunk]) -> str:
    """Render retrieved chunks into a single context block for the LLM.

    Each chunk is labeled with its source filename so the model can cite it
    naturally in the answer.
    """
    if not chunks:
        return "(no relevant context found)"
    parts = []
    for c in chunks:
        parts.append(
            f"[Source: {c.source} | chunk {c.chunk_index}]\n{c.text.strip()}"
        )
    return "\n\n---\n\n".join(parts)


def _build_chain():
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.0,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT),
        ]
    )
    # LCEL: prompt -> llm -> string. Stateless and Lambda-friendly.
    return prompt | llm | StrOutputParser()


def answer_question(
    *,
    question: str,
    namespace: str = "default",
    top_k: Optional[int] = None,
) -> QAResult:
    """End-to-end RAG: retrieve context, run LLM, return answer + citations."""
    chunks = similarity_search(
        question=question, namespace=namespace, top_k=top_k
    )

    if not chunks:
        # Skip the LLM call entirely - we have nothing to ground on.
        return QAResult(
            answer="I don't have enough information to answer that.",
            sources=[],
        )

    chain = _build_chain()
    context = _format_context(chunks)
    try:
        answer_text = chain.invoke({"context": context, "question": question})
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    sources = [
        SourceCitation(filename=c.source, chunk_index=c.chunk_index, score=c.score)
        for c in chunks
    ]
    return QAResult(answer=answer_text.strip(), sources=sources)
