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
