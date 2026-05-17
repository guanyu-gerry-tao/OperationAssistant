from time import perf_counter

from backend.app.retrieval.chunker import chunk_document_text
from backend.app.retrieval.embeddings import (
    TOKEN_PATTERN,
    DeterministicEmbeddingProvider,
    cosine_similarity,
)
from backend.app.retrieval.models import (
    Citation,
    DocumentChunk,
    RetrievalRequest,
    RetrievalResult,
    RetrievalStrategy,
    RunbookDocument,
    ScoredChunk,
)
from backend.app.retrieval.query_rewriter import rewrite_query


SUPPORTED_STRATEGIES = {"lexical", "hybrid_rerank_rewrite"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "did",
    "for",
    "how",
    "in",
    "is",
    "of",
    "the",
    "to",
    "why",
}


def retrieve_chunks(
    request: RetrievalRequest,
    *,
    documents: list[RunbookDocument],
    embedding_provider: DeterministicEmbeddingProvider | None = None,
) -> RetrievalResult:
    """Rank runbook chunks with either lexical baseline or improved hybrid retrieval."""

    if request.strategy not in SUPPORTED_STRATEGIES:
        raise ValueError("Unknown retrieval strategy")
    if request.top_k <= 0:
        raise ValueError("top_k must be positive")

    started_at = perf_counter()
    strategy = request.strategy
    effective_query = rewrite_query(request.query) if strategy == "hybrid_rerank_rewrite" else request.query
    provider = embedding_provider or DeterministicEmbeddingProvider()

    chunks = _chunk_documents(documents)
    filtered_chunks = [chunk for chunk in chunks if _matches_metadata(chunk, request.metadata_filter)]
    scored = [
        _score_chunk(chunk, request.query, effective_query, strategy, provider)
        for chunk in filtered_chunks
    ]
    ranked = sorted(scored, key=lambda chunk: (-chunk.score, chunk.source_id, chunk.chunk_id))

    latency_ms = round((perf_counter() - started_at) * 1000, 3)
    return RetrievalResult(
        query=request.query,
        rewritten_query=effective_query,
        strategy=strategy,  # type: ignore[arg-type]
        chunks=ranked[: request.top_k],
        latency_ms=latency_ms,
    )


def _chunk_documents(documents: list[RunbookDocument]) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for document in documents:
        chunks.extend(
            chunk_document_text(
                document_id=document.document_id,
                source_path=document.source_path,
                title=document.title,
                text=document.text,
                metadata=document.metadata,
            )
        )
    return chunks


def _matches_metadata(chunk: DocumentChunk, metadata_filter: dict[str, str]) -> bool:
    for key, expected_value in metadata_filter.items():
        if chunk.metadata.get(key) != expected_value:
            return False
    return True


def _score_chunk(
    chunk: DocumentChunk,
    original_query: str,
    effective_query: str,
    strategy: RetrievalStrategy,
    embedding_provider: DeterministicEmbeddingProvider,
) -> ScoredChunk:
    lexical_score = _lexical_score(original_query, chunk)
    if strategy == "lexical":
        score = lexical_score
    else:
        vector_score = _vector_score(effective_query, chunk, embedding_provider)
        rerank_bonus = _rerank_bonus(original_query, chunk)
        score = (0.55 * lexical_score) + (0.35 * vector_score) + rerank_bonus

    return ScoredChunk(
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        title=chunk.title,
        snippet=_build_snippet(chunk.text),
        score=round(score, 4),
        metadata=chunk.metadata,
        citation=Citation(
            source_id=chunk.source_id,
            source_title=chunk.title,
            source_path=chunk.source_path,
            chunk_id=chunk.chunk_id,
        ),
    )


def _lexical_score(query: str, chunk: DocumentChunk) -> float:
    query_tokens = _important_tokens(query)
    if not query_tokens:
        return 0.0

    searchable_text = " ".join(
        [
            chunk.title,
            chunk.text,
            " ".join(chunk.metadata.values()),
        ]
    )
    chunk_tokens = set(_important_tokens(searchable_text))
    matches = sum(1 for token in query_tokens if token in chunk_tokens)
    return matches / len(set(query_tokens))


def _vector_score(
    query: str,
    chunk: DocumentChunk,
    embedding_provider: DeterministicEmbeddingProvider,
) -> float:
    query_vector = embedding_provider.embed(query)
    chunk_vector = embedding_provider.embed(f"{chunk.title} {chunk.text} {' '.join(chunk.metadata.values())}")
    return max(cosine_similarity(query_vector, chunk_vector), 0.0)


def _rerank_bonus(query: str, chunk: DocumentChunk) -> float:
    query_tokens = set(_important_tokens(query))
    title_tokens = set(_important_tokens(chunk.title))
    metadata_tokens = set(_important_tokens(" ".join(chunk.metadata.values())))

    bonus = 0.0
    if query_tokens & title_tokens:
        bonus += 0.06
    if query_tokens & metadata_tokens:
        bonus += 0.04
    return bonus


def _important_tokens(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def _build_snippet(text: str, max_length: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1].rstrip()}..."
