import json
from pathlib import Path
from typing import Any


DEFAULT_LATEST_SUMMARY_PATH = Path("evals/results/full/latest_summary.json")


def load_latest_eval_summary(path: Path | None = None) -> dict[str, Any]:
    """Load the latest eval summary written by scripts/eval_all.py."""

    summary_path = DEFAULT_LATEST_SUMMARY_PATH if path is None else path
    if not summary_path.exists():
        return {
            "run_id": "not-run",
            "arm": "none",
            "case_count": 0,
            "metrics": {},
            "report_path": None,
            "version_snapshot": {},
        }
    return json.loads(summary_path.read_text(encoding="utf-8"))
