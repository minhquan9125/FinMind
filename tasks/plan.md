# Knowledge Graph implementation plan

Approved scope: work on `nhan`; preserve `quan` crawler, normalization and data.
Contract: [Knowledge Graph v1](../docs/knowledge_graph_contract.md).

1. Define and test normalized schema 1.0 validation and graph projection.
   Preserve original JSON and source pointers; adapt year/quarter/TTM metadata.
2. Implement Neo4j uniqueness constraints, transaction claims, immutable
   dataset snapshots, batched ingestion, and paginated provenance reads.
3. Add CLI preflight and dry-run without a database dependency.
4. Verify all real datasets, transaction callback failure paths, conflicts,
   repeated ingestion, parameter safety and credential-safe CLI errors.
5. Review changes, run the original pipeline auditor, confirm `quan` and
   crawler/data remain unchanged, and save separate contract/store commits.

Live database validation requires a Neo4j server. The user confirmed none is
currently available; offline results must not be described as live ingestion.
