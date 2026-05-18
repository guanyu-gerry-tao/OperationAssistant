from dataclasses import asdict
from time import perf_counter
from uuid import uuid4

from backend.app.retrieval.loader import load_runbook_documents
from backend.app.retrieval.models import RetrievalRequest, ScoredChunk
from backend.app.retrieval.retriever import retrieve_chunks
from backend.app.seeds import get_seed_incident
from backend.app.tools.models import ToolCall, ToolResult
from backend.app.tools.registry import execute_tool
from backend.app.tracing.models import TraceSpan
from backend.app.verification.grounding import verify_answer_grounding
from backend.app.workflows.models import InvestigationRequest, InvestigationResult, InvestigationMode


SUPPORTED_INVESTIGATION_MODES = {"rag_only", "agent_tools"}


def run_investigation(request: InvestigationRequest) -> InvestigationResult:
    """Run the deterministic M3 investigation workflow for one curated incident."""

    if request.mode not in SUPPORTED_INVESTIGATION_MODES:
        raise ValueError("Unknown investigation mode")
    if request.top_k <= 0:
        raise ValueError("top_k must be positive")

    started_at = perf_counter()
    trace_id = f"trace-{uuid4().hex[:12]}"
    spans: list[TraceSpan] = []

    # Resolve curated incident context before selecting retrieval filters or tools.
    incident = get_seed_incident(request.incident_id)
    if incident is None:
        raise ValueError("Incident not found")
    _append_span(
        spans,
        trace_id=trace_id,
        parent_span_id=None,
        step_name="triage",
        input_summary=request.question,
        output_summary=f"{incident['id']} affects {incident['service']} via {incident['likely_area']}",
    )

    # Retrieve runbook evidence using the M2 improved strategy for the default path.
    retrieval_query = f"{request.question} {incident['symptom']} {incident['likely_area']}"
    retrieval_result = retrieve_chunks(
        RetrievalRequest(
            query=retrieval_query,
            strategy="hybrid_rerank_rewrite",
            top_k=request.top_k,
            metadata_filter={"service": str(incident["service"])},
        ),
        documents=load_runbook_documents(),
    )
    retrieved_chunks = retrieval_result.chunks
    _append_span(
        spans,
        trace_id=trace_id,
        parent_span_id=spans[-1].span_id,
        step_name="retrieve",
        input_summary=retrieval_query,
        output_summary=_summarize_citations(retrieved_chunks),
        latency_ms=retrieval_result.latency_ms,
    )

    # Baseline mode stops after retrieval so eval can compare tool value in the same codebase.
    selected_tools: list[ToolCall] = []
    tool_results: list[ToolResult] = []
    if request.mode == "agent_tools":
        selected_tools = _select_tools(incident=incident, question=request.question)
        _append_span(
            spans,
            trace_id=trace_id,
            parent_span_id=spans[0].span_id,
            step_name="tool_select",
            input_summary=f"{incident['service']} / {request.question}",
            output_summary=", ".join(call.tool_name for call in selected_tools),
        )
        for tool_call in selected_tools:
            tool_started_at = perf_counter()
            try:
                result = execute_tool(tool_call)
            except ValueError as exc:
                # Preserve the failed tool step in the trace before returning an API error.
                _append_span(
                    spans,
                    trace_id=trace_id,
                    parent_span_id=spans[-1].span_id,
                    step_name=f"tool_execute:{tool_call.tool_name}",
                    input_summary=str(tool_call.arguments),
                    output_summary="tool execution failed",
                    latency_ms=round((perf_counter() - tool_started_at) * 1000, 3),
                    error=str(exc),
                )
                raise
            tool_results.append(result)
            _append_span(
                spans,
                trace_id=trace_id,
                parent_span_id=spans[-1].span_id,
                step_name=f"tool_execute:{tool_call.tool_name}",
                input_summary=str(tool_call.arguments),
                output_summary=result.output_summary,
                latency_ms=round((perf_counter() - tool_started_at) * 1000, 3),
            )

    # Compose a grounded answer from retrieved sources and optional tool outputs.
    final_answer = _build_final_answer(
        incident=incident,
        question=request.question,
        mode=request.mode,  # type: ignore[arg-type]
        retrieved_chunks=retrieved_chunks,
        tool_results=tool_results,
    )
    _append_span(
        spans,
        trace_id=trace_id,
        parent_span_id=spans[0].span_id,
        step_name="answer",
        input_summary=f"{len(retrieved_chunks)} citations, {len(tool_results)} tool outputs",
        output_summary=final_answer[:220],
        token_cost_estimate=_estimate_token_cost(final_answer),
    )

    # Product verifier checks the runtime answer against citations and tool outputs.
    verifier = verify_answer_grounding(
        final_answer=final_answer,
        citations=retrieved_chunks,
        tool_results=tool_results,
        require_tools=request.mode == "agent_tools",
    )
    _append_span(
        spans,
        trace_id=trace_id,
        parent_span_id=spans[-1].span_id,
        step_name="verify",
        input_summary="runtime groundedness checks",
        output_summary=f"{verifier.status}: {len([check for check in verifier.checks if check.passed])}/{len(verifier.checks)} checks passed",
    )

    return InvestigationResult(
        trace_id=trace_id,
        incident_id=request.incident_id,
        question=request.question,
        mode=request.mode,  # type: ignore[arg-type]
        final_answer=final_answer,
        retrieved_chunks=retrieved_chunks,
        selected_tools=selected_tools,
        tool_results=tool_results,
        verifier=verifier,
        trace=spans,
        latency_ms=round((perf_counter() - started_at) * 1000, 3),
    )


def investigation_to_dict(result: InvestigationResult) -> dict[str, object]:
    """Convert a workflow result into a JSON-friendly API payload."""

    return asdict(result)


def _select_tools(*, incident: dict[str, object], question: str) -> list[ToolCall]:
    """Choose read-only tools using incident service and query signals."""

    incident_id = str(incident["id"])
    service = str(incident["service"])
    likely_area = str(incident["likely_area"])
    searchable = f"{question} {service} {likely_area}".lower()
    calls = [
        ToolCall(
            tool_name="get_incident_summary",
            arguments={"incident_id": incident_id},
            reason="Every investigation starts by grounding the incident context.",
        )
    ]

    # Summary-only requests should not inflate domain tool selection accuracy.
    if _is_summary_only_question(question):
        return calls

    # Select one domain tool so the trace explains why tool calling adds evidence.
    if any(term in searchable for term in ["workflow", "retry", "payment", "checkout"]):
        calls.append(
            ToolCall(
                tool_name="get_failed_events",
                arguments={"incident_id": incident_id},
                reason="Workflow and retry questions need failed event evidence.",
            )
        )
    elif any(term in searchable for term in ["metric", "error rate", "inventory", "feed", "validation"]):
        calls.append(
            ToolCall(
                tool_name="get_service_metrics",
                arguments={"incident_id": incident_id},
                reason="Error-rate questions need metric evidence.",
            )
        )
    elif any(term in searchable for term in ["latency", "queue", "worker", "notification"]):
        calls.append(
            ToolCall(
                tool_name="get_trace_like_records",
                arguments={"incident_id": incident_id},
                reason="Latency and queue questions need trace-like evidence.",
            )
        )

    return calls


def _is_summary_only_question(question: str) -> bool:
    """Return whether the user asks only for incident context, not domain evidence."""

    normalized_question = question.lower()
    summary_terms = ["summary", "overview", "current incident", "context"]
    evidence_terms = [
        "evidence",
        "record",
        "metric",
        "trace",
        "failed",
        "why",
        "diagnose",
        "investigate",
    ]
    has_summary_intent = any(term in normalized_question for term in summary_terms)
    has_evidence_intent = any(term in normalized_question for term in evidence_terms)
    return has_summary_intent and not has_evidence_intent


def _build_final_answer(
    *,
    incident: dict[str, object],
    question: str,
    mode: InvestigationMode,
    retrieved_chunks: list[ScoredChunk],
    tool_results: list[ToolResult],
) -> str:
    """Build a deterministic answer from citations and read-only tool evidence."""

    citation_bits = [f"{chunk.source_id} ({chunk.citation.source_path})" for chunk in retrieved_chunks]
    citation_text = "; ".join(citation_bits) if citation_bits else "no retrieved citations"
    answer_parts = [
        f"Question: {question}",
        (
            "Observed fact: {title} affects {service}; symptom is {symptom}; customer impact is {customer_impact}; likely area is {likely_area}".format(
                title=incident["title"],
                service=incident["service"],
                symptom=incident["symptom"],
                customer_impact=incident["customer_impact"],
                likely_area=incident["likely_area"],
            )
        ),
        f"Retrieved evidence: {citation_text}.",
    ]
    if retrieved_chunks:
        # Include compact snippets so the answer exposes the citation-backed facts it used.
        snippet_text = " ".join(chunk.snippet for chunk in retrieved_chunks[:2])
        answer_parts.append(f"Citation-backed note: {snippet_text}")

    if mode == "agent_tools":
        tool_summaries = "; ".join(result.output_summary for result in tool_results)
        answer_parts.append(f"Read-only tool evidence: {tool_summaries}.")
    else:
        answer_parts.append("Baseline mode did not call read-only tools, so it can only cite runbook evidence.")

    answer_parts.append(
        "Recommended next step: continue evidence gathering and prepare a remediation plan without executing any write action."
    )
    return " ".join(answer_parts)


def _append_span(
    spans: list[TraceSpan],
    *,
    trace_id: str,
    parent_span_id: str | None,
    step_name: str,
    input_summary: str,
    output_summary: str,
    latency_ms: float = 0.0,
    token_cost_estimate: float = 0.0,
    error: str | None = None,
) -> None:
    """Append one OpenTelemetry-style span to the in-memory trace."""

    spans.append(
        TraceSpan(
            trace_id=trace_id,
            span_id=f"span-{len(spans) + 1:02d}",
            parent_span_id=parent_span_id,
            step_name=step_name,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            token_cost_estimate=token_cost_estimate,
            error=error,
        )
    )


def _summarize_citations(chunks: list[ScoredChunk]) -> str:
    """Return a short trace summary for retrieved citation chunks."""

    if not chunks:
        return "no citations returned"
    return ", ".join(chunk.source_id for chunk in chunks)


def _estimate_token_cost(text: str) -> float:
    """Return a placeholder cost estimate for trace visibility without an LLM call."""

    # M3 has no provider call, so this is a deterministic placeholder for later replacement.
    estimated_tokens = max(len(text.split()), 1)
    return round(estimated_tokens * 0.000001, 6)
