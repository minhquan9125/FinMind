"""Atomic, versioned Neo4j storage. The driver is imported only on connection."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

from .adapter import to_graph
from .contract import GRAPH_VERSION, SECTIONS, ContractError, require


ENV_FILE = Path(__file__).resolve().parents[3] / '.env'


class DatasetConflictError(ContractError):
    """An immutable dataset identity has already been used for other content."""


@dataclass(frozen=True)
class IngestResult:
    dataset_id: str
    created: bool
    counts: dict[str, int]


CLAIM = """
MERGE (d:Dataset {id: $id})
ON CREATE SET d.checksum = $checksum, d.graph_version = $graph_version,
              d.status = 'IMPORTING', d.claim_token = $claim_token
RETURN d.checksum AS checksum, d.graph_version AS graph_version,
       d.status AS status, d.claim_token AS claim_token
"""
DATASET = """
MATCH (d:Dataset {id: $id})
SET d += $properties
MERGE (c:Company {symbol: $symbol})
MERGE (c)-[:HAS_DATASET]->(d)
"""
PERIODS = """
UNWIND $rows AS row
MERGE (p:ReportingPeriod {id: row.id})
SET p += row
"""
METRICS = """
UNWIND $rows AS row
MERGE (m:Metric {id: row.id})
ON CREATE SET m += row
"""
REPORTS = """
MATCH (d:Dataset {id: $id})
UNWIND $rows AS row
MATCH (p:ReportingPeriod {id: row.period_label})
MERGE (r:FinancialReport {id: row.id})
SET r += row
MERGE (d)-[:HAS_REPORT]->(r)
MERGE (r)-[:FOR_PERIOD]->(p)
"""
OBSERVATIONS = """
UNWIND $rows AS row
MATCH (r:FinancialReport {id: row.report_id})
MATCH (m:Metric {id: row.metric_id})
MERGE (o:Observation {id: row.id})
SET o += row
MERGE (r)-[:HAS_OBSERVATION]->(o)
MERGE (o)-[:OF_METRIC]->(m)
"""
PRICES = """
MATCH (d:Dataset {id: $id})
UNWIND $rows AS row
MERGE (p:PriceBar {id: row.id})
SET p += row
MERGE (d)-[:HAS_PRICE]->(p)
"""
SELECT_DATASET = """
MATCH (:Company {symbol: $symbol})-[:HAS_DATASET]->(d:Dataset)
WHERE d.status = 'COMPLETE' AND ($version IS NULL OR d.dataset_version = $version)
WITH d ORDER BY d.dataset_version DESC LIMIT 1
"""
READ_OBSERVATIONS = SELECT_DATASET + """
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:HAS_OBSERVATION]->(o:Observation)
MATCH (o)-[:OF_METRIC]->(m:Metric)
WHERE r.period_label = $period AND r.section = $section
      AND ($code IS NULL OR m.code = $code)
RETURN m.code AS code, m.unit_status AS unit_status, o.value_json AS value_json,
       o.value_type AS value_type, o.is_null AS is_null, r.basis AS basis,
       r.source AS source, r.source_file AS source_file, o.json_pointer AS json_pointer,
       d.id AS dataset_id, d.dataset_version AS dataset_version,
       d.checksum AS checksum, r.period_label AS period_label, r.section AS section
ORDER BY m.code, o.id SKIP $offset LIMIT $limit
"""


class GraphStore:
    """Own a Neo4j driver; methods scope reads/writes to immutable snapshots."""

    def __init__(self, driver, *, database="neo4j", batch_size=1000):
        require(type(batch_size) is int and 1 <= batch_size <= 10000,
                "batch_size must be an integer in 1..10000")
        require(isinstance(database, str) and bool(database.strip()), "database is required")
        self.driver = driver
        self.database = database
        self.batch_size = batch_size
        self._schema_ready = False

    @classmethod
    def from_environment(cls):
        """Read repository .env as fallback; process settings take precedence."""
        values = {}
        if ENV_FILE.is_file():
            try:
                from dotenv import dotenv_values
            except ImportError:
                raise RuntimeError("Install backend/requirements.txt to read .env") from None
            # Keep passwords literal and load only connection settings.
            values = dotenv_values(ENV_FILE, interpolate=False, encoding='utf-8-sig')
        username = os.environ.get('NEO4J_USERNAME',
                                  values.get('NEO4J_USER', values.get('NEO4J_USERNAME')))
        if username is not None:
            os.environ.setdefault('NEO4J_USER', username)
        for name in ('NEO4J_URI', 'NEO4J_PASSWORD', 'NEO4J_DATABASE'):
            if values.get(name) is not None:
                os.environ.setdefault(name, values[name])
        settings = {name: os.environ.get(name, "") for name in
                    ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")}
        require(all(settings.values()), "NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD are required")
        try:
            uri = urlsplit(settings["NEO4J_URI"])
            valid = (uri.scheme in ("bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc")
                     and uri.hostname and uri.username is None and uri.password is None
                     and uri.path in ("", "/") and not uri.fragment)
            uri.port
        except ValueError:
            valid = False
        require(valid, "Invalid NEO4J_URI; credentials must be separate environment variables")
        database = os.environ.get("NEO4J_DATABASE", "neo4j")
        require(bool(database.strip()), "NEO4J_DATABASE cannot be empty")
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise RuntimeError("Install backend/requirements.txt to connect to Neo4j") from None
        driver = GraphDatabase.driver(settings["NEO4J_URI"],
                                      auth=(settings["NEO4J_USER"], settings["NEO4J_PASSWORD"]),
                                      connection_timeout=10, max_transaction_retry_time=30)
        try:
            driver.verify_connectivity()
        except Exception:
            driver.close()
            raise
        return cls(driver, database=database)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.driver.close()

    def ensure_schema(self):
        """Apply package-owned constraints before any dataset claim."""
        if self._schema_ready:
            return
        path = Path(__file__).resolve().parents[2] / "scripts/init_neo4j_graph.cypher"
        statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()
        self._schema_ready = True

    def ingest(self, payload: dict, *, source_file: str = "") -> IngestResult:
        """Validate then atomically import one snapshot, or reject a conflict."""
        graph = to_graph(payload, source_file=source_file)
        self.ensure_schema()
        token = uuid4().hex
        with self.driver.session(database=self.database) as session:
            return session.execute_write(self._write, graph, token)

    def _write(self, tx, graph, token):
        dataset = graph.dataset
        dataset_id = dataset["id"]
        claim = tx.run(CLAIM, id=dataset_id, checksum=dataset["checksum"],
                       graph_version=GRAPH_VERSION, claim_token=token).single(strict=True)
        if claim["checksum"] != dataset["checksum"] or claim["graph_version"] != GRAPH_VERSION:
            raise DatasetConflictError("Dataset identity already has different content or graph version")
        if claim["status"] == "COMPLETE":
            return IngestResult(dataset_id, False, graph.counts())
        if claim["status"] != "IMPORTING" or claim["claim_token"] != token:
            raise DatasetConflictError("Dataset has an incompatible ingestion state")
        tx.run(DATASET, id=dataset_id, properties=dataset, symbol=graph.company["symbol"]).consume()
        for query, rows in ((PERIODS, graph.periods), (METRICS, graph.metrics),
                            (REPORTS, graph.reports), (OBSERVATIONS, graph.observations),
                            (PRICES, graph.prices)):
            for start in range(0, len(rows), self.batch_size):
                tx.run(query, id=dataset_id, rows=list(rows[start:start + self.batch_size])).consume()
        tx.run("MATCH (d:Dataset {id: $id}) SET d.status = 'COMPLETE' REMOVE d.claim_token",
               id=dataset_id).consume()
        return IngestResult(dataset_id, True, graph.counts())

    @staticmethod
    def _read_rows(tx, query, parameters):
        return [dict(record) for record in tx.run(query, **parameters)]

    def get_dataset(self, symbol: str, dataset_version: str | None = None) -> dict | None:
        """Return original input for the latest or specified COMPLETE snapshot."""
        def read(tx):
            record = tx.run(SELECT_DATASET + "RETURN d.payload_json AS payload_json",
                            symbol=symbol, version=dataset_version).single()
            return json.loads(record["payload_json"]) if record is not None else None
        with self.driver.session(database=self.database) as session:
            return session.execute_read(read)

    def get_observations(self, symbol: str, period_label: str, section: str, *,
                         code: str | None = None, dataset_version: str | None = None,
                         limit: int = 100, offset: int = 0) -> list[dict]:
        """Return paginated values and citations scoped to exactly one snapshot."""
        require(isinstance(section, str) and section in SECTIONS, "Unsupported financial section")
        require(isinstance(period_label, str) and
                re.fullmatch(r"[1-9][0-9]{3}-(Q[1-4]|YEAR)", period_label), "Invalid period_label")
        require(type(limit) is int and 1 <= limit <= 1000, "limit must be in 1..1000")
        require(type(offset) is int and 0 <= offset < 2**63,
                "offset must be a nonnegative signed 64-bit integer")
        parameters = {"symbol": symbol, "version": dataset_version, "period": period_label,
                      "section": section, "code": code, "offset": offset, "limit": limit}
        with self.driver.session(database=self.database) as session:
            rows = session.execute_read(self._read_rows, READ_OBSERVATIONS, parameters)
        for row in rows:
            row["value"] = json.loads(row.pop("value_json"))
        return rows
