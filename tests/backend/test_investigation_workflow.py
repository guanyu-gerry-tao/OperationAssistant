from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.tools.models import ToolCall
from backend.app.tools.registry import execute_tool, list_tool_definitions
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
    assert all(definition.permission_level == "read_only" for definition in definitions)
    assert all(definition.arguments[0].name == "incident_id" for definition in definitions)


def test_tool_execution_validates_required_arguments() -> None:
    call = ToolCall(tool_name="get_failed_events", arguments={}, reason="missing incident id")

    # Missing function arguments should fail before a tool reads sample data.
    try:
        execute_tool(call)
    except ValueError as exc:
        assert str(exc) == "Missing required argument: incident_id"
    else:
        raise AssertionError("expected tool validation to fail")


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
