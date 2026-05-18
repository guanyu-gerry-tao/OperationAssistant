from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationCheck:
    """One product verifier check against citations or tool outputs."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationResult:
    """Groundedness verdict returned with a runtime investigation answer."""

    status: str
    grounded: bool
    checks: list[VerificationCheck]
