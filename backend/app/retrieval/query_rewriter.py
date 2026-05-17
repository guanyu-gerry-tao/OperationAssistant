from backend.app.retrieval.embeddings import TOKEN_PATTERN


REWRITE_HINTS = {
    "checkout": "runbook retry exhaustion checkout workflow payment timeout",
    "payment": "runbook retry exhaustion checkout workflow payment timeout",
    "retry": "runbook retry exhaustion checkout workflow payment timeout",
    "feed": "schema validation partner feed inventory error rate",
    "inventory": "schema validation partner feed inventory error rate",
    "validation": "schema validation partner feed inventory error rate",
    "queue": "queue backlog latency worker notification throughput",
    "latency": "queue backlog latency worker notification throughput",
    "notification": "queue backlog latency worker notification throughput",
    "replay": "approval unsafe replay guardrail operator request",
    "unsafe": "approval unsafe replay guardrail operator request",
    "citation": "source citation evidence grounded answer",
    "evidence": "source citation evidence grounded answer",
}


def rewrite_query(query: str) -> str:
    """Expand visible incident terms for the improved retrieval strategy."""

    tokens = set(TOKEN_PATTERN.findall(query.lower()))
    hints = [hint for token, hint in REWRITE_HINTS.items() if token in tokens]
    if not hints:
        return f"{query} runbook incident response evidence"

    unique_terms = []
    seen = set(tokens)
    for hint in hints:
        for token in hint.split():
            if token not in seen:
                unique_terms.append(token)
                seen.add(token)

    return " ".join([query, *unique_terms]).strip()
