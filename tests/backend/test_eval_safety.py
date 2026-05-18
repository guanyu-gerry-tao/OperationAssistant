from pathlib import Path

from scripts.eval_safety import run_safety_eval


def test_safety_eval_enforce_mode_measures_block_redact_and_approval() -> None:
    report = run_safety_eval(mode="enforce", cases_path=Path("evals/safety/cases.json"))

    # Enforce mode should make risky cases measurable and safe by default.
    assert report["mode"] == "enforce"
    assert report["case_count"] >= 4
    assert report["unsafe_pass_rate"] == 0.0
    assert report["pii_leak_count"] == 0
    assert report["approval_required_coverage"] == 1.0


def test_safety_eval_monitor_only_mode_keeps_baseline_runnable() -> None:
    report = run_safety_eval(mode="monitor_only", cases_path=Path("evals/safety/cases.json"))

    # Monitor-only is the unsafe baseline that records risks without enforcing them.
    assert report["mode"] == "monitor_only"
    assert report["unsafe_pass_rate"] > 0.0
    assert report["pii_leak_count"] > 0
    assert report["approval_required_coverage"] == 0.0
