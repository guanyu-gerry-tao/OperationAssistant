from dataclasses import dataclass, field
from typing import Literal

from backend.app.approvals.models import ApprovalRequest
from backend.app.retrieval.models import ScoredChunk
from backend.app.safety.models import SafetyDecision, SafetyMode
from backend.app.tools.models import ToolCall, ToolResult
from backend.app.tracing.models import TraceSpan
from backend.app.verification.models import VerificationResult


InvestigationMode = Literal["rag_only", "agent_tools"]


@dataclass(frozen=True)
class InvestigationRequest:
    """Inputs for one incident investigation run."""

    incident_id: str
    question: str
    mode: InvestigationMode | str = "agent_tools"
    top_k: int = 3
    safety_mode: SafetyMode = "enforce"


@dataclass(frozen=True)
class InvestigationResult:
    """Complete result returned by the investigation workflow and API."""

    trace_id: str
    incident_id: str
    question: str
    mode: InvestigationMode
    final_answer: str
    retrieved_chunks: list[ScoredChunk]
    safety_decision: SafetyDecision | None = None
    approval_request: ApprovalRequest | None = None
    selected_tools: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    verifier: VerificationResult | None = None
    trace: list[TraceSpan] = field(default_factory=list)
    latency_ms: float = 0.0
