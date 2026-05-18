from scripts.eval_retrieval import run_retrieval_eval


def test_eval_runner_reports_precision_citation_coverage_and_latency() -> None:
    report = run_retrieval_eval(strategy="hybrid_rerank_rewrite", limit=5)

    assert report["strategy"] == "hybrid_rerank_rewrite"
    assert report["case_count"] == 5
    assert report["precision_at_k"] >= 0.8
    assert report["citation_coverage"] >= 0.8
    assert report["average_latency_ms"] >= 0
