import hashlib
import math
import re


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class DeterministicEmbeddingProvider:
    """Local embedding adapter used for reproducible tests and offline demos."""

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        """Return a normalized hash-bucket vector for the provided text."""

        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector

        return [round(value / magnitude, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two already-sized vectors."""

    if len(left) != len(right) or not left:
        return 0.0

    left_mag = math.sqrt(sum(value * value for value in left))
    right_mag = math.sqrt(sum(value * value for value in right))
    if left_mag == 0 or right_mag == 0:
        return 0.0

    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_mag * right_mag)
