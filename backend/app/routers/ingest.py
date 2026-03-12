"""POST /ingest — upload a document, chunk it, embed it, store in Pinecone."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import get_settings
from app.services.ingestion import ingest_document
from app.utils.parsers import (
    SUPPORTED_EXTENSIONS,
    FileParseError,
    UnsupportedFileTypeError,
    parse_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestResponse(BaseModel):
    status: str
    chunks_ingested: int
    namespace: str
    filename: str


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Unsupported file type or empty document"},
        413: {"description": "File too large"},
        500: {"description": "Internal error during embedding/upsert"},
    },
)
async def ingest(
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or MD file"),
    namespace: str = Form(default="default"),
) -> IngestResponse:
    settings = get_settings()

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file has no filename",
        )

    # Read full file into memory. With MAX_FILE_SIZE_MB capped at 20 by default
    # and a 512MB Lambda this is safe; revisit if we ever raise the limit.
    content = await file.read()
    size = len(content)

    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )

    if size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File too large: {size / (1024 * 1024):.2f} MB exceeds "
                f"limit of {settings.MAX_FILE_SIZE_MB} MB"
            ),
        )

    try:
        text = parse_file(file.filename, content)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse file: {exc}",
        ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document parsed but contained no extractable text",
        )

    try:
        n_chunks = ingest_document(
            text=text, source_filename=file.filename, namespace=namespace
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        logger.exception("Ingestion failed for %s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        ) from exc

    return IngestResponse(
        status="success",
        chunks_ingested=n_chunks,
        namespace=namespace,
        filename=file.filename,
    )


@router.get("/supported-types", tags=["ingest"])
async def supported_types() -> dict:
    """Tiny helper for the frontend to know what extensions to accept."""
    return {"supported_extensions": sorted(SUPPORTED_EXTENSIONS)}
