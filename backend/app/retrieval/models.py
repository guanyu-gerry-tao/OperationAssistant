from dataclasses import dataclass, field
from typing import Literal


RetrievalStrategy = Literal["lexical", "hybrid_rerank_rewrite"]


@dataclass(frozen=True)
class RunbookDocument:
    """A source document loaded from the local runbook corpus."""

    document_id: str
    source_id: str
    title: str
    source_path: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentChunk:
    """A retrievable section of a runbook with source metadata."""

    chunk_id: str
    document_id: str
    source_id: str
    title: str
    source_path: str
    text: str
    metadata: dict[str, str]
    chunk_index: int


@dataclass(frozen=True)
class Citation:
    """Source details attached to a retrieved chunk."""

    source_id: str
    source_title: str
    source_path: str
    chunk_id: str


@dataclass(frozen=True)
class ScoredChunk:
    """A ranked retrieval hit returned by the API and eval runner."""

    chunk_id: str
    source_id: str
    title: str
    snippet: str
    score: float
    metadata: dict[str, str]
    citation: Citation


@dataclass(frozen=True)
class RetrievalRequest:
    """Inputs for one retrieval query."""

    query: str
    strategy: RetrievalStrategy | str = "hybrid_rerank_rewrite"
    top_k: int = 3
    metadata_filter: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """Ranked retrieval output with the effective query."""

    query: str
    rewritten_query: str
    strategy: RetrievalStrategy
    chunks: list[ScoredChunk]
    latency_ms: float
