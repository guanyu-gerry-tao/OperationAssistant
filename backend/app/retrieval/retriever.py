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

    # Validate public request knobs before doing any scoring work.
    if request.strategy not in SUPPORTED_STRATEGIES:
        raise ValueError("Unknown retrieval strategy")
    if request.top_k <= 0:
        raise ValueError("top_k must be positive")

    started_at = perf_counter()
    strategy = request.strategy
    if strategy == "hybrid_rerank_rewrite":
        effective_query = rewrite_query(request.query)
    else:
        effective_query = request.query
    provider = embedding_provider or DeterministicEmbeddingProvider()

    # Build, filter, score, and rank chunks in separate steps so each stage is testable.
    chunks = _chunk_documents(documents)
    filtered_chunks = [chunk for chunk in chunks if _matches_metadata(chunk, request.metadata_filter)]
    scored = [
        _score_chunk(chunk, request.query, effective_query, strategy, provider)
        for chunk in filtered_chunks
    ]
    ranked = sorted(scored, key=lambda chunk: (-chunk.score, chunk.source_id, chunk.chunk_id))

    # Include latency in the response so evals can track retrieval cost over time.
    latency_ms = round((perf_counter() - started_at) * 1000, 3)
    return RetrievalResult(
        query=request.query,
        rewritten_query=effective_query,
        strategy=strategy,  # type: ignore[arg-type]
        chunks=ranked[: request.top_k],
        latency_ms=latency_ms,
    )


def _chunk_documents(documents: list[RunbookDocument]) -> list[DocumentChunk]:
    """Convert loaded runbooks into retrieval chunks."""

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
    """Return whether a chunk satisfies every requested metadata filter."""

    # Empty filters match everything; each provided key must match exactly.
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
    """Score one chunk and attach the citation returned to callers."""

    # Lexical scoring is always computed so the baseline and hybrid strategy are comparable.
    lexical_score = _lexical_score(original_query, chunk)
    if strategy == "lexical":
        score = lexical_score
    else:
        # Hybrid scoring blends term overlap, deterministic vector similarity, and reranking.
        vector_score = _vector_score(effective_query, chunk, embedding_provider)
        rerank_bonus = _rerank_bonus(original_query, chunk)
        score = (0.55 * lexical_score) + (0.35 * vector_score) + rerank_bonus

    # Return a compact snippet plus full citation metadata for grounded UI display.
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
    """Score a chunk by normalized overlap with important query tokens."""

    query_tokens = _important_tokens(query)
    if not query_tokens:
        return 0.0

    # Search title, body, and metadata because runbook labels often carry useful signals.
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
    """Score a chunk with deterministic cosine similarity."""

    # Embed the rewritten query and the citation-bearing chunk text in the same vector space.
    query_vector = embedding_provider.embed(query)
    chunk_vector = embedding_provider.embed(f"{chunk.title} {chunk.text} {' '.join(chunk.metadata.values())}")
    return max(cosine_similarity(query_vector, chunk_vector), 0.0)


def _rerank_bonus(query: str, chunk: DocumentChunk) -> float:
    """Add a small bonus when query terms match high-signal fields."""

    # Title and metadata matches usually mean the runbook is directly about the query.
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
    """Return searchable lowercase tokens after removing common stopwords."""

    return [
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def _build_snippet(text: str, max_length: int = 220) -> str:
    """Return a compact snippet that fits in the retrieval preview panel."""

    # Collapse Markdown whitespace before truncating so snippets stay readable in cards.
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1].rstrip()}..."
