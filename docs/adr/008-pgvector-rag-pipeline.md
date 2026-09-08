# ADR 008: pgvector RAG Pipeline and Document Grounding

## Context

RetailOps AI agents reason over structured ERP data via StockPilot HTTP tools (inventory, purchase orders, sales transactions). However, certain operational decisions require unstructured domain knowledge — such as supplier SLA guidelines, return/refund policies, safety-stock standard operating procedures (SOPs), and perishable shelf-life handling rules.

To support unstructured context without compromising the platform's core zero-hallucination invariant (CLAUDE.md Invariant 1: Grounded Numbers & Invariant 2: Explicit Citations), we define this Architecture Decision Record for the Retrieval-Augmented Generation (RAG) subsystem.

## Decision

### 1. Document Corpus
The RAG corpus contains operational enterprise knowledge organized into versioned collections:
- **Supplier Agreements & SLAs**: Guaranteed lead times, penalty clauses, minimum order quantities (MOQs), and return allowances.
- **Inventory SOPs**: Reorder cycle rules, ABC/XYZ classification policies, and safety stock adjustment guidelines.
- **Product Care & Expiry Handling**: Shelf-life expiry alerts, temperature-sensitive storage instructions, and batch quarantine rules.

### 2. Embedding Provider & Vector Storage
- **Embedding Provider**: Google GenAI `text-embedding-004` (768 dimensions), with deterministic fallback/mocking for offline test suites.
- **Vector Storage**: PostgreSQL `pgvector` extension with HNSW / IVFFlat cosine distance indexing (`vector_cosine_ops`), storing embeddings in a `rag_documents` table within the `retailops-ai` database schema.

### 3. Retention & Ingestion Strategy
- Documents are split into semantic chunks (300–500 tokens) with 50-token overlap.
- Each chunk stores `document_id`, `chunk_index`, `title`, `category`, `content`, `metadata_json`, and `embedding (vector(768))`.
- Ingestion runs via an idempotent CLI script `python -m scripts.ingest_rag_corpus` that re-embeds only modified document hashes.

### 4. Citation Format & Tool Interface
- The retrieval tool `search_operational_documents(query: str, category: str | None = None, top_k: int = 3)` returns matched text chunks with similarity scores.
- RAG citations follow the standard envelope: `{"source": "rag_document", "document_id": "...", "title": "...", "section": "..."}`.

### 5. Provenance Mapping
- Numbers or metrics extracted from policy documents carry `"inferred"` or `"observed"` policy provenance.
- The Citation Validator verifies that all cited policy statements match the returned document chunk content.

## Consequences
- Agents can provide context-aware recommendations (e.g. why a supplier is delayed against their contractual SLA) grounded in verified contract text.
- Full offline testability is preserved via mock vector distance calculation in SQLite / test environments.
