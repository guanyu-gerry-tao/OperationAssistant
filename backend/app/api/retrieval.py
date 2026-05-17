from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.app.retrieval.loader import load_runbook_documents
from backend.app.retrieval.retriever import RetrievalRequest, retrieve_chunks


router = APIRouter(prefix="/api", tags=["retrieval"])


@router.get("/retrieval")
def preview_retrieval(
    query: str = Query(..., min_length=1),
    strategy: Literal["lexical", "hybrid_rerank_rewrite"] | str = "hybrid_rerank_rewrite",
    top_k: int = Query(3, ge=1, le=10),
    service: str | None = None,
    incident_pattern: str | None = None,
) -> dict[str, object]:
    """Return ranked runbook chunks with citations for the investigation preview."""

    metadata_filter = {}
    if service:
        metadata_filter["service"] = service
    if incident_pattern:
        metadata_filter["incident_pattern"] = incident_pattern

    try:
        result = retrieve_chunks(
            RetrievalRequest(
                query=query,
                strategy=strategy,
                top_k=top_k,
                metadata_filter=metadata_filter,
            ),
            documents=load_runbook_documents(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(result)
