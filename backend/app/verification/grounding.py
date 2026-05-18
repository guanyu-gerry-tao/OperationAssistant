from backend.app.retrieval.models import ScoredChunk
from backend.app.tools.models import ToolResult
from backend.app.verification.models import VerificationCheck, VerificationResult


def verify_answer_grounding(
    *,
    final_answer: str,
    citations: list[ScoredChunk],
    tool_results: list[ToolResult],
    require_tools: bool,
) -> VerificationResult:
    """Check whether the answer references retrieved citations and tool evidence."""

    checks = [
        _check_has_citations(citations),
        _check_answer_references_citation(final_answer, citations),
    ]
    if require_tools:
        checks.append(_check_has_tool_outputs(tool_results))
        checks.append(_check_answer_references_tool_evidence(final_answer, tool_results))

    # Product verifier is a runtime guardrail-like check, not a full offline eval judge.
    grounded = all(check.passed for check in checks)
    return VerificationResult(
        status="passed" if grounded else "failed",
        grounded=grounded,
        checks=checks,
    )


def _check_has_citations(citations: list[ScoredChunk]) -> VerificationCheck:
    """Verify that retrieval supplied at least one citation-bearing chunk."""

    passed = len(citations) > 0
    return VerificationCheck(
        name="has_citations",
        passed=passed,
        detail="retrieved citation chunks are present" if passed else "no citation chunks were retrieved",
    )


def _check_answer_references_citation(final_answer: str, citations: list[ScoredChunk]) -> VerificationCheck:
    """Verify that the answer names a retrieved source id."""

    source_ids = {chunk.source_id for chunk in citations}
    passed = any(source_id in final_answer for source_id in source_ids)
    return VerificationCheck(
        name="answer_references_citation",
        passed=passed,
        detail="answer references a retrieved source id" if passed else "answer does not name a retrieved source id",
    )


def _check_has_tool_outputs(tool_results: list[ToolResult]) -> VerificationCheck:
    """Verify that tool-assisted mode produced at least one tool output."""

    passed = len(tool_results) > 0
    return VerificationCheck(
        name="has_tool_outputs",
        passed=passed,
        detail="read-only tool outputs are present" if passed else "no read-only tool outputs were captured",
    )


def _check_answer_references_tool_evidence(
    final_answer: str,
    tool_results: list[ToolResult],
) -> VerificationCheck:
    """Verify that the answer mentions at least one high-signal tool output value."""

    evidence_terms = []
    for result in tool_results:
        evidence_terms.extend(_extract_output_terms(result))

    passed = any(term and term in final_answer for term in evidence_terms)
    return VerificationCheck(
        name="answer_references_tool_evidence",
        passed=passed,
        detail="answer references a tool output value" if passed else "answer does not cite a tool output value",
    )


def _extract_output_terms(result: ToolResult) -> list[str]:
    """Extract deterministic terms that can be checked inside the final answer."""

    if result.tool_name == "get_incident_summary":
        return [str(result.output.get("service", "")), str(result.output.get("likely_area", ""))]

    terms = []
    for record in result.output.get("records", []):
        for value in record.get("payload", {}).values():
            terms.append(str(value))
    return terms
