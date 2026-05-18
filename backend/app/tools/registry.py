import json
from pathlib import Path
from typing import Any

from backend.app.seeds import get_seed_incident
from backend.app.tools.models import ToolArgumentSpec, ToolCall, ToolDefinition, ToolResult


SEED_TOOL_RECORDS_PATH = Path(__file__).resolve().parents[3] / "data" / "seeds" / "tool_sample_records.json"

TOOL_DEFINITIONS = {
    "get_incident_summary": ToolDefinition(
        name="get_incident_summary",
        description="Return the curated incident summary and visible impact fields.",
        permission_level="read_only",
        arguments=[
            ToolArgumentSpec(
                name="incident_id",
                argument_type="string",
                description="Curated incident id such as INC-1001.",
            )
        ],
        output_contract="incident id, title, service, symptom, impact, and likely area",
    ),
    "get_service_metrics": ToolDefinition(
        name="get_service_metrics",
        description="Return sample metric evidence for an incident.",
        permission_level="read_only",
        arguments=[
            ToolArgumentSpec(name="incident_id", argument_type="string"),
        ],
        output_contract="metric records with values and time windows",
    ),
    "get_failed_events": ToolDefinition(
        name="get_failed_events",
        description="Return sample failed workflow or event records for an incident.",
        permission_level="read_only",
        arguments=[
            ToolArgumentSpec(name="incident_id", argument_type="string"),
        ],
        output_contract="failed event records with workflow ids, errors, and retry counters",
    ),
    "get_trace_like_records": ToolDefinition(
        name="get_trace_like_records",
        description="Return sample trace-like records for latency or queue investigations.",
        permission_level="read_only",
        arguments=[
            ToolArgumentSpec(name="incident_id", argument_type="string"),
        ],
        output_contract="trace-like records with queue depth, latency, or worker state",
    ),
    "simulate_event_replay_plan": ToolDefinition(
        name="simulate_event_replay_plan",
        description="Draft a simulated replay plan for a failed event without external side effects.",
        permission_level="action_simulated",
        arguments=[
            ToolArgumentSpec(name="incident_id", argument_type="string"),
            ToolArgumentSpec(name="rationale", argument_type="string"),
        ],
        output_contract="simulated replay plan steps and approval reminder",
    ),
}


def list_tool_definitions() -> list[ToolDefinition]:
    """Return all supported read-only function-calling contracts."""

    # Sorting by name keeps API responses and tests deterministic.
    return [TOOL_DEFINITIONS[name] for name in sorted(TOOL_DEFINITIONS)]


def list_function_schemas() -> list[dict[str, Any]]:
    """Return JSON Schema compatible function-calling contracts."""

    # Expose SDK-shaped schemas while keeping the local ToolDefinition model readable.
    return [definition.to_function_schema() for definition in list_tool_definitions()]


def get_tool_definition(tool_name: str) -> ToolDefinition:
    """Return one tool definition by name."""

    definition = TOOL_DEFINITIONS.get(tool_name)
    if definition is None:
        raise ValueError("Unknown tool")
    return definition


def execute_tool(call: ToolCall, *, approval_granted: bool = False) -> ToolResult:
    """Validate and execute one read-only sample tool call."""

    # Validate schema before any tool-specific logic runs.
    definition = get_tool_definition(call.tool_name)
    _validate_tool_arguments(definition, call.arguments)

    # M4 action-like tools are simulated, but they still cannot bypass approval.
    if definition.permission_level != "read_only" and not approval_granted:
        raise ValueError("Tool requires approval")

    # Keep every M3 tool read-only and backed by local sample data.
    incident_id = str(call.arguments["incident_id"])
    if call.tool_name == "get_incident_summary":
        output = _get_incident_summary(incident_id)
    elif call.tool_name == "simulate_event_replay_plan":
        output = _build_simulated_replay_plan(incident_id, str(call.arguments["rationale"]))
    else:
        output = _get_tool_records(incident_id=incident_id, tool_name=call.tool_name)

    return ToolResult(
        tool_name=call.tool_name,
        arguments=call.arguments,
        permission_level=definition.permission_level,
        output=output,
        output_summary=_summarize_tool_output(call.tool_name, output),
    )


def _validate_tool_arguments(definition: ToolDefinition, arguments: dict[str, Any]) -> None:
    """Raise a validation error when a tool call does not match its schema."""

    allowed_names = {argument.name for argument in definition.arguments}
    for argument in definition.arguments:
        if argument.required and argument.name not in arguments:
            raise ValueError(f"Missing required argument: {argument.name}")
        if argument.name in arguments and argument.argument_type == "string":
            if not isinstance(arguments[argument.name], str) or not arguments[argument.name]:
                raise ValueError(f"Argument must be a non-empty string: {argument.name}")

    # Unknown arguments are rejected so function-calling contracts stay explicit.
    unknown_arguments = set(arguments) - allowed_names
    if unknown_arguments:
        raise ValueError(f"Unknown argument: {sorted(unknown_arguments)[0]}")


def _get_incident_summary(incident_id: str) -> dict[str, Any]:
    """Build the incident summary tool output from curated seed incidents."""

    incident = get_seed_incident(incident_id)
    if incident is None:
        raise ValueError("Incident not found")

    return {
        "incident_id": incident["id"],
        "title": incident["title"],
        "service": incident["service"],
        "severity": incident["severity"],
        "symptom": incident["symptom"],
        "customer_impact": incident["customer_impact"],
        "likely_area": incident["likely_area"],
    }


def _get_tool_records(*, incident_id: str, tool_name: str) -> dict[str, Any]:
    """Load matching sample records for a read-only evidence tool."""

    payload = json.loads(SEED_TOOL_RECORDS_PATH.read_text(encoding="utf-8"))
    records = [
        record
        for record in payload["records"]
        if record["incident_id"] == incident_id and record["tool_name"] == tool_name
    ]
    return {
        "incident_id": incident_id,
        "tool_name": tool_name,
        "records": records,
        "record_count": len(records),
    }


def _build_simulated_replay_plan(incident_id: str, rationale: str) -> dict[str, Any]:
    """Return a simulated action plan after approval has already been granted."""

    incident = get_seed_incident(incident_id)
    if incident is None:
        raise ValueError("Incident not found")

    return {
        "incident_id": incident_id,
        "tool_name": "simulate_event_replay_plan",
        "rationale": rationale,
        "simulation_only": True,
        "steps": [
            "confirm failed event id and retry budget",
            "dry-run replay against curated sample state",
            "prepare operator-facing remediation plan",
        ],
    }


def _summarize_tool_output(tool_name: str, output: dict[str, Any]) -> str:
    """Return a compact human-readable summary for trace spans and UI timelines."""

    if tool_name == "get_incident_summary":
        return "{incident_id} on {service}: {symptom}".format(**output)
    if tool_name == "simulate_event_replay_plan":
        return "simulated replay plan prepared after human approval"

    records = output.get("records", [])
    if not records:
        return f"{tool_name} returned no sample records for {output['incident_id']}."

    # Show one high-signal payload in the summary while preserving full output separately.
    first_payload = records[0]["payload"]
    if tool_name == "get_failed_events":
        return (
            "failed event {workflow_id} has {retry_count} retries and last error {last_error}".format(
                **first_payload
            )
        )
    if tool_name == "get_service_metrics":
        return "{metric} is {value} over {window}".format(**first_payload)
    if tool_name == "get_trace_like_records":
        return "queue depth {queue_depth}, p95 latency {p95_latency_ms} ms".format(**first_payload)

    return f"{tool_name} returned {len(records)} sample records."
