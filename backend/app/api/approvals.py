from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.approvals.store import approval_to_dict, decide_approval_request, get_approval_request


router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalDecisionRequest(BaseModel):
    """Human decision payload for one pending approval request."""

    decided_by: str = Field(..., min_length=1)
    note: str = Field(default="", max_length=500)


@router.get("/{approval_id}")
def read_approval(approval_id: str) -> dict[str, object]:
    """Read one approval request and its audit trail."""

    approval_request = get_approval_request(approval_id)
    if approval_request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return {"approval_request": approval_to_dict(approval_request)}


@router.post("/{approval_id}/approve")
def approve_request(approval_id: str, payload: ApprovalDecisionRequest) -> dict[str, object]:
    """Approve one pending simulated action request."""

    return _decide_request(
        approval_id=approval_id,
        decision="approved",
        decided_by=payload.decided_by,
        note=payload.note,
    )


@router.post("/{approval_id}/reject")
def reject_request(approval_id: str, payload: ApprovalDecisionRequest) -> dict[str, object]:
    """Reject one pending simulated action request."""

    return _decide_request(
        approval_id=approval_id,
        decision="rejected",
        decided_by=payload.decided_by,
        note=payload.note,
    )


def _decide_request(*, approval_id: str, decision: str, decided_by: str, note: str) -> dict[str, object]:
    """Apply an approval decision and translate store errors into HTTP responses."""

    try:
        approval_request = decide_approval_request(
            approval_id=approval_id,
            decision=decision,
            decided_by=decided_by,
            note=note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"approval_request": approval_to_dict(approval_request)}
