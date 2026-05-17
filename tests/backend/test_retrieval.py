from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.retrieval.chunker import chunk_document_text
from backend.app.retrieval.embeddings import DeterministicEmbeddingProvider
from backend.app.retrieval.loader import load_runbook_documents
from backend.app.retrieval.retriever import RetrievalRequest, retrieve_chunks


def test_chunker_splits_text_with_source_metadata() -> None:
    text = "first line about retries\nsecond line about payments\nthird line about resolution"

    chunks = chunk_document_text(
        document_id="doc-1",
        source_path="data/runbooks/example.md",
        title="Example Runbook",
        text=text,
        metadata={"service": "checkout-workflow"},
        max_words=5,
        overlap_words=2,
    )

    assert len(chunks) >= 2
    assert chunks[0].document_id == "doc-1"
    assert chunks[0].source_path == "data/runbooks/example.md"
    assert chunks[0].metadata["service"] == "checkout-workflow"


def test_deterministic_embedding_provider_returns_stable_vectors() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=8)

    first_vector = provider.embed("checkout retry timeout")
    second_vector = provider.embed("checkout retry timeout")

    assert first_vector == second_vector
    assert len(first_vector) == 8
    assert any(value != 0 for value in first_vector)


def test_retrieval_applies_metadata_filtering_and_citations() -> None:
    documents = load_runbook_documents()

    result = retrieve_chunks(
        RetrievalRequest(
            query="why did checkout payment retries exhaust",
            strategy="hybrid_rerank_rewrite",
            top_k=3,
            metadata_filter={"service": "checkout-workflow"},
        ),
        documents=documents,
    )

    assert result.strategy == "hybrid_rerank_rewrite"
    assert result.rewritten_query != result.query
    assert len(result.chunks) > 0
    assert all(chunk.metadata["service"] == "checkout-workflow" for chunk in result.chunks)
    assert result.chunks[0].citation.source_id.startswith("RB-")


def test_retrieval_keeps_lexical_baseline_and_hybrid_improved_modes() -> None:
    documents = load_runbook_documents()

    lexical_result = retrieve_chunks(
        RetrievalRequest(query="partner feed validation errors", strategy="lexical", top_k=3),
        documents=documents,
    )
    hybrid_result = retrieve_chunks(
        RetrievalRequest(query="partner feed validation errors", strategy="hybrid_rerank_rewrite", top_k=3),
        documents=documents,
    )

    assert lexical_result.strategy == "lexical"
    assert hybrid_result.strategy == "hybrid_rerank_rewrite"
    assert lexical_result.chunks[0].source_id == "RB-1002"
    assert hybrid_result.chunks[0].source_id == "RB-1002"


def test_retrieval_api_defaults_to_improved_strategy() -> None:
    response = TestClient(app).get(
        "/api/retrieval",
        params={"query": "queue latency backlog notifications", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "hybrid_rerank_rewrite"
    assert payload["chunks"][0]["citation"]["source_id"] == "RB-1003"
    assert payload["chunks"][0]["citation"]["source_path"].startswith("data/runbooks/")


def test_retrieval_api_rejects_unknown_strategy() -> None:
    response = TestClient(app).get(
        "/api/retrieval",
        params={"query": "checkout retry", "strategy": "agent_tools"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown retrieval strategy"}
