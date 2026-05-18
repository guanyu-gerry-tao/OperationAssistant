from dataclasses import dataclass, field
from typing import Literal


SafetyMode = Literal["monitor_only", "enforce"]
SafetyDecisionName = Literal["allowed", "blocked", "approval_required"]


@dataclass(frozen=True)
class SafetyDecision:
    """Guardrail result for one user request before workflow execution."""

    mode: SafetyMode
    decision: SafetyDecisionName
    original_text: str
    redacted_text: str
    reasons: list[str] = field(default_factory=list)
    prompt_injection_detected: bool = False
    unsafe_request_detected: bool = False
    pii_detected: bool = False
    pii_redactions: list[str] = field(default_factory=list)
