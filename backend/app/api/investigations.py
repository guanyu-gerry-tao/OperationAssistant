from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.tools.registry import list_function_schemas, list_tool_definitions
from backend.app.workflows.investigation import investigation_to_dict, run_investigation
from backend.app.workflows.models import InvestigationRequest
from backend.app.workflows.store import get_investigation, save_investigation


router = APIRouter(prefix="/api", tags=["investigations"])


class InvestigationCreateRequest(BaseModel):
    """Request body for a synchronous M3 investigation run."""

    incident_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    mode: Literal["rag_only", "agent_tools"] = "agent_tools"
    top_k: int = Field(default=3, ge=1, le=10)


@router.get("/tools")
def read_tool_schemas() -> dict[str, object]:
    """Return read-only tool schemas used by the function-calling workflow."""

    return {
        "tools": [asdict(definition) for definition in list_tool_definitions()],
        "function_schemas": list_function_schemas(),
    }


@router.post("/investigations")
def create_investigation(payload: InvestigationCreateRequest) -> dict[str, object]:
    """Run an investigation immediately and store its trace for follow-up reads."""

    try:
        result = run_investigation(
            InvestigationRequest(
                incident_id=payload.incident_id,
                question=payload.question,
                mode=payload.mode,
                top_k=payload.top_k,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_investigation(result)
    return investigation_to_dict(result)


@router.get("/investigations/{trace_id}")
def read_investigation(trace_id: str) -> dict[str, object]:
    """Return one previously executed investigation result."""

    result = get_investigation(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation_to_dict(result)


@router.get("/investigations/{trace_id}/trace")
def read_investigation_trace(trace_id: str) -> dict[str, object]:
    """Return only the trace spans for a previously executed investigation."""

    result = get_investigation(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"trace_id": trace_id, "trace": [asdict(span) for span in result.trace]}


@router.get("/investigations/{trace_id}/answer")
def read_investigation_answer(
    trace_id: str,
    include_verifier: bool = Query(True),
) -> dict[str, object]:
    """Return the final answer and optional product verifier result."""

    result = get_investigation(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    response: dict[str, object] = {
        "trace_id": trace_id,
        "final_answer": result.final_answer,
    }
    if include_verifier:
        response["verifier"] = asdict(result.verifier) if result.verifier is not None else None
    return response
