import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.retrieval.loader import load_runbook_documents
from backend.app.retrieval.models import RetrievalRequest
from backend.app.retrieval.retriever import SUPPORTED_STRATEGIES, retrieve_chunks


CASES_PATH = Path("evals/retrieval/cases.json")
DEFAULT_OUTPUT_DIR = Path("evals/results/retrieval")


def run_retrieval_eval(
    *,
    strategy: str,
    limit: int | None = None,
    top_k: int = 3,
    cases_path: Path = CASES_PATH,
) -> dict[str, Any]:
    """Run labeled retrieval cases and return benchmark metrics."""

    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError("Unknown retrieval strategy")

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    selected_cases = cases[:limit] if limit is not None else cases
    documents = load_runbook_documents()

    results = []
    precision_hits = 0
    citation_hits = 0
    latencies = []

    for case in selected_cases:
        request = RetrievalRequest(
            query=case["query"],
            strategy=strategy,
            top_k=top_k,
            metadata_filter=case.get("metadata_filter", {}),
        )
        result = retrieve_chunks(request, documents=documents)
        expected_sources = set(case["expected_sources"])
        returned_sources = [chunk.source_id for chunk in result.chunks]
        has_expected_source = any(source_id in expected_sources for source_id in returned_sources)
        has_expected_citation = any(
            chunk.citation.source_id in expected_sources and chunk.citation.source_path
            for chunk in result.chunks
        )

        precision_hits += 1 if has_expected_source else 0
        citation_hits += 1 if has_expected_citation else 0
        latencies.append(result.latency_ms)
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_sources": sorted(expected_sources),
                "returned_sources": returned_sources,
                "hit": has_expected_source,
                "citation_hit": has_expected_citation,
                "top_chunks": [asdict(chunk) for chunk in result.chunks],
                "latency_ms": result.latency_ms,
            }
        )

    case_count = len(selected_cases)
    return {
        "strategy": strategy,
        "case_count": case_count,
        "precision_at_k": round(precision_hits / case_count, 4) if case_count else 0.0,
        "citation_coverage": round(citation_hits / case_count, 4) if case_count else 0.0,
        "average_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "cases": results,
    }


def write_eval_report(report: dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    """Persist retrieval benchmark output as JSON and Markdown."""

    output_dir.mkdir(parents=True, exist_ok=True)
    strategy = report["strategy"]
    json_path = output_dir / f"retrieval_{strategy}.json"
    markdown_path = output_dir / f"retrieval_{strategy}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_format_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _format_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Retrieval Eval: {report['strategy']}",
        "",
        f"- Case count: {report['case_count']}",
        f"- Precision@k: {report['precision_at_k']}",
        f"- Citation coverage: {report['citation_coverage']}",
        f"- Average latency ms: {report['average_latency_ms']}",
        "",
        "| Case | Hit | Citation | Returned sources |",
        "| --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        sources = ", ".join(case["returned_sources"])
        lines.append(f"| {case['id']} | {case['hit']} | {case['citation_hit']} | {sources} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval benchmark cases.")
    parser.add_argument("--strategy", choices=sorted(SUPPORTED_STRATEGIES), required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = run_retrieval_eval(strategy=args.strategy, limit=args.limit, top_k=args.top_k)
    json_path, markdown_path = write_eval_report(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(
        "precision_at_k={precision_at_k} citation_coverage={citation_coverage} average_latency_ms={average_latency_ms}".format(
            **report
        )
    )


if __name__ == "__main__":
    main()
