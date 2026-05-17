from pathlib import Path

from backend.app.retrieval.models import RunbookDocument


RUNBOOK_DIR = Path("data/runbooks")


def load_runbook_documents(runbook_dir: Path = RUNBOOK_DIR) -> list[RunbookDocument]:
    """Load Markdown runbooks with simple front matter metadata."""

    documents = []
    for path in sorted(runbook_dir.glob("*.md")):
        metadata, body = _parse_markdown_with_front_matter(path.read_text(encoding="utf-8"))
        source_id = metadata.get("source_id", path.stem)
        title = metadata.get("title", path.stem.replace("_", " ").title())
        documents.append(
            RunbookDocument(
                document_id=source_id,
                source_id=source_id,
                title=title,
                source_path=path.as_posix(),
                text=body.strip(),
                metadata={**metadata, "source_id": source_id, "title": title},
            )
        )

    return documents


def _parse_markdown_with_front_matter(raw_text: str) -> tuple[dict[str, str], str]:
    if not raw_text.startswith("---"):
        return {}, raw_text

    sections = raw_text.split("---", 2)
    if len(sections) < 3:
        return {}, raw_text

    metadata: dict[str, str] = {}
    for line in sections[1].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"')

    return metadata, sections[2]
