from dataclasses import dataclass


@dataclass(frozen=True)
class TraceSpan:
    """OpenTelemetry-style span captured during one investigation workflow."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    step_name: str
    input_summary: str
    output_summary: str
    latency_ms: float
    token_cost_estimate: float
    error: str | None = None
