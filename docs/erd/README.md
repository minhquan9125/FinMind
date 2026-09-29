# FinMind ERD

These DBML files are focused views of the supplied PostgreSQL schema. Import each file separately into dbdiagram.io. Shared lookup/source tables may appear in more than one view to keep each diagram understandable.

## Diagrams

- `00_full_erd_overview.dbml`: all 36 tables in one overview, showing keys and selected identifiers for a whole-system screenshot. Use this as a map; it intentionally omits most non-key columns to keep the complete diagram legible.
- `01_financial_core.dbml`: companies, periods, datasets, statements, facts, prices, and source documents.
- `02_document_chunk_stores.dbml`: source documents and the older `text_chunks`/`embeddings` path.
- `03_active_vector_rag.dbml`: current API ingestion and vector-search storage (`rag_*`).
- `04_query_evidence.dbml`: query/retrieval/evidence/citation tracking; highlights the current chunk-FK mismatch.
- `05_security_operations.dbml`: users, roles, sessions, feedback, audit, and configuration.
- `06_corpus_evaluation.dbml`: corpus snapshots and evaluation data.
- `07_postgres_graph_tables.dbml`: graph-shaped tables stored in PostgreSQL. This is not a Neo4j schema or proof of a Neo4j connection.
- `08_target_normalized_full_overview.dbml`: proposed full-system overview with the duplicate RAG tables removed (34 tables); not the current live schema.
- `09_target_normalized_vector_rag.dbml`: proposed detailed Vector RAG target; not the current live schema.
- `10_api_financial_news_target.dbml`: proposed target for financial API data normalized to JSON/facts plus scraped news stored as source documents and vectorized chunks. Neo4j remains outside the PostgreSQL ERD.

## Canonical Vector RAG path found in code

The FastAPI document endpoints write to `rag_documents` and `rag_document_chunks`. The search endpoint reads `rag_document_chunks`. The separate `backend/ingest_to_vector.py` script writes to `documents`, `text_chunks`, and `embeddings` and is a competing ingestion path.

There is a schema/code mismatch to resolve: `vector_retrieval_results.chunk_id` and `answer_citations.chunk_id` reference `text_chunks`, while the active API search returns chunks from `rag_document_chunks`. The current diagrams preserve the supplied FKs as-is and mark the mismatch in notes; they do not silently redraw the database as though those FKs had already changed.

Recommended target: consolidate on `documents -> text_chunks -> embeddings`. The existing retrieval-result and citation foreign keys already point to `text_chunks`, and a separate `embeddings` table can retain model/version metadata. Migrate the active FastAPI ingestion/search code to this chain, then retire or migrate the `rag_*` path. Do not delete existing tables or records until rows and all callers have been checked.

The `10_api_financial_news_target.dbml` diagram applies that target to the requested ingestion plan: structured financial API JSON is represented by datasets/reports/observations, while news articles are source documents with publication/scrape metadata and chunks for vector retrieval. This is a target design; the active API still writes the `rag_*` tables until migrated.

For the proposed normalized full-system overview, see `08_target_normalized_full_overview.dbml`; for the detailed RAG schema, see `09_target_normalized_vector_rag.dbml`. Both keep `documents -> text_chunks -> embeddings` and drop the duplicate `rag_documents` / `rag_document_chunks` layer in the target model. Adopting that target requires migrating the active FastAPI repository/search code first; these files are proposals, not ready-to-run migrations.

`rag_documents` can link to the business `documents` table using `source_document_id`, but the current API repository only inserts `id`, `filename`, and `page_count`; those source links are not populated by that path yet.

## Scope notes

- `graph_nodes` and `graph_edges` are PostgreSQL tables. Neo4j must be shown separately in an architecture diagram if/when the application has a Neo4j driver, sync path, and graph queries.
- The supplied schema dump reports embedding columns as `USER-DEFINED`; the migration in `backend/scripts/init_postgres_schema.sql` defines the RAG embedding as `public.vector(1024)`. Confirm the live Supabase type and index before describing that as deployed state.
- These are documentation views, not SQL migrations. They do not change Supabase.
