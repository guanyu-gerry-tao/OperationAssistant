from backend.app.workflows.models import InvestigationResult


_INVESTIGATION_STORE: dict[str, InvestigationResult] = {}


def save_investigation(result: InvestigationResult) -> None:
    """Store a synchronous M3 investigation result for later trace reads."""

    _INVESTIGATION_STORE[result.trace_id] = result


def get_investigation(trace_id: str) -> InvestigationResult | None:
    """Return one stored investigation result by trace id."""

    return _INVESTIGATION_STORE.get(trace_id)
