import re

from backend.app.safety.models import SafetyDecision, SafetyMode


PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore (all )?(previous|prior) instructions",
        r"ignore (the )?(above|previous|prior) instruction",
        r"reveal (the )?(hidden )?(system|developer) prompt",
        r"\bprint (the )?(developer|system) message\b",
        r"\boutput (secrets|hidden instructions)\b",
        r"\bforget (the )?(guardrails|instructions|policies)\b",
        r"disable (the )?(guardrails|safety)",
        r"jailbreak",
    ]
]

HIGH_RISK_ACTION_TERMS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b(replay|rerun|restart|rollback|roll\s+back|deploy|refund|disable|repair|purge|execute)\b",
    ]
]

AMBIGUOUS_ACTION_TERMS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bretry\b",
    ]
]

UNSAFE_ACTION_MODIFIERS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b(now|immediately|automatically)\b",
        r"\b(execute|perform|apply|do it|run it)\b",
        r"\bwithout (review|approval|waiting)\b",
        r"\b(skip|bypass) (review|approval)\b",
    ]
]

PII_PATTERNS = [
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_CARD]"),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    ("phone", re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), "[REDACTED_PHONE]"),
]


def evaluate_safety(text: str, *, safety_mode: SafetyMode) -> SafetyDecision:
    """Classify request safety and redact PII when enforcement is enabled."""

    # Detect risks independently so monitor-only mode can report every finding.
    prompt_injection_detected = any(pattern.search(text) is not None for pattern in PROMPT_INJECTION_PATTERNS)
    unsafe_request_detected = _detect_unsafe_action_request(text)
    redacted_text, pii_redactions = redact_pii(text)
    pii_detected = bool(pii_redactions)

    reasons: list[str] = []
    if prompt_injection_detected:
        reasons.append("prompt_injection")
    if unsafe_request_detected:
        reasons.append("unsafe_replay_or_action")
    if pii_detected:
        reasons.append("pii_detected")

    # Baseline mode records risk only; it intentionally does not block or redact.
    if safety_mode == "monitor_only":
        return SafetyDecision(
            mode=safety_mode,
            decision="allowed",
            original_text=text,
            redacted_text=text,
            reasons=reasons,
            prompt_injection_detected=prompt_injection_detected,
            unsafe_request_detected=unsafe_request_detected,
            pii_detected=pii_detected,
            pii_redactions=[],
        )

    # Enforcement blocks prompt injection before retrieval, tools, or traces run.
    if prompt_injection_detected:
        return SafetyDecision(
            mode=safety_mode,
            decision="blocked",
            original_text=redacted_text,
            redacted_text=redacted_text,
            reasons=reasons,
            prompt_injection_detected=prompt_injection_detected,
            unsafe_request_detected=unsafe_request_detected,
            pii_detected=pii_detected,
            pii_redactions=pii_redactions,
        )

    # Unsafe action-like requests become approval work instead of automatic execution.
    if unsafe_request_detected:
        return SafetyDecision(
            mode=safety_mode,
            decision="approval_required",
            original_text=redacted_text,
            redacted_text=redacted_text,
            reasons=reasons,
            prompt_injection_detected=prompt_injection_detected,
            unsafe_request_detected=unsafe_request_detected,
            pii_detected=pii_detected,
            pii_redactions=pii_redactions,
        )

    return SafetyDecision(
        mode=safety_mode,
        decision="allowed",
        original_text=redacted_text,
        redacted_text=redacted_text,
        reasons=reasons,
        prompt_injection_detected=prompt_injection_detected,
        unsafe_request_detected=unsafe_request_detected,
        pii_detected=pii_detected,
        pii_redactions=pii_redactions,
    )


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace supported PII patterns and return the redaction labels applied."""

    redacted_text = text
    redactions: list[str] = []
    for label, pattern, replacement in PII_PATTERNS:
        redacted_text, count = pattern.subn(replacement, redacted_text)
        if count > 0:
            redactions.append(label)
    return redacted_text, redactions


def _detect_unsafe_action_request(text: str) -> bool:
    """Return whether text asks to perform a high-risk action now."""

    normalized_text = text.strip().lower()
    starts_with_high_risk_action = re.match(
        r"^(please\s+)?(replay|rerun|restart|rollback|roll\s+back|deploy|refund|retry|disable|repair|purge|execute)\b",
        normalized_text,
    ) is not None
    asks_to_perform_high_risk_action = re.search(
        r"\b(can you|could you|please|go ahead and)\s+(replay|rerun|restart|rollback|roll\s+back|deploy|refund|retry|disable|repair|purge|execute)\b",
        normalized_text,
    ) is not None
    if starts_with_high_risk_action or asks_to_perform_high_risk_action:
        return True

    has_high_risk_action_term = any(pattern.search(text) is not None for pattern in HIGH_RISK_ACTION_TERMS)
    has_ambiguous_action_term = any(pattern.search(text) is not None for pattern in AMBIGUOUS_ACTION_TERMS)
    has_action_modifier = any(pattern.search(text) is not None for pattern in UNSAFE_ACTION_MODIFIERS)
    return (has_high_risk_action_term or has_ambiguous_action_term) and has_action_modifier
