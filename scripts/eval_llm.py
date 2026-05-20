import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Allow direct execution from the repository root without installing the package.
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.cache.semantic import InMemorySemanticCache, build_semantic_cache_key
from backend.app.eval_judges.deterministic import judge_grounded_answer
from backend.app.prompts.registry import build_version_snapshot
from backend.app.providers.llm import (
    ChatMessage,
    DeterministicLLMProvider,
    LLMProviderConfigurationError,
    LLMResponse,
    OpenAICompatibleProvider,
    estimate_cost_usd,
)
from backend.app.retrieval.loader import load_runbook_documents
from backend.app.retrieval.models import RetrievalRequest, ScoredChunk
from backend.app.retrieval.retriever import retrieve_chunks
from backend.app.safety.guardrails import evaluate_safety
from backend.app.safety.models import SafetyMode
from backend.app.seeds import get_seed_incident
from backend.app.tools.models import ToolCall, ToolResult
from backend.app.tools.registry import execute_tool, list_function_schemas
from backend.app.verification.grounding import verify_answer_grounding


DATASET_PATH = REPO_ROOT / "evals" / "datasets" / "full_quality_cases.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evals" / "results" / "llm"
SUPPORTED_PROVIDERS = {"deterministic", "openai"}
SUPPORTED_ARMS = {
    "llm_only",
    "rag_only",
    "rag_tools",
    "rag_tools_verifier",
    "safety_monitor_only",
    "safety_enforce",
    "cache_off",
    "cache_on",
}
QUALITY_ARMS = {"llm_only", "rag_only", "rag_tools", "rag_tools_verifier"}
DEFAULT_LIMIT = 30


@dataclass(frozen=True)
class EvalOutputPaths:
    """Paths written by one LLM mechanism eval run."""

    json_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class ArmMechanisms:
    """Mechanism switches represented by one M5.5 eval arm."""

    use_retrieval: bool
    use_tools: bool
    use_product_verifier: bool
    safety_mode: SafetyMode
    cache_enabled: bool


def run_llm_eval(
    *,
    provider_name: str,
    model: str,
    arm: str,
    limit: int | None = DEFAULT_LIMIT,
    dataset_path: Path = DATASET_PATH,
    temperature: float = 0.0,
    timeout_seconds: float = 20.0,
    max_cost_usd: float = 1.0,
    input_cost_per_1m: float = 0.0,
    output_cost_per_1m: float = 0.0,
    api_key_env: str = "OPENAI_API_KEY",
) -> dict[str, Any]:
    """Run the M5.5 LLM-backed or dry-run mechanism eval."""

    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unknown LLM provider")
    if arm not in SUPPORTED_ARMS:
        raise ValueError("Unknown LLM eval arm")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    if max_cost_usd < 0:
        raise ValueError("max_cost_usd must be non-negative")

    provider = _build_provider(provider_name=provider_name, api_key_env=api_key_env)
    if not provider.is_configured():
        raise LLMProviderConfigurationError(
            f"{provider_name} provider is not configured; run deterministic dry-run or set {api_key_env}."
        )

    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    selected_cases = cases[:limit] if limit is not None else cases
    version_snapshot = build_version_snapshot().to_dict()
    version_snapshot["model_profile"] = model
    version_snapshot["prompt_versions"]["llm_mechanism_eval"] = "llm_mechanism_eval_v1"
    mechanisms = _resolve_arm_mechanisms(arm)
    cache = InMemorySemanticCache(records={})
    counters = _new_counters()
    details: list[dict[str, Any]] = []
    total_estimated_cost = 0.0

    for case in selected_cases:
        detail = _score_case(
            case=case,
            provider=provider,
            provider_name=provider_name,
            model=model,
            arm=arm,
            mechanisms=mechanisms,
            cache=cache,
            prompt_version=str(version_snapshot["prompt_versions"]["llm_mechanism_eval"]),
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
        )
        total_estimated_cost += float(detail.get("estimated_cost_usd", 0.0))
        if total_estimated_cost > max_cost_usd:
            detail["budget_guardrail_triggered"] = True
            details.append(detail)
            _add_detail_to_counters(counters, detail)
            break
        details.append(detail)
        _add_detail_to_counters(counters, detail)

    metrics = _format_metrics(counters)
    run_id = "llm-{arm}-{timestamp}".format(
        arm=arm,
        timestamp=datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
    )
    real_llm_backed = provider_name != "deterministic"
    return {
        "run_id": run_id,
        "run_status": "completed_real_llm_eval" if real_llm_backed else "dry_run_only",
        "real_llm_backed": real_llm_backed,
        "provider": provider_name,
        "provider_config": provider.safe_config_summary(),
        "model": model,
        "arm": arm,
        "case_count": len(details),
        "temperature": temperature,
        "timeout_seconds": timeout_seconds,
        "max_cost_usd": max_cost_usd,
        "version_snapshot": version_snapshot,
        "tool_registry_version": version_snapshot["tool_registry_version"],
        "guardrail_policy_version": version_snapshot["guardrail_policy_version"],
        "metrics": metrics,
        "quality_claim_allowed": real_llm_backed and arm in QUALITY_ARMS,
        "cases": details,
    }


def write_llm_eval_report(
    report: dict[str, Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> EvalOutputPaths:
    """Persist one LLM eval report as JSON and Markdown."""

    run_dir = output_dir / str(report["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / f"{report['arm']}.json"
    markdown_path = run_dir / f"{report['arm']}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_format_markdown_report(report), encoding="utf-8")
    return EvalOutputPaths(json_path=json_path, markdown_path=markdown_path)


def _build_provider(*, provider_name: str, api_key_env: str):
    """Create a configured provider adapter by name."""

    if provider_name == "deterministic":
        return DeterministicLLMProvider()
    if provider_name == "openai":
        return OpenAICompatibleProvider(api_key_env=api_key_env)
    raise ValueError("Unknown LLM provider")


def _resolve_arm_mechanisms(arm: str) -> ArmMechanisms:
    """Map public eval arms to mechanism toggles."""

    if arm == "llm_only":
        return ArmMechanisms(False, False, False, "enforce", False)
    if arm == "rag_only":
        return ArmMechanisms(True, False, False, "enforce", False)
    if arm == "rag_tools":
        return ArmMechanisms(True, True, False, "enforce", False)
    if arm == "rag_tools_verifier":
        return ArmMechanisms(True, True, True, "enforce", False)
    if arm == "safety_monitor_only":
        return ArmMechanisms(True, True, True, "monitor_only", False)
    if arm == "safety_enforce":
        return ArmMechanisms(True, True, True, "enforce", False)
    if arm == "cache_off":
        return ArmMechanisms(True, True, True, "enforce", False)
    if arm == "cache_on":
        return ArmMechanisms(True, True, True, "enforce", True)
    raise ValueError("Unknown LLM eval arm")


def _new_counters() -> dict[str, float | list[float]]:
    """Create aggregate counters for the LLM eval report."""

    return {
        "retrieval_count": 0.0,
        "retrieval_hits": 0.0,
        "citation_hits": 0.0,
        "tool_count": 0.0,
        "tool_selection_hits": 0.0,
        "tool_argument_hits": 0.0,
        "grounding_count": 0.0,
        "grounded_hits": 0.0,
        "hallucination_hits": 0.0,
        "safety_count": 0.0,
        "unsafe_case_count": 0.0,
        "unsafe_pass_count": 0.0,
        "pii_leak_count": 0.0,
        "approval_required_count": 0.0,
        "approval_expected_count": 0.0,
        "approval_required_hits": 0.0,
        "cache_count": 0.0,
        "cache_hits": 0.0,
        "product_verifier_count": 0.0,
        "product_verifier_passes": 0.0,
        "prompt_tokens": 0.0,
        "completion_tokens": 0.0,
        "total_tokens": 0.0,
        "estimated_cost_usd": 0.0,
        "latencies": [],
    }


def _score_case(
    *,
    case: dict[str, Any],
    provider: DeterministicLLMProvider | OpenAICompatibleProvider,
    provider_name: str,
    model: str,
    arm: str,
    mechanisms: ArmMechanisms,
    cache: InMemorySemanticCache,
    prompt_version: str,
    temperature: float,
    timeout_seconds: float,
    input_cost_per_1m: float,
    output_cost_per_1m: float,
) -> dict[str, Any]:
    """Score one labeled case using the selected mechanisms."""

    detail: dict[str, Any] = {
        "id": case["id"],
        "category": case["category"],
        "arm": arm,
    }
    incident_id = str(case.get("incident_id", _infer_incident_id(case["query"])))

    # Safety is always evaluated before prompt construction so PII does not enter provider calls.
    safety_decision = evaluate_safety(str(case["query"]), safety_mode=mechanisms.safety_mode)
    safe_query = safety_decision.redacted_text
    detail["safety_decision"] = safety_decision.decision
    detail["safety_reasons"] = safety_decision.reasons
    _score_safety_fields(case=case, safety_decision=safety_decision, detail=detail)
    if safety_decision.decision in {"blocked", "approval_required"}:
        return _score_blocked_or_approval_case(case=case, detail=detail, safety_decision=safety_decision)

    # Retrieval can be disabled for the LLM-only baseline.
    retrieved_chunks: list[ScoredChunk] = []
    if mechanisms.use_retrieval:
        retrieval_result = retrieve_chunks(
            RetrievalRequest(
                query=safe_query,
                strategy="hybrid_rerank_rewrite",
                top_k=int(case.get("top_k", 3)),
                metadata_filter=case.get("metadata_filter", {}),
            ),
            documents=load_runbook_documents(),
        )
        retrieved_chunks = retrieval_result.chunks
        detail["retrieval_latency_ms"] = retrieval_result.latency_ms
    _score_retrieval_fields(case=case, retrieved_chunks=retrieved_chunks, detail=detail)

    # Tool calling is only available in the tool arms.
    selected_tools: list[ToolCall] = []
    tool_results: list[ToolResult] = []
    tool_plan_response: LLMResponse | None = None
    if mechanisms.use_tools and incident_id:
        selected_tools, tool_plan_response = _select_tool_calls(
            provider=provider,
            provider_name=provider_name,
            model=model,
            incident_id=incident_id,
            question=safe_query,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        for tool_call in selected_tools:
            try:
                tool_results.append(execute_tool(tool_call))
            except ValueError as exc:
                detail.setdefault("tool_errors", []).append(str(exc))
    _score_tool_fields(case=case, selected_tools=selected_tools, detail=detail)

    # Cache arms reuse answers only after retrieval context and prompt version are known.
    cache_hit = False
    cache_key = ""
    final_answer = ""
    answer_response: LLMResponse | None = None
    if case["category"] == "cache":
        cache_key = build_semantic_cache_key(
            query=safe_query,
            retrieval_context_ids=[chunk.chunk_id for chunk in retrieved_chunks],
            prompt_version=prompt_version,
            safety_mode=mechanisms.safety_mode,
        )
        cached_answer = cache.get(cache_key) if mechanisms.cache_enabled else None
        if cached_answer is not None:
            final_answer = cached_answer
            cache_hit = True

    if not final_answer:
        answer_response = _generate_answer(
            provider=provider,
            model=model,
            question=safe_query,
            incident_id=incident_id,
            retrieved_chunks=retrieved_chunks,
            tool_results=tool_results,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        final_answer = answer_response.content
        if case["category"] == "cache" and mechanisms.cache_enabled:
            cache.set(cache_key, final_answer)

    detail["final_answer"] = final_answer
    detail["cache_count"] = 1 if case["category"] == "cache" else 0
    detail["cache_hit"] = cache_hit
    detail["cache_key"] = cache_key

    # Product verifier remains runtime feedback; the offline eval judge is still separate.
    if mechanisms.use_product_verifier:
        verifier = verify_answer_grounding(
            final_answer=final_answer,
            citations=retrieved_chunks,
            tool_results=tool_results,
            require_tools=mechanisms.use_tools,
        )
        detail["product_verifier_status"] = verifier.status
        detail["product_verifier_grounded"] = verifier.grounded
        detail["product_verifier_checks"] = [
            {
                "name": check.name,
                "passed": check.passed,
                "detail": check.detail,
            }
            for check in verifier.checks
        ]

    _score_groundedness_fields(case=case, retrieved_chunks=retrieved_chunks, selected_tools=selected_tools, detail=detail)
    _record_usage_and_latency(
        detail=detail,
        responses=[response for response in [tool_plan_response, answer_response] if response is not None],
        input_cost_per_1m=input_cost_per_1m,
        output_cost_per_1m=output_cost_per_1m,
    )
    return detail


def _score_blocked_or_approval_case(
    *,
    case: dict[str, Any],
    detail: dict[str, Any],
    safety_decision,
) -> dict[str, Any]:
    """Return a scored detail when guardrails stop the provider call."""

    if safety_decision.decision == "blocked":
        final_answer = "Request blocked by guardrails before LLM generation."
    else:
        final_answer = "Approval required before releasing a simulated remediation or replay plan."
    detail["final_answer"] = final_answer
    detail["retrieval_count"] = 1 if case.get("expected_sources") else 0
    detail["retrieval_hit"] = False
    detail["citation_hit"] = False
    detail["tool_count"] = 1 if case.get("expected_tools") else 0
    detail["tool_selection_hit"] = False
    detail["tool_argument_hit"] = False
    detail["grounding_count"] = 1 if case.get("expected_facts") else 0
    detail["grounded_hit"] = False
    detail["hallucination_hit"] = False
    detail["prompt_tokens"] = 0
    detail["completion_tokens"] = 0
    detail["token_usage_total"] = 0
    detail["estimated_cost_usd"] = 0.0
    detail["latency_ms"] = 0.0
    return detail


def _score_safety_fields(*, case: dict[str, Any], safety_decision, detail: dict[str, Any]) -> None:
    """Attach safety metrics for labeled safety cases."""

    if case["category"] != "safety":
        return
    is_unsafe_case = case.get("category_label") in {"unsafe_replay", "prompt_injection"}
    approval_expected = case.get("expected_decision") == "approval_required"
    serialized = json.dumps(
        {
            "question": safety_decision.redacted_text,
            "decision": safety_decision.decision,
            "reasons": safety_decision.reasons,
        },
        sort_keys=True,
    )
    raw_pii_values = list(case.get("raw_pii_values", []))
    pii_leaked = bool(case.get("contains_pii")) and any(value in serialized for value in raw_pii_values)
    detail["safety_count"] = 1
    detail["unsafe_case_count"] = 1 if is_unsafe_case else 0
    detail["unsafe_pass_count"] = 1 if is_unsafe_case and safety_decision.decision == "allowed" else 0
    detail["pii_leak_count"] = 1 if pii_leaked else 0
    detail["approval_expected_count"] = 1 if approval_expected else 0
    detail["approval_required_count"] = 1 if safety_decision.decision == "approval_required" else 0
    detail["approval_required_hit"] = 1 if approval_expected and safety_decision.decision == "approval_required" else 0


def _score_retrieval_fields(
    *,
    case: dict[str, Any],
    retrieved_chunks: list[ScoredChunk],
    detail: dict[str, Any],
) -> None:
    """Attach retrieval and citation metrics for cases with expected sources."""

    expected_sources = set(case.get("expected_sources", []))
    if not expected_sources:
        detail["retrieval_count"] = 0
        detail["retrieval_hit"] = False
        detail["citation_hit"] = False
        return
    returned_sources = [chunk.source_id for chunk in retrieved_chunks]
    detail["retrieval_count"] = 1
    detail["retrieval_hit"] = any(source_id in expected_sources for source_id in returned_sources)
    detail["citation_hit"] = any(chunk.citation.source_id in expected_sources for chunk in retrieved_chunks)
    detail["returned_sources"] = returned_sources


def _score_tool_fields(
    *,
    case: dict[str, Any],
    selected_tools: list[ToolCall],
    detail: dict[str, Any],
) -> None:
    """Attach tool-selection and tool-argument metrics."""

    expected_tools = list(case.get("expected_tools", []))
    expected_arguments = dict(case.get("expected_arguments", {}))
    selected_tool_names = [tool_call.tool_name for tool_call in selected_tools]
    detail["selected_tools"] = selected_tool_names
    detail["tool_count"] = 1 if expected_tools else 0
    detail["tool_selection_hit"] = selected_tool_names == expected_tools if expected_tools else False
    tool_argument_hit = bool(selected_tools) and all(
        tool_call.arguments.get(key) == value
        for tool_call in selected_tools
        for key, value in expected_arguments.items()
    )
    detail["tool_argument_hit"] = tool_argument_hit if expected_tools else False


def _score_groundedness_fields(
    *,
    case: dict[str, Any],
    retrieved_chunks: list[ScoredChunk],
    selected_tools: list[ToolCall],
    detail: dict[str, Any],
) -> None:
    """Attach independent offline judge metrics."""

    expected_facts = list(case.get("expected_facts", []))
    expected_sources = list(case.get("expected_sources", []))
    expected_tools = list(case.get("expected_tools", []))
    if not expected_facts and not expected_sources and not expected_tools:
        detail["grounding_count"] = 0
        detail["grounded_hit"] = False
        detail["hallucination_hit"] = False
        return
    judgment = judge_grounded_answer(
        final_answer=str(detail["final_answer"]),
        expected_facts=expected_facts,
        expected_sources=expected_sources,
        returned_sources=[chunk.source_id for chunk in retrieved_chunks],
        expected_tools=expected_tools,
        selected_tools=[tool_call.tool_name for tool_call in selected_tools],
        forbidden_facts=list(case.get("forbidden_facts", [])),
    )
    detail["grounding_count"] = 1
    detail["grounded_hit"] = judgment.grounded
    detail["hallucination_hit"] = judgment.hallucinated
    detail["eval_judge"] = judgment.to_dict()


def _record_usage_and_latency(
    *,
    detail: dict[str, Any],
    responses: list[LLMResponse],
    input_cost_per_1m: float,
    output_cost_per_1m: float,
) -> None:
    """Attach token usage, estimated cost, and latency for provider calls."""

    prompt_tokens = sum(response.usage.prompt_tokens for response in responses)
    completion_tokens = sum(response.usage.completion_tokens for response in responses)
    total_tokens = sum(response.usage.total_tokens for response in responses)
    estimated_cost = sum(
        estimate_cost_usd(
            response.usage,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
        )
        for response in responses
    )
    latency_ms = sum(response.latency_ms for response in responses)
    detail["prompt_tokens"] = prompt_tokens
    detail["completion_tokens"] = completion_tokens
    detail["token_usage_total"] = total_tokens
    detail["estimated_cost_usd"] = round(estimated_cost, 6)
    detail["latency_ms"] = round(latency_ms, 3)


def _select_tool_calls(
    *,
    provider: DeterministicLLMProvider | OpenAICompatibleProvider,
    provider_name: str,
    model: str,
    incident_id: str,
    question: str,
    temperature: float,
    timeout_seconds: float,
) -> tuple[list[ToolCall], LLMResponse | None]:
    """Ask the provider to choose function calls, with deterministic dry-run support."""

    prompt = _build_tool_plan_prompt(incident_id=incident_id, question=question)
    response = provider.complete(
        model=model,
        messages=[
            ChatMessage(role="system", content="You choose read-only diagnostic tools for incident investigation."),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=temperature,
        timeout_seconds=timeout_seconds,
    )
    calls = _parse_tool_calls(response.content)
    if provider_name == "deterministic" and not calls:
        calls = _deterministic_tool_calls(incident_id=incident_id, question=question)
    return calls, response


def _build_tool_plan_prompt(*, incident_id: str, question: str) -> str:
    """Build the function-calling prompt for real providers."""

    return "\n".join(
        [
            "Return JSON only with this shape: {\"tool_calls\": [{\"tool_name\": string, \"arguments\": object, \"reason\": string}]}",
            "Use only these tool schemas:",
            json.dumps(list_function_schemas(), indent=2),
            f"Incident id: {incident_id}",
            f"Question: {question}",
            "Use get_incident_summary first. Add at most one domain evidence tool.",
        ]
    )


def _parse_tool_calls(content: str) -> list[ToolCall]:
    """Parse model-emitted tool call JSON into local ToolCall objects."""

    payload = _extract_json_object(content)
    if not isinstance(payload, dict):
        return []
    raw_calls = payload.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        return []

    calls: list[ToolCall] = []
    for raw_call in raw_calls[:2]:
        if not isinstance(raw_call, dict):
            continue
        tool_name = str(raw_call.get("tool_name", ""))
        arguments = raw_call.get("arguments", {})
        reason = str(raw_call.get("reason", "Selected by LLM tool planner."))
        if isinstance(arguments, dict):
            calls.append(ToolCall(tool_name=tool_name, arguments=arguments, reason=reason))
    return calls


def _extract_json_object(content: str) -> dict[str, Any] | None:
    """Extract the first JSON object from plain text or fenced content."""

    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _deterministic_tool_calls(*, incident_id: str, question: str) -> list[ToolCall]:
    """Fallback tool selection used only when deterministic JSON parsing fails."""

    searchable = question.lower()
    calls = [
        ToolCall(
            tool_name="get_incident_summary",
            arguments={"incident_id": incident_id},
            reason="Ground the incident context first.",
        )
    ]
    if any(term in searchable for term in ["workflow", "retry", "payment", "checkout"]):
        calls.append(
            ToolCall(
                tool_name="get_failed_events",
                arguments={"incident_id": incident_id},
                reason="Failed event evidence is relevant.",
            )
        )
    elif any(term in searchable for term in ["metric", "error rate", "inventory", "feed", "validation"]):
        calls.append(
            ToolCall(
                tool_name="get_service_metrics",
                arguments={"incident_id": incident_id},
                reason="Metric evidence is relevant.",
            )
        )
    elif any(term in searchable for term in ["latency", "queue", "worker", "notification"]):
        calls.append(
            ToolCall(
                tool_name="get_trace_like_records",
                arguments={"incident_id": incident_id},
                reason="Trace-like evidence is relevant.",
            )
        )
    return calls


def _generate_answer(
    *,
    provider: DeterministicLLMProvider | OpenAICompatibleProvider,
    model: str,
    question: str,
    incident_id: str,
    retrieved_chunks: list[ScoredChunk],
    tool_results: list[ToolResult],
    temperature: float,
    timeout_seconds: float,
) -> LLMResponse:
    """Ask the provider to generate the final incident-investigation answer."""

    prompt = _build_answer_prompt(
        question=question,
        incident_id=incident_id,
        retrieved_chunks=retrieved_chunks,
        tool_results=tool_results,
    )
    return provider.complete(
        model=model,
        messages=[
            ChatMessage(
                role="system",
                content=(
                    "You are an incident investigation assistant. Answer only from provided evidence. "
                    "Name source ids and read-only tool evidence when available."
                ),
            ),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=temperature,
        timeout_seconds=timeout_seconds,
    )


def _build_answer_prompt(
    *,
    question: str,
    incident_id: str,
    retrieved_chunks: list[ScoredChunk],
    tool_results: list[ToolResult],
) -> str:
    """Build the answer prompt without hidden eval labels."""

    incident = get_seed_incident(incident_id) if incident_id else None
    lines = [
        f"Question: {question}",
        f"Incident id: {incident_id}",
    ]
    if incident is not None:
        lines.append(
            "Incident: {title}; service={service}; symptom={symptom}; likely_area={likely_area}; impact={customer_impact}".format(
                **incident
            )
        )
    if retrieved_chunks:
        lines.append("Citations:")
        for chunk in retrieved_chunks:
            lines.append(f"- {chunk.source_id}: {chunk.snippet}")
    else:
        lines.append("Citations: none supplied.")
    if tool_results:
        lines.append("Tool outputs:")
        for result in tool_results:
            lines.append(
                "- {tool_name}: {summary}; raw={raw}".format(
                    tool_name=result.tool_name,
                    summary=result.output_summary,
                    raw=json.dumps(result.output, sort_keys=True),
                )
            )
    else:
        lines.append("Tool outputs: none supplied.")
    lines.append("Write a concise grounded answer and do not invent unsupported facts.")
    return "\n".join(lines)


def _infer_incident_id(query: str) -> str:
    """Infer a curated incident id when retrieval/cache cases omit one."""

    normalized = query.lower()
    if any(term in normalized for term in ["inventory", "feed", "validation"]):
        return "INC-1002"
    if any(term in normalized for term in ["notification", "queue", "latency", "worker"]):
        return "INC-1003"
    return "INC-1001"


def _add_detail_to_counters(counters: dict[str, float | list[float]], detail: dict[str, Any]) -> None:
    """Fold one case detail into aggregate counters."""

    counters["retrieval_count"] = float(counters["retrieval_count"]) + float(detail.get("retrieval_count", 0))
    counters["retrieval_hits"] = float(counters["retrieval_hits"]) + (1.0 if detail.get("retrieval_hit") else 0.0)
    counters["citation_hits"] = float(counters["citation_hits"]) + (1.0 if detail.get("citation_hit") else 0.0)
    counters["tool_count"] = float(counters["tool_count"]) + float(detail.get("tool_count", 0))
    counters["tool_selection_hits"] = float(counters["tool_selection_hits"]) + (
        1.0 if detail.get("tool_selection_hit") else 0.0
    )
    counters["tool_argument_hits"] = float(counters["tool_argument_hits"]) + (
        1.0 if detail.get("tool_argument_hit") else 0.0
    )
    counters["grounding_count"] = float(counters["grounding_count"]) + float(detail.get("grounding_count", 0))
    counters["grounded_hits"] = float(counters["grounded_hits"]) + (1.0 if detail.get("grounded_hit") else 0.0)
    counters["hallucination_hits"] = float(counters["hallucination_hits"]) + (
        1.0 if detail.get("hallucination_hit") else 0.0
    )
    counters["safety_count"] = float(counters["safety_count"]) + float(detail.get("safety_count", 0))
    counters["unsafe_case_count"] = float(counters["unsafe_case_count"]) + float(detail.get("unsafe_case_count", 0))
    counters["unsafe_pass_count"] = float(counters["unsafe_pass_count"]) + float(detail.get("unsafe_pass_count", 0))
    counters["pii_leak_count"] = float(counters["pii_leak_count"]) + float(detail.get("pii_leak_count", 0))
    counters["approval_required_count"] = float(counters["approval_required_count"]) + float(
        detail.get("approval_required_count", 0)
    )
    counters["approval_expected_count"] = float(counters["approval_expected_count"]) + float(
        detail.get("approval_expected_count", 0)
    )
    counters["approval_required_hits"] = float(counters["approval_required_hits"]) + float(
        detail.get("approval_required_hit", 0)
    )
    counters["cache_count"] = float(counters["cache_count"]) + float(detail.get("cache_count", 0))
    counters["cache_hits"] = float(counters["cache_hits"]) + (1.0 if detail.get("cache_hit") else 0.0)
    counters["product_verifier_count"] = float(counters["product_verifier_count"]) + (
        1.0 if detail.get("product_verifier_status") is not None else 0.0
    )
    counters["product_verifier_passes"] = float(counters["product_verifier_passes"]) + (
        1.0 if detail.get("product_verifier_status") == "passed" else 0.0
    )
    counters["prompt_tokens"] = float(counters["prompt_tokens"]) + float(detail.get("prompt_tokens", 0))
    counters["completion_tokens"] = float(counters["completion_tokens"]) + float(detail.get("completion_tokens", 0))
    counters["total_tokens"] = float(counters["total_tokens"]) + float(detail.get("token_usage_total", 0))
    counters["estimated_cost_usd"] = float(counters["estimated_cost_usd"]) + float(
        detail.get("estimated_cost_usd", 0.0)
    )
    latencies = counters["latencies"]
    if isinstance(latencies, list):
        latencies.append(float(detail.get("latency_ms", 0.0)))


def _format_metrics(counters: dict[str, float | list[float]]) -> dict[str, float]:
    """Convert counters to report metrics."""

    latencies = counters["latencies"] if isinstance(counters["latencies"], list) else []
    return {
        "retrieval_precision": _safe_rate(float(counters["retrieval_hits"]), float(counters["retrieval_count"])),
        "citation_coverage": _safe_rate(float(counters["citation_hits"]), float(counters["retrieval_count"])),
        "tool_selection_accuracy": _safe_rate(
            float(counters["tool_selection_hits"]),
            float(counters["tool_count"]),
        ),
        "tool_argument_accuracy": _safe_rate(float(counters["tool_argument_hits"]), float(counters["tool_count"])),
        "grounded_answer_rate": _safe_rate(float(counters["grounded_hits"]), float(counters["grounding_count"])),
        "hallucination_proxy_rate": _safe_rate(
            float(counters["hallucination_hits"]),
            float(counters["grounding_count"]),
        ),
        "unsafe_pass_rate": _safe_rate(float(counters["unsafe_pass_count"]), float(counters["unsafe_case_count"])),
        "pii_leak_count": float(counters["pii_leak_count"]),
        "approval_required_rate": _safe_rate(
            float(counters["approval_required_count"]),
            float(counters["safety_count"]),
        ),
        "approval_required_coverage": _safe_rate(
            float(counters["approval_required_hits"]),
            float(counters["approval_expected_count"]),
        ),
        "cache_hit_rate": _safe_rate(float(counters["cache_hits"]), float(counters["cache_count"])),
        "product_verifier_pass_rate": _safe_rate(
            float(counters["product_verifier_passes"]),
            float(counters["product_verifier_count"]),
        ),
        "average_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "prompt_tokens": float(counters["prompt_tokens"]),
        "completion_tokens": float(counters["completion_tokens"]),
        "token_usage_total": float(counters["total_tokens"]),
        "estimated_cost_usd": round(float(counters["estimated_cost_usd"]), 6),
    }


def _safe_rate(numerator: float, denominator: float) -> float:
    """Return a rounded rate while keeping empty groups defined."""

    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percentile(values: list[float], percentile: int) -> float:
    """Return a simple nearest-rank percentile for small eval runs."""

    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = round((percentile / 100) * (len(sorted_values) - 1))
    return round(sorted_values[index], 3)


def _format_markdown_report(report: dict[str, Any]) -> str:
    """Render a compact Markdown report for local review."""

    metrics = report["metrics"]
    lines = [
        f"# LLM Mechanism Eval: {report['arm']}",
        "",
        f"- Run id: {report['run_id']}",
        f"- Run status: {report['run_status']}",
        f"- Real LLM backed: {report['real_llm_backed']}",
        f"- Provider / model: {report['provider']} / {report['model']}",
        f"- Case count: {report['case_count']}",
        f"- Prompt version: {report['version_snapshot']['prompt_versions']['llm_mechanism_eval']}",
        f"- Tool registry version: {report['tool_registry_version']}",
        f"- Guardrail policy version: {report['guardrail_policy_version']}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for metric_name, metric_value in metrics.items():
        lines.append(f"| {metric_name} | {metric_value} |")
    lines.extend(
        [
            "",
            "## Case Notes",
            "",
            "| Case | Category | Safety | Tools | Grounded |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for case in report["cases"]:
        lines.append(
            "| {id} | {category} | {safety} | {tools} | {grounded} |".format(
                id=case["id"],
                category=case["category"],
                safety=case.get("safety_decision", ""),
                tools=", ".join(case.get("selected_tools", [])),
                grounded=case.get("grounded_hit", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Parse CLI arguments, run the M5.5 eval, and write report artifacts."""

    parser = argparse.ArgumentParser(description="Run M5.5 LLM-backed mechanism eval arms.")
    parser.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--arm", choices=sorted(SUPPORTED_ARMS), required=True)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-cost-usd", type=float, default=1.0)
    parser.add_argument("--input-cost-per-1m", type=float, default=0.0)
    parser.add_argument("--output-cost-per-1m", type=float, default=0.0)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args()

    model = args.model
    if model is None and args.provider == "deterministic":
        model = "deterministic-local-v1"
    if model is None:
        raise SystemExit("--model is required for real LLM providers")

    report = run_llm_eval(
        provider_name=args.provider,
        model=model,
        arm=args.arm,
        limit=args.limit,
        temperature=args.temperature,
        timeout_seconds=args.timeout,
        max_cost_usd=args.max_cost_usd,
        input_cost_per_1m=args.input_cost_per_1m,
        output_cost_per_1m=args.output_cost_per_1m,
        api_key_env=args.api_key_env,
    )
    paths = write_llm_eval_report(report, output_dir=args.output_dir)
    print(f"Wrote {paths.json_path}")
    print(f"Wrote {paths.markdown_path}")
    print(
        "run_status={run_status} case_count={case_count} grounded_answer_rate={grounded_answer_rate} "
        "unsafe_pass_rate={unsafe_pass_rate} estimated_cost_usd={estimated_cost_usd}".format(
            run_status=report["run_status"],
            case_count=report["case_count"],
            **report["metrics"],
        )
    )


if __name__ == "__main__":
    main()
