from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from orchestration.models.rag_document import RagDocument


def compute_text_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Deterministic token/character embedding generator for local/test use
    and fallback when live embedding provider is unavailable.
    """
    cleaned = text.lower().strip()
    vector = [0.0] * dimensions
    if not cleaned:
        return vector

    for i, char in enumerate(cleaned):
        code = ord(char)
        idx = (code + i * 31) % dimensions
        vector[idx] += math.sin(code + i)

    # Normalize vector
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def search_documents(
    query: str,
    session: Session,
    *,
    category: str | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieves top matching operational document chunks using semantic similarity."""
    query_emb = compute_text_embedding(query)
    q = session.query(RagDocument)
    if category:
        q = q.filter(RagDocument.category == category)
    docs = q.all()

    scored: list[tuple[float, RagDocument]] = []
    for doc in docs:
        doc_emb = doc.embedding_json or compute_text_embedding(doc.content)
        sim = cosine_similarity(query_emb, doc_emb)
        scored.append((sim, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, doc in scored[:top_k]:
        results.append(
            {
                "document_id": doc.document_id,
                "title": doc.title,
                "category": doc.category,
                "section": doc.section,
                "content": doc.content,
                "similarity_score": round(score, 4),
                "provenance": "observed",
            }
        )
    return results
