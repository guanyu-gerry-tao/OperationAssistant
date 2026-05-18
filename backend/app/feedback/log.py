import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_FEEDBACK_LOG_PATH = Path("evals/feedback/quality_feedback.jsonl")
SUPPORTED_FEEDBACK_LABELS = {
    "citation_issue",
    "wrong_tool",
    "unsafe_answer",
    "missing_fact",
    "helpful",
}


@dataclass(frozen=True)
class FeedbackEntry:
    """One lightweight quality feedback event for the M5 feedback loop."""

    run_id: str
    case_id: str
    label: str
    note: str
    created_at: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly feedback payload."""

        payload = asdict(self)
        if payload["created_at"] is None:
            payload["created_at"] = datetime.now(UTC).isoformat()
        return payload


def append_feedback_entry(
    entry: FeedbackEntry,
    path: Path = DEFAULT_FEEDBACK_LOG_PATH,
) -> None:
    """Append one labeled feedback event to a JSONL file."""

    if entry.label not in SUPPORTED_FEEDBACK_LABELS:
        raise ValueError("Unsupported feedback label")

    # JSONL keeps the feedback loop append-only and easy to inspect locally.
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = entry.to_dict()
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def read_feedback_log(path: Path = DEFAULT_FEEDBACK_LOG_PATH) -> list[FeedbackEntry]:
    """Read feedback entries from a JSONL file."""

    if not path.exists():
        return []

    entries: list[FeedbackEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        entries.append(
            FeedbackEntry(
                run_id=payload["run_id"],
                case_id=payload["case_id"],
                label=payload["label"],
                note=payload["note"],
                created_at=payload["created_at"],
            )
        )
    return entries
