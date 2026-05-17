from backend.app.retrieval.models import DocumentChunk


def chunk_document_text(
    *,
    document_id: str,
    source_path: str,
    title: str,
    text: str,
    metadata: dict[str, str],
    max_words: int = 90,
    overlap_words: int = 15,
) -> list[DocumentChunk]:
    """Split a document into overlapping word chunks while preserving citation metadata."""

    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("overlap_words must be lower than max_words")

    words = text.split()
    if not words:
        return []

    source_id = metadata.get("source_id", document_id)
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append(
            DocumentChunk(
                chunk_id=f"{source_id}-{index + 1:03d}",
                document_id=document_id,
                source_id=source_id,
                title=title,
                source_path=source_path,
                text=chunk_text,
                metadata=dict(metadata),
                chunk_index=index,
            )
        )
        if end == len(words):
            break
        start = end - overlap_words
        index += 1

    return chunks
