from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VersionSnapshot:
    """Describe the deterministic runtime versions used by eval reports."""

    prompt_versions: dict[str, str]
    model_profile: str
    tool_registry_version: str
    guardrail_policy_version: str
    cache_inputs: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly version snapshot."""

        return asdict(self)


def build_version_snapshot() -> VersionSnapshot:
    """Return prompt/model/tool/guardrail metadata for M5 eval traceability."""

    # These versions are intentionally simple because this repo uses deterministic local logic.
    return VersionSnapshot(
        prompt_versions={
            "triage": "triage_prompt_v1",
            "retrieval_query": "retrieval_query_rewrite_v1",
            "investigation_answer": "investigation_answer_v1",
            "approval_response": "approval_response_v1",
            "llm_mechanism_eval": "llm_mechanism_eval_v1",
        },
        model_profile="deterministic-local-v1",
        tool_registry_version="sample_tools_v1",
        guardrail_policy_version="guardrail_policy_v1",
        cache_inputs=[
            "semantic_cache_key",
            "normalized_query",
            "retrieval_context_ids",
            "prompt_version",
            "safety_mode",
        ],
    )
