from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.tools.models import ToolCall
from backend.app.tools.registry import execute_tool, list_function_schemas, list_tool_definitions
from backend.app.verification.grounding import verify_answer_grounding
from backend.app.workflows.investigation import run_investigation
from backend.app.workflows.models import InvestigationRequest


def test_tool_registry_exposes_read_only_function_schemas() -> None:
    definitions = list_tool_definitions()

    # M3 function-calling contracts must stay explicit and read-only.
    tool_names = {definition.name for definition in definitions}
    assert {
        "get_incident_summary",
        "get_failed_events",
        "get_service_metrics",
        "get_trace_like_records",
    }.issubset(tool_names)
    read_only_tool_names = {
        definition.name
        for definition in definitions
        if definition.permission_level == "read_only"
    }
    assert {
        "get_incident_summary",
        "get_failed_events",
        "get_service_metrics",
        "get_trace_like_records",
    }.issubset(read_only_tool_names)
    action_tool = next(
        definition
        for definition in definitions
        if definition.name == "simulate_event_replay_plan"
    )
    assert action_tool.permission_level == "action_simulated"
    assert all(definition.arguments[0].name == "incident_id" for definition in definitions)


def test_tool_registry_exports_json_schema_function_contracts() -> None:
    schemas = list_function_schemas()

    # Function schemas should be compatible with standard tool-calling contracts.
    failed_events_schema = next(
        schema
        for schema in schemas
        if schema["name"] == "get_failed_events"
    )
    assert failed_events_schema["parameters"] == {
        "type": "object",
        "properties": {
            "incident_id": {
                "type": "string",
                "description": "",
            }
        },
        "required": ["incident_id"],
        "additionalProperties": False,
    }
    assert failed_events_schema["metadata"]["permission_level"] == "read_only"


def test_tool_execution_validates_required_arguments() -> None:
    call = ToolCall(tool_name="get_failed_events", arguments={}, reason="missing incident id")

    # Missing function arguments should fail before a tool reads sample data.
    try:
        execute_tool(call)
    except ValueError as exc:
        assert str(exc) == "Missing required argument: incident_id"
    else:
        raise AssertionError("expected tool validation to fail")


def test_tool_execution_rejects_unknown_arguments() -> None:
    call = ToolCall(
        tool_name="get_failed_events",
        arguments={"incident_id": "INC-1001", "extra": "not allowed"},
        reason="unknown argument",
    )

    # Function calls should reject arguments outside the exported schema.
    try:
        execute_tool(call)
    except ValueError as exc:
        assert str(exc) == "Unknown argument: extra"
    else:
        raise AssertionError("expected unknown argument validation to fail")


def test_agent_tools_workflow_runs_full_investigation_trace() -> None:
    result = run_investigation(
        InvestigationRequest(
            incident_id="INC-1001",
            question="why did this checkout workflow fail after retries",
            mode="agent_tools",
        )
    )

    # Agent mode should retrieve citations, call read-only tools, and verify the final answer.
    assert result.mode == "agent_tools"
    assert [call.tool_name for call in result.selected_tools] == [
        "get_incident_summary",
        "get_failed_events",
    ]
    assert result.retrieved_chunks[0].source_id == "RB-1001"
    assert any(tool.output["incident_id"] == "INC-1001" for tool in result.tool_results)
    assert result.verifier is not None
    assert result.verifier.status == "passed"
    assert "retry_count" in str(result.tool_results[1].output) or "5" in result.final_answer
    assert {span.step_name for span in result.trace}.issuperset(
        {"triage", "retrieve", "tool_select", "tool_execute:get_failed_events", "answer", "verify"}
    )


def test_summary_only_agent_workflow_does_not_call_domain_tool() -> None:
    result = run_investigation(
        InvestigationRequest(
            incident_id="INC-1001",
            question="summarize the current incident context",
            mode="agent_tools",
        )
    )

    # Summary-only questions should not force failed-event, metric, or trace tools.
    assert [call.tool_name for call in result.selected_tools] == ["get_incident_summary"]
    assert [tool.tool_name for tool in result.tool_results] == ["get_incident_summary"]
    assert result.verifier is not None
    assert result.verifier.status == "passed"


def test_verifier_fails_when_domain_tool_output_is_missing_from_answer() -> None:
    result = run_investigation(
        InvestigationRequest(
            incident_id="INC-1001",
            question="why did this checkout workflow fail after retries",
            mode="agent_tools",
        )
    )
    answer_without_domain_tool_evidence = (
        "Observed fact: checkout-workflow has workflow retry handling. "
        "Retrieved evidence: RB-1001."
    )

    verifier = verify_answer_grounding(
        final_answer=answer_without_domain_tool_evidence,
        citations=result.retrieved_chunks,
        tool_results=result.tool_results,
        require_tools=True,
    )

    # Mentioning incident summary context is not enough when a domain tool was called.
    assert verifier.status == "failed"
    assert any(
        check.name == "answer_references_tool_evidence" and not check.passed
        for check in verifier.checks
    )


def test_rag_only_baseline_keeps_tools_disabled_but_retrieval_runnable() -> None:
    result = run_investigation(
        InvestigationRequest(
            incident_id="INC-1002",
            question="why did inventory validation errors increase",
            mode="rag_only",
        )
    )

    # Baseline mode remains runnable for eval comparison and does not call sample tools.
    assert result.mode == "rag_only"
    assert result.selected_tools == []
    assert result.tool_results == []
    assert result.retrieved_chunks[0].source_id == "RB-1002"
    assert result.verifier is not None
    assert result.verifier.status == "passed"


def test_investigation_api_creates_and_reads_trace_and_answer() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/investigations",
        json={
            "incident_id": "INC-1003",
            "question": "why did notification latency spike during the queue backlog",
            "mode": "agent_tools",
        },
    )

    # The API should expose create, trace read, and final answer read contracts.
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "agent_tools"
    assert body["tool_results"][1]["tool_name"] == "get_trace_like_records"
    assert body["verifier"]["status"] == "passed"

    trace_response = client.get(f"/api/investigations/{body['trace_id']}/trace")
    assert trace_response.status_code == 200
    assert trace_response.json()["trace"][0]["step_name"] == "triage"

    answer_response = client.get(f"/api/investigations/{body['trace_id']}/answer")
    assert answer_response.status_code == 200
    assert "RB-1003" in answer_response.json()["final_answer"]


def test_tools_api_includes_function_calling_schemas() -> None:
    response = TestClient(app).get("/api/tools")

    # The public tool endpoint should expose both local definitions and SDK-shaped schemas.
    assert response.status_code == 200
    body = response.json()
    assert "tools" in body
    assert "function_schemas" in body
    failed_events_schema = next(
        schema
        for schema in body["function_schemas"]
        if schema["name"] == "get_failed_events"
    )
    assert failed_events_schema["parameters"]["additionalProperties"] is False
    assert failed_events_schema["parameters"]["required"] == ["incident_id"]


def test_investigation_api_rejects_unknown_incident() -> None:
    response = TestClient(app).post(
        "/api/investigations",
        json={
            "incident_id": "INC-9999",
            "question": "what happened",
            "mode": "agent_tools",
        },
    )

    # Unknown curated incidents should fail through the public HTTP error contract.
    assert response.status_code == 400
    assert response.json() == {"detail": "Incident not found"}
