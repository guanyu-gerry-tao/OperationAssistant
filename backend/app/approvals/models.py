from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


ApprovalStatus = Literal["pending", "approved", "rejected"]
ApprovalPermissionLevel = Literal["read_only", "planning", "action_simulated"]


@dataclass(frozen=True)
class ApprovalAuditEntry:
    """One immutable audit event for a human approval request."""

    decision: str
    actor: str
    note: str
    created_at: str


@dataclass
class ApprovalRequest:
    """Human approval gate for an action-like simulated operation."""

    approval_id: str
    incident_id: str
    question: str
    action_type: str
    permission_level: ApprovalPermissionLevel
    risk_reason: str
    status: ApprovalStatus = "pending"
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decided_at: str | None = None
    decided_by: str | None = None
    note: str | None = None
    audit_log: list[ApprovalAuditEntry] = field(default_factory=list)
