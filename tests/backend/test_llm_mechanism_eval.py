import json
from pathlib import Path

import httpx


def test_openai_compatible_provider_requires_env_key(monkeypatch) -> None:
    """Real providers must read secrets from local environment boundaries only."""

    from backend.app.providers.llm import OpenAICompatibleProvider

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAICompatibleProvider(api_key_env="OPENAI_API_KEY")

    assert provider.is_configured() is False
    assert provider.safe_config_summary() == {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "configured": False,
    }


def test_openai_compatible_provider_parses_chat_completion_without_exposing_key(monkeypatch) -> None:
    """Adapter should call a real provider boundary while keeping the key out of reports."""

    from backend.app.providers.llm import ChatMessage, OpenAICompatibleProvider

    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "RB-1001 shows retry evidence from wf-checkout-7741."
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 7,
                    "total_tokens": 17,
                },
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    provider = OpenAICompatibleProvider(
        api_key_env="OPENAI_API_KEY",
        transport=httpx.MockTransport(handler),
    )

    response = provider.complete(
        model="unit-test-model",
        messages=[ChatMessage(role="user", content="Give evidence.")],
        temperature=0.0,
        timeout_seconds=5.0,
    )

    assert response.content == "RB-1001 shows retry evidence from wf-checkout-7741."
    assert response.usage.total_tokens == 17
    assert captured_headers["authorization"] == "Bearer sk-test-secret"
    assert "sk-test-secret" not in json.dumps(response.to_safe_dict())
    assert "sk-test-secret" not in json.dumps(provider.safe_config_summary())


def test_openai_compatible_provider_retries_transient_timeouts(monkeypatch) -> None:
    """Long eval runs should survive one transient provider timeout."""

    from backend.app.providers.llm import ChatMessage, OpenAICompatibleProvider

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadTimeout("temporary read timeout", request=request)
        return httpx.Response(
            status_code=200,
            json={
                "choices": [{"message": {"content": "Recovered after retry."}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    provider = OpenAICompatibleProvider(
        api_key_env="OPENAI_API_KEY",
        transport=httpx.MockTransport(handler),
        max_retries=1,
        retry_backoff_seconds=0.0,
    )

    response = provider.complete(
        model="unit-test-model",
        messages=[ChatMessage(role="user", content="Retry once.")],
        temperature=0.0,
        timeout_seconds=1.0,
    )

    assert response.content == "Recovered after retry."
    assert call_count == 2


def test_llm_eval_dry_run_writes_metrics_for_all_requested_fields(tmp_path: Path) -> None:
    """Dry-run eval should prove the runner contract without pretending to be real LLM output."""

    from scripts.eval_llm import run_llm_eval, write_llm_eval_report

    report = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="rag_tools_verifier",
        limit=4,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )
    output_paths = write_llm_eval_report(report, output_dir=tmp_path)

    assert report["provider"] == "deterministic"
    assert report["real_llm_backed"] is False
    assert report["arm"] == "rag_tools_verifier"
    assert report["case_count"] == 4
    assert report["version_snapshot"]["model_profile"] == "deterministic-local-v1"
    for metric_name in [
        "retrieval_precision",
        "citation_coverage",
        "tool_selection_accuracy",
        "tool_argument_accuracy",
        "grounded_answer_rate",
        "hallucination_proxy_rate",
        "unsafe_pass_rate",
        "pii_leak_count",
        "approval_required_rate",
        "average_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "token_usage_total",
        "estimated_cost_usd",
    ]:
        assert metric_name in report["metrics"]
    assert output_paths.json_path.exists()
    assert output_paths.markdown_path.exists()


def test_llm_eval_cli_helpers_load_model_from_local_env(tmp_path: Path, monkeypatch) -> None:
    """CLI helpers should support keeping the real model name in local .env."""

    from scripts.eval_llm import _load_local_env_file, _resolve_model

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_MODEL=gpt-test-model",
                "OPENAI_API_KEY=sk-test-secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _load_local_env_file(env_path)

    assert _resolve_model(None) == "gpt-test-model"
    assert _resolve_model("cli-model") == "cli-model"
    assert "sk-test-secret" not in json.dumps({"model": _resolve_model(None)})


def test_rag_tools_verifier_arm_records_product_verifier_separately() -> None:
    """Product verifier should be a runtime arm feature, not the offline eval judge."""

    from scripts.eval_llm import run_llm_eval

    report = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="rag_tools_verifier",
        limit=6,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )

    verifier_cases = [
        case
        for case in report["cases"]
        if case.get("product_verifier_status") is not None
    ]

    assert verifier_cases
    assert all(case["eval_judge"] for case in verifier_cases)
    assert all(case["product_verifier_status"] != "eval_judge" for case in verifier_cases)


def test_safety_and_cache_eval_arms_change_only_their_mechanism() -> None:
    """Safety and cache arms should be explicit mechanism comparisons, not quality aliases."""

    from scripts.eval_llm import run_llm_eval

    safety_monitor = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="safety_monitor_only",
        limit=6,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )
    safety_enforce = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="safety_enforce",
        limit=6,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )
    cache_off = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="cache_off",
        limit=10,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )
    cache_on = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="cache_on",
        limit=10,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )

    assert safety_monitor["metrics"]["unsafe_pass_rate"] > safety_enforce["metrics"]["unsafe_pass_rate"]
    assert cache_off["metrics"]["cache_hit_rate"] == 0.0
    assert cache_on["metrics"]["cache_hit_rate"] > 0.0
    assert cache_on["quality_claim_allowed"] is False


def test_tool_plan_prompt_includes_incident_routing_context() -> None:
    """Tool planning should include service and likely-area signals before model routing."""

    from scripts.eval_llm import _build_tool_plan_prompt

    prompt = _build_tool_plan_prompt(
        incident_id="INC-1002",
        question="why did inventory validation errors increase",
    )

    assert "service: inventory-sync" in prompt
    assert "likely_area: partner feed validation" in prompt
    assert "Use get_service_metrics for inventory-sync validation, metrics, error-rate, feed, or availability questions." in prompt


def test_tool_routing_repair_corrects_inventory_failed_events_choice() -> None:
    """Local routing policy should repair incompatible raw model choices before execution."""

    from backend.app.tools.models import ToolCall
    from scripts.eval_llm import _apply_tool_routing_policy

    raw_calls = [
        ToolCall(
            tool_name="get_incident_summary",
            arguments={"incident_id": "INC-1002"},
            reason="Ground context.",
        ),
        ToolCall(
            tool_name="get_failed_events",
            arguments={"incident_id": "INC-1002"},
            reason="The question mentions errors.",
        ),
    ]

    repaired = _apply_tool_routing_policy(
        incident_id="INC-1002",
        question="why did inventory validation errors increase",
        calls=raw_calls,
    )

    assert [call.tool_name for call in repaired] == ["get_incident_summary", "get_service_metrics"]
    assert repaired[1].reason == "Routing policy selected service metrics for inventory validation evidence."


def test_eval_limit_can_cycle_dataset_for_large_stability_runs(tmp_path: Path) -> None:
    """Large eval runs may repeat the current labeled set but must report that honestly."""

    from scripts.eval_llm import run_llm_eval

    dataset_path = tmp_path / "small_cases.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "SMALL-001",
                    "category": "retrieval",
                    "query": "checkout retry timeout",
                    "expected_sources": ["RB-1001"],
                },
                {
                    "id": "SMALL-002",
                    "category": "retrieval",
                    "query": "inventory validation errors",
                    "expected_sources": ["RB-1002"],
                },
            ]
        ),
        encoding="utf-8",
    )

    report = run_llm_eval(
        provider_name="deterministic",
        model="deterministic-local-v1",
        arm="rag_only",
        limit=5,
        dataset_path=dataset_path,
        temperature=0.0,
        timeout_seconds=5.0,
        max_cost_usd=0.25,
    )

    assert report["case_count"] == 5
    assert report["unique_case_count"] == 2
    assert report["case_repeat_mode"] == "cycled_to_limit"
    assert [case["id"] for case in report["cases"]] == [
        "SMALL-001",
        "SMALL-002",
        "SMALL-001",
        "SMALL-002",
        "SMALL-001",
    ]
