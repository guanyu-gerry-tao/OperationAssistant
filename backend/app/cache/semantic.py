import hashlib
import json
from dataclasses import dataclass


def build_semantic_cache_key(
    *,
    query: str,
    retrieval_context_ids: list[str],
    prompt_version: str,
    safety_mode: str,
) -> str:
    """Build a stable semantic-cache key from the M5 versioned inputs."""

    normalized_payload = {
        "normalized_query": " ".join(query.lower().split()),
        "retrieval_context_ids": sorted(retrieval_context_ids),
        "prompt_version": prompt_version,
        "safety_mode": safety_mode,
    }
    encoded = json.dumps(normalized_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


@dataclass
class InMemorySemanticCache:
    """Small deterministic cache used by the M5 eval arm."""

    records: dict[str, str]

    def get(self, key: str) -> str | None:
        """Return a cached answer when the key exists."""

        return self.records.get(key)

    def set(self, key: str, value: str) -> None:
        """Store an answer under one semantic-cache key."""

        self.records[key] = value
