from dataclasses import dataclass


@dataclass(frozen=True)
class GroundednessJudgment:
    """Offline deterministic score for one labeled answer."""

    grounded: bool
    hallucinated: bool
    missing_facts: list[str]
    missing_tools: list[str]
    citation_mismatch_count: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly judge result."""

        return {
            "grounded": self.grounded,
            "hallucinated": self.hallucinated,
            "missing_facts": self.missing_facts,
            "missing_tools": self.missing_tools,
            "citation_mismatch_count": self.citation_mismatch_count,
        }


def judge_grounded_answer(
    *,
    final_answer: str,
    expected_facts: list[str],
    expected_sources: list[str],
    returned_sources: list[str],
    expected_tools: list[str],
    selected_tools: list[str],
) -> GroundednessJudgment:
    """Score groundedness from labels instead of product verifier self-assessment."""

    normalized_answer = final_answer.lower()

    # Facts are checked against the final text so hallucination metrics tie back to labels.
    missing_facts = [
        fact
        for fact in expected_facts
        if fact.lower() not in normalized_answer
    ]

    # Citations are scored from returned source ids, independent of verifier pass/fail state.
    returned_source_set = set(returned_sources)
    citation_mismatch_count = len(
        [
            source_id
            for source_id in expected_sources
            if source_id not in returned_source_set
        ]
    )

    # Tool use is part of groundedness only for cases that explicitly expect tools.
    selected_tool_set = set(selected_tools)
    missing_tools = [
        tool_name
        for tool_name in expected_tools
        if tool_name not in selected_tool_set
    ]

    grounded = not missing_facts and citation_mismatch_count == 0 and not missing_tools
    return GroundednessJudgment(
        grounded=grounded,
        hallucinated=not grounded,
        missing_facts=missing_facts,
        missing_tools=missing_tools,
        citation_mismatch_count=citation_mismatch_count,
    )
