from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.approvals.models import ApprovalAuditEntry, ApprovalRequest


_APPROVAL_STORE: dict[str, ApprovalRequest] = {}


def create_approval_request(
    *,
    incident_id: str,
    question: str,
    action_type: str,
    risk_reason: str,
) -> ApprovalRequest:
    """Create and store one pending human approval request."""

    approval_request = ApprovalRequest(
        approval_id=f"approval-{uuid4().hex[:12]}",
        incident_id=incident_id,
        question=question,
        action_type=action_type,
        permission_level="action_simulated",
        risk_reason=risk_reason,
    )
    approval_request.audit_log.append(
        ApprovalAuditEntry(
            decision="requested",
            actor="system",
            note=risk_reason,
            created_at=_utc_now(),
        )
    )
    _APPROVAL_STORE[approval_request.approval_id] = approval_request
    return approval_request


def get_approval_request(approval_id: str) -> ApprovalRequest | None:
    """Return one approval request from the in-memory audit store."""

    return _APPROVAL_STORE.get(approval_id)


def decide_approval_request(
    *,
    approval_id: str,
    decision: str,
    decided_by: str,
    note: str,
) -> ApprovalRequest:
    """Approve or reject a pending approval request and append an audit event."""

    approval_request = get_approval_request(approval_id)
    if approval_request is None:
        raise ValueError("Approval request not found")
    if approval_request.status != "pending":
        raise RuntimeError("Approval request already decided")
    if decision not in {"approved", "rejected"}:
        raise ValueError("Unknown approval decision")

    # Mutate only the stored request so later reads preserve the audit trail.
    approval_request.status = decision  # type: ignore[assignment]
    approval_request.decided_at = _utc_now()
    approval_request.decided_by = decided_by
    approval_request.note = note
    approval_request.audit_log.append(
        ApprovalAuditEntry(
            decision=decision,
            actor=decided_by,
            note=note,
            created_at=approval_request.decided_at,
        )
    )
    return approval_request


def approval_to_dict(approval_request: ApprovalRequest) -> dict[str, object]:
    """Convert an approval request into the public API response shape."""

    return asdict(approval_request)


def reset_approval_store() -> None:
    """Clear approval state between tests."""

    _APPROVAL_STORE.clear()


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp for audit records."""

    return datetime.now(timezone.utc).isoformat()
