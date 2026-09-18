# Knowledge Graph contract v1

## Objective and boundaries

Consume the normalized `schema_version: "1.0"` output from branch `quan`
without changing the crawler, normalizer, raw files, or normalized files.
Graph contract version is independently `1.0`. Implement on `nhan` only.
Use Python >= 3.10, standard-library validation/tests, and the official Neo4j
driver. Neo4j 5+ is the target server. This package is a backend library and
CLI; it does not introduce HTTP routes or authentication.

## Input contract

Each dataset requires `schema_version`, `dataset_version`, `symbol`,
`generated_at`, `sources`, `quality`, `meta`, `price_history`, and
`financial_data`. Dataset version is a UTC `YYYYMMDDTHHMMSSZ` identifier
matching the whole seconds of `generated_at`. Sources require `prices` and
`fundamentals`. Unknown top-level fields and provider fields are retained.

The four financial sections are `ratios`, `income_statement`, `balance_sheet`,
and `cash_flow_statement`; all must be nonempty. Periods must be unique within
each section and match `YYYY-Q1`..`YYYY-Q4` or `YYYY-YEAR`. Graph years are
integers. For annual ratios, input `quarter=5` becomes graph `quarter=null`;
the original row remains unchanged. Preserve `ratioType` as the report's
`basis`, especially `RATIO_TTM`: a quarterly period label does not establish
quarter-only coverage. Provider dates remain opaque strings; do not invent
their timezone or a publication time that is absent.

Prices require strictly increasing unique ISO dates, positive finite OHLC
containing open/close within low/high, integer-or-null nonnegative volume,
and an integer `source_timestamp` matching the trading date in UTC+07:00.
`meta` counts/date bounds and quality counts must agree with the actual rows.
Accept both `PASS` and `PASS_WITH_WARNINGS`. Source issues with severity
`ERROR` may describe quarantined rows and do not invalidate clean output.
Reject duplicate JSON keys, nonfinite numbers, missing required sections,
inconsistent symbol/period metadata, nesting beyond 128 levels, and unsupported
schema versions. Every financial row requires the four canonical period fields;
an explicit null quarter is different from a missing field.

## Graph model and identity

| Node | Unique identity | Properties |
| --- | --- | --- |
| Company | symbol | symbol only; no inferred company name or sector |
| Dataset | symbol:dataset_version | checksum, versions, generated_at, source_file, payload_json, quality_json, sources_json, meta_json, status |
| ReportingPeriod | period_label | integer year, quarter or null, period_type |
| FinancialReport | dataset_id:section:period_label | source, basis, period_label, section, payload_json, source_file, json_pointer |
| Metric | source:section:provider_code | code, section, source, unit_status=UNKNOWN |
| Observation | report_id:provider_code | value_json, value_type, numeric value when representable, is_null, json_pointer |
| PriceBar | dataset_id:date | original OHLCV, timestamp, source, source_file, json_pointer |

Relationships: Company `HAS_DATASET` Dataset; Dataset `HAS_REPORT`
FinancialReport; FinancialReport `FOR_PERIOD` ReportingPeriod;
FinancialReport `HAS_OBSERVATION` Observation; Observation `OF_METRIC` Metric;
Dataset `HAS_PRICE` PriceBar. Dataset membership scopes all reads and retains
old versions. A report's JSON pointer locates its original financial row;
an observation extends it with a JSON-Pointer-escaped field name.

Metadata fields (identity, period, provider row IDs/type, create/update/public
dates) stay in report `payload_json`. Other provider fields become
observations, including null and future JSON-valued fields. Preserve zero
and negative values. Do not assign meaning, currency, scaling, or units to
undocumented provider codes. `value_json` preserves every parsed JSON value;
`is_null` distinguishes explicit null from a missing observation because
Neo4j does not store null properties. Integers outside signed 64-bit range
remain available in JSON but are not sent as numeric Neo4j properties.

## Ingestion and backend interface

`to_graph(payload, source_file=...)` validates without mutating input.
`GraphStore.ingest(payload, source_file=...)` returns dataset ID, whether it
was created, and counts. All nodes/edges for one symbol/version are written
in one managed transaction, with batched `UNWIND` queries. This is atomic per
dataset, not per directory. Initialize uniqueness constraints before writes.

Canonical JSON (sorted keys, compact separators, strict finite values) is
hashed with SHA-256. Object key order and file location do not affect the
checksum; array order does. Identical symbol/version/checksum/graph version
returns an unchanged result. Reusing symbol/version with different content
raises `DatasetConflictError`. A unique dataset constraint plus transaction
claim serializes concurrent creation; no check-then-write outside the
transaction. Failed writes roll back the claim and all new graph records.
Schema initialization is separate and idempotent; it is not part of the data
transaction. Stored `payload_json` enables whole-dataset reconstruction.

`get_dataset(symbol, dataset_version=None)` returns the original parsed
payload, or `None`; default is latest COMPLETE version.
`get_observations(symbol, period_label, section, code=None,
dataset_version=None, limit=100, offset=0)` returns values and provenance,
scoped to one snapshot; pagination limit is 1..1000 and offset is a
nonnegative signed 64-bit integer.

Use parameterized Cypher; only fixed package-owned queries/labels are used.
Read credentials only from process environment: `NEO4J_URI`, `NEO4J_USER`,
`NEO4J_PASSWORD`, optional `NEO4J_DATABASE` (default `neo4j`). No automatic
`.env` loading, credential writing, or credentials in CLI arguments/logs.
Support local Bolt and TLS Neo4j URIs. This package does not deploy a server.

## Commands and verification

Run from the repo root with an available Python >= 3.10:

```powershell
python -B -m unittest discover -s backend/tests -p "test_graph*.py" -v
python -B data_pipeline/tests/audit_pipeline.py
python -B -m backend.src.graph.ingest --dry-run
# Install backend requirements in your working virtual environment:
python -m pip install -r backend/requirements.txt
# After configuring process environment and starting Neo4j:
python -B -m backend.src.graph.ingest
```

Dry-run needs no Neo4j driver/server/credentials. CLI validates every file
before connecting; then ingests each dataset in a separate transaction.
Invalid input/configuration exits nonzero. Default input is `data/normalized`
resolved relative to the repository, not the shell's current directory.
Source code uses explicit dataclasses, snake_case, and `ValueError` subclasses
for contract/conflict errors. Tests cover all eight real datasets, immutable
input, periods/TTM/null/zero, provenance, checksum stability, invalid payloads,
driver-boundary transaction behavior and CLI dry-run. Real-server validation
is a separate check and must be reported separately from unit tests.

## Design rationale and official sources

Neo4j follows the existing `backend/scripts/init_neo4j_graph.cypher` layout.
Snapshot identity avoids overwriting restated reports. An adapter handles
provider quirks without changing `quan`'s output. JSON preservation avoids
guessing metric semantics and preserves null/nested values that cannot be
stored directly as Neo4j properties.

- [Managed transactions and parameters](https://neo4j.com/docs/python-manual/current/transactions/)
- [Uniqueness constraints](https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/)
- [Property value limitations](https://neo4j.com/docs/cypher-manual/current/values-and-types/property-structural-constructed/)

## Verification status

Validated on Windows with Python 3.14: 24 graph tests pass, CLI dry-run covers
all eight datasets (17,232 prices and 1,335 reports), and the original pipeline
auditor passes all eight symbols with 394,932 cells checked. Source syntax
also parses under Python 3.10 grammar. The official driver 6.3.1 successfully
serializes FPT graph parameters into Bolt PackStream; dependency checks pass.
The shared `~/.venv` contains the backend dependency. The tracked backend
venv points to another machine and is not used or modified.

No Neo4j server is available. Actual Cypher execution, database rollback and
concurrent ingestion have not been validated against a live database.
