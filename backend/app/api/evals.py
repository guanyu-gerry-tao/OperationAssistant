from fastapi import APIRouter

from backend.app.evals.latest_summary import load_latest_eval_summary


router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.get("/latest")
def read_latest_eval_summary() -> dict[str, object]:
    """Return the latest local eval summary for the frontend dashboard."""

    return {"summary": load_latest_eval_summary()}
