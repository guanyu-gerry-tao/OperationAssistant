import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Allow this script to run directly from the repository root without installing a package.
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.workflows.investigation import SUPPORTED_INVESTIGATION_MODES, run_investigation
from backend.app.workflows.models import InvestigationRequest


CASES_PATH = Path("evals/tool_use/cases.json")
DEFAULT_OUTPUT_DIR = Path("evals/results/investigation")


def run_investigation_eval(
    *,
    mode: str,
    limit: int | None = None,
    top_k: int = 3,
    cases_path: Path = CASES_PATH,
) -> dict[str, Any]:
    """Run labeled investigation cases and return tool/grounding metrics."""

    # Fail fast when a caller asks for a mode that the runtime cannot execute.
    if mode not in SUPPORTED_INVESTIGATION_MODES:
        raise ValueError("Unknown investigation mode")

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if limit is not None:
        selected_cases = cases[:limit]
    else:
        selected_cases = cases

    results = []
    tool_selection_hits = 0
    tool_argument_hits = 0
    grounded_hits = 0
    source_hits = 0
    latencies = []

    for case in selected_cases:
        # Use the same deterministic workflow path as the API.
        result = run_investigation(
            InvestigationRequest(
                incident_id=case["incident_id"],
                question=case["query"],
                mode=mode,
                top_k=top_k,
            )
        )
        selected_tools = [tool_call.tool_name for tool_call in result.selected_tools]
        returned_sources = [chunk.source_id for chunk in result.retrieved_chunks]
        expected_tools = list(case["expected_tools"])
        expected_sources = set(case["expected_sources"])
        expected_arguments = dict(case["expected_arguments"])

        has_expected_tools = selected_tools == expected_tools
        has_expected_arguments = bool(result.selected_tools) and all(
            tool_call.arguments.get(key) == value
            for tool_call in result.selected_tools
            for key, value in expected_arguments.items()
        )
        has_expected_source = any(source_id in expected_sources for source_id in returned_sources)
        grounded = _answer_has_expected_facts(result.final_answer, case["expected_facts"])

        tool_selection_hits += 1 if has_expected_tools else 0
        tool_argument_hits += 1 if has_expected_arguments else 0
        source_hits += 1 if has_expected_source else 0
        grounded_hits += 1 if grounded else 0
        latencies.append(result.latency_ms)
        results.append(
            {
                "id": case["id"],
                "incident_id": case["incident_id"],
                "query": case["query"],
                "expected_tools": expected_tools,
                "selected_tools": selected_tools,
                "tool_selection_hit": has_expected_tools,
                "tool_argument_hit": has_expected_arguments,
                "expected_sources": sorted(expected_sources),
                "returned_sources": returned_sources,
                "source_hit": has_expected_source,
                "grounded_answer_hit": grounded,
                "verifier_status": result.verifier.status if result.verifier is not None else "missing",
                "trace_steps": [span.step_name for span in result.trace],
                "final_answer": result.final_answer,
                "tool_results": [asdict(tool_result) for tool_result in result.tool_results],
                "latency_ms": result.latency_ms,
            }
        )

    case_count = len(selected_cases)
    return {
        "mode": mode,
        "case_count": case_count,
        "tool_selection_accuracy": round(tool_selection_hits / case_count, 4) if case_count else 0.0,
        "tool_argument_accuracy": round(tool_argument_hits / case_count, 4) if case_count else 0.0,
        "source_coverage": round(source_hits / case_count, 4) if case_count else 0.0,
        "grounded_answer_rate": round(grounded_hits / case_count, 4) if case_count else 0.0,
        "average_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "cases": results,
    }


def write_eval_report(report: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    """Persist investigation eval output as JSON and Markdown."""

    # Eval output is ignored by git, but writing it locally helps manual review.
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = report["mode"]
    json_path = output_dir / f"investigation_{mode}.json"
    markdown_path = output_dir / f"investigation_{mode}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_format_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _answer_has_expected_facts(final_answer: str, expected_facts: list[str]) -> bool:
    """Return whether the final answer contains all labeled evidence terms."""

    normalized_answer = final_answer.lower()
    return all(fact.lower() in normalized_answer for fact in expected_facts)


def _format_markdown_report(report: dict[str, Any]) -> str:
    """Render a compact Markdown summary for humans reviewing M3 quality."""

    lines = [
        f"# Investigation Eval: {report['mode']}",
        "",
        f"- Case count: {report['case_count']}",
        f"- Tool-selection accuracy: {report['tool_selection_accuracy']}",
        f"- Tool-argument accuracy: {report['tool_argument_accuracy']}",
        f"- Source coverage: {report['source_coverage']}",
        f"- Grounded-answer rate: {report['grounded_answer_rate']}",
        f"- Average latency ms: {report['average_latency_ms']}",
        "",
        "| Case | Tools | Args | Source | Grounded | Verifier |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            "| {id} | {tool_selection_hit} | {tool_argument_hit} | {source_hit} | {grounded_answer_hit} | {verifier_status} |".format(
                **case
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Parse CLI arguments, run investigation eval, and print summary metrics."""

    parser = argparse.ArgumentParser(description="Run investigation workflow benchmark cases.")
    parser.add_argument("--mode", choices=sorted(SUPPORTED_INVESTIGATION_MODES), required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = run_investigation_eval(mode=args.mode, limit=args.limit, top_k=args.top_k)
    json_path, markdown_path = write_eval_report(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(
        "tool_selection_accuracy={tool_selection_accuracy} tool_argument_accuracy={tool_argument_accuracy} "
        "source_coverage={source_coverage} grounded_answer_rate={grounded_answer_rate} average_latency_ms={average_latency_ms}".format(
            **report
        )
    )


if __name__ == "__main__":
    main()
