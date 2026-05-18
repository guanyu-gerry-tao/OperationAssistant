from scripts.eval_investigation import run_investigation_eval


def test_investigation_eval_reports_category_and_tool_breakdowns() -> None:
    report = run_investigation_eval(mode="agent_tools")

    # The M3 eval should include harder summary-only cases and per-bucket metrics.
    assert report["case_count"] == 30
    assert report["tool_selection_accuracy"] == 1.0
    assert report["category_tool_selection_accuracy"]["summary_only"] == 1.0
    assert report["category_tool_selection_accuracy"]["weak_keyword_domain"] == 1.0
    assert report["expected_tool_selection_coverage"]["get_incident_summary"] == 1.0
    assert report["expected_tool_selection_coverage"]["get_failed_events"] == 1.0
