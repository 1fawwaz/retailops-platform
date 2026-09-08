from __future__ import annotations

from sqlalchemy.orm import Session

from orchestration.models.rag_document import RagDocument
from services.rag import compute_text_embedding, cosine_similarity, search_documents


def test_compute_embedding_normalized() -> None:
    emb = compute_text_embedding("Supplier SLA Lead Time Policy")
    assert len(emb) == 64
    norm = sum(x * x for x in emb)
    assert 0.99 <= norm <= 1.01


def test_cosine_similarity_identical() -> None:
    v1 = [0.6, 0.8]
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-6


def test_search_documents(db_session: Session) -> None:
    doc1 = RagDocument(
        document_id="SLA-001",
        title="Supplier SLA Contract",
        category="supplier",
        section="Lead Times",
        content="Suppliers must deliver within 5 business days or incur a 2% daily penalty.",
        embedding_json=compute_text_embedding("supplier deliver lead time penalty"),
    )
    doc2 = RagDocument(
        document_id="INV-001",
        title="Inventory Quarantine SOP",
        category="inventory",
        section="Expiry Handling",
        content="Items within 30 days of shelf life expiration must be quarantined immediately.",
        embedding_json=compute_text_embedding("quarantine expired items shelf life"),
    )
    db_session.add_all([doc1, doc2])
    db_session.commit()

    results = search_documents("supplier delivery penalty lead time", db_session, top_k=1)
    assert len(results) == 1
    assert results[0]["document_id"] == "SLA-001"
    assert "2%" in results[0]["content"]
    assert results[0]["provenance"] == "observed"
