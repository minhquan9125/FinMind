"""Natural-language to read-only Cypher queries for the FinMind graph."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

from neo4j_graphrag.exceptions import Neo4jGraphRagError
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.retrievers.text2cypher import extract_cypher

from .graph_store import ENV_FILE, GraphStore


FINMIND_NEO4J_SCHEMA = """
Node properties:
Company {symbol: STRING}
Dataset {id: STRING, symbol: STRING, dataset_version: STRING, schema_version: STRING,
         graph_version: STRING, generated_at: STRING, source_file: STRING, checksum: STRING,
         payload_json: STRING, quality_json: STRING, sources_json: STRING, meta_json: STRING,
         status: STRING}
ReportingPeriod {id: STRING, year: INTEGER, quarter: INTEGER, period_type: STRING}
FinancialReport {id: STRING, section: STRING, period_label: STRING, source: STRING,
                 basis: STRING, payload_json: STRING, source_file: STRING, json_pointer: STRING}
Metric {id: STRING, code: STRING, section: STRING, source: STRING, unit_status: STRING}
Observation {id: STRING, report_id: STRING, metric_id: STRING, code: STRING,
             value: FLOAT, value_json: STRING, value_type: STRING, is_null: BOOLEAN,
             json_pointer: STRING}
PriceBar {id: STRING, date: STRING, open: FLOAT, high: FLOAT, low: FLOAT, close: FLOAT,
          volume: INTEGER, source_timestamp: INTEGER, source: STRING, source_file: STRING,
          json_pointer: STRING, payload_json: STRING}

Relationship properties:
No relationship has properties.

The relationships:
(:Company)-[:HAS_DATASET]->(:Dataset)
(:Dataset)-[:HAS_REPORT]->(:FinancialReport)
(:FinancialReport)-[:FOR_PERIOD]->(:ReportingPeriod)
(:FinancialReport)-[:HAS_OBSERVATION]->(:Observation)
(:Observation)-[:OF_METRIC]->(:Metric)
(:Dataset)-[:HAS_PRICE]->(:PriceBar)

Domain facts needed to interpret the provider codes already stored in Metric.code:
- In section "balance_sheet", bsa53 means total assets (tổng tài sản).
- In section "balance_sheet", bsa54 means total liabilities (nợ phải trả).
- In section "balance_sheet", bsa78 means owners' equity (vốn chủ sở hữu).
- Financial amounts are raw provider values. Metric.unit_status is currently "UNKNOWN".
- Company has no industry or sector property. Never invent one. For an industry question,
  return null as industry and a note explaining that industry is unavailable.
- Only Dataset nodes whose status is "COMPLETE" are queryable snapshots.
- If a company has multiple COMPLETE datasets, use the dataset for which no newer COMPLETE
  dataset_version exists. dataset_version is a sortable UTC string like 20260915T093340Z.
- Vietnamese "quý N/YYYY" maps to period_label "YYYY-QN".
""".strip()


TEXT2CYPHER_EXAMPLES = [
    """USER INPUT: 'FPT thuộc ngành nào?'
QUERY: MATCH (c:Company) WHERE c.symbol = 'FPT'
RETURN c.symbol AS symbol, null AS industry,
       'Industry is not available in the current graph schema' AS note""",
    """USER INPUT: 'Tổng tài sản FPT quý 2/2026 là bao nhiêu?'
QUERY: MATCH (c:Company)-[:HAS_DATASET]->(d:Dataset)
WHERE c.symbol = 'FPT' AND d.status = 'COMPLETE'
  AND NOT EXISTS {
    MATCH (c)-[:HAS_DATASET]->(newer:Dataset)
    WHERE newer.status = 'COMPLETE' AND newer.dataset_version > d.dataset_version
  }
WITH d
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:HAS_OBSERVATION]->(o:Observation)-[:OF_METRIC]->(m:Metric)
WHERE r.section = 'balance_sheet' AND r.period_label = '2026-Q2' AND m.code = 'bsa53'
RETURN r.period_label AS period, m.code AS metric_code, o.value AS value,
       m.unit_status AS unit_status, r.source AS source, o.json_pointer AS json_pointer""",
    """USER INPUT: 'Nợ phải trả FPT quý 2/2026 là bao nhiêu?'
QUERY: MATCH (c:Company)-[:HAS_DATASET]->(d:Dataset)
WHERE c.symbol = 'FPT' AND d.status = 'COMPLETE'
  AND NOT EXISTS {
    MATCH (c)-[:HAS_DATASET]->(newer:Dataset)
    WHERE newer.status = 'COMPLETE' AND newer.dataset_version > d.dataset_version
  }
WITH d
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:HAS_OBSERVATION]->(o:Observation)-[:OF_METRIC]->(m:Metric)
WHERE r.section = 'balance_sheet' AND r.period_label = '2026-Q2' AND m.code = 'bsa54'
RETURN r.period_label AS period, m.code AS metric_code, o.value AS value,
       m.unit_status AS unit_status, r.source AS source, o.json_pointer AS json_pointer""",
    """USER INPUT: 'Vốn chủ sở hữu FPT quý 2/2026 là bao nhiêu?'
QUERY: MATCH (c:Company)-[:HAS_DATASET]->(d:Dataset)
WHERE c.symbol = 'FPT' AND d.status = 'COMPLETE'
  AND NOT EXISTS {
    MATCH (c)-[:HAS_DATASET]->(newer:Dataset)
    WHERE newer.status = 'COMPLETE' AND newer.dataset_version > d.dataset_version
  }
WITH d
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:HAS_OBSERVATION]->(o:Observation)-[:OF_METRIC]->(m:Metric)
WHERE r.section = 'balance_sheet' AND r.period_label = '2026-Q2' AND m.code = 'bsa78'
RETURN r.period_label AS period, m.code AS metric_code, o.value AS value,
       m.unit_status AS unit_status, r.source AS source, o.json_pointer AS json_pointer""",
    """USER INPUT: 'FPT có những kỳ báo cáo nào?'
QUERY: MATCH (c:Company)-[:HAS_DATASET]->(d:Dataset)
WHERE c.symbol = 'FPT' AND d.status = 'COMPLETE'
  AND NOT EXISTS {
    MATCH (c)-[:HAS_DATASET]->(newer:Dataset)
    WHERE newer.status = 'COMPLETE' AND newer.dataset_version > d.dataset_version
  }
WITH d
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:FOR_PERIOD]->(p:ReportingPeriod)
RETURN DISTINCT p.id AS period_label, p.period_type AS period_type""",
    """USER INPUT: 'So sánh tổng tài sản FPT giữa hai kỳ gần nhất.'
QUERY: MATCH (c:Company)-[:HAS_DATASET]->(d:Dataset)
WHERE c.symbol = 'FPT' AND d.status = 'COMPLETE'
  AND NOT EXISTS {
    MATCH (c)-[:HAS_DATASET]->(newer:Dataset)
    WHERE newer.status = 'COMPLETE' AND newer.dataset_version > d.dataset_version
  }
WITH d
MATCH (d)-[:HAS_REPORT]->(latestReport:FinancialReport)-[:FOR_PERIOD]->(latestPeriod:ReportingPeriod)
WHERE latestReport.section = 'balance_sheet' AND latestPeriod.period_type = 'QUARTER'
WITH d, max(latestPeriod.id) AS latest
MATCH (d)-[:HAS_REPORT]->(previousReport:FinancialReport)-[:FOR_PERIOD]->(previousPeriod:ReportingPeriod)
WHERE previousReport.section = 'balance_sheet' AND previousPeriod.period_type = 'QUARTER'
  AND previousPeriod.id < latest
WITH d, latest, max(previousPeriod.id) AS previous
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)-[:HAS_OBSERVATION]->(o:Observation)-[:OF_METRIC]->(m:Metric)
WHERE r.section = 'balance_sheet' AND m.code = 'bsa53'
  AND (r.period_label = latest OR r.period_label = previous)
RETURN r.period_label AS period, o.value AS total_assets,
       m.unit_status AS unit_status, r.source AS source, o.json_pointer AS json_pointer""",
]


TEXT2CYPHER_PROMPT = """
Task: Generate exactly one Cypher statement for the user's question.

Schema:
{schema}

Examples:
{examples}

Input:
{query_text}

Security and correctness rules:
- Use only MATCH, OPTIONAL MATCH, WHERE, WITH and RETURN clauses.
- Do not use ORDER BY, SKIP, LIMIT, CALL, YIELD, UNWIND, UNION, LOAD CSV or FOREACH.
- Never use CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP or any write operation.
- Use only labels, relationships and properties listed in the schema.
- Do not guess missing facts. Return a null value with a clear note when the schema says a fact is unavailable.
- Return primitive fields rather than whole nodes or relationships.
- Return only Cypher. Do not include markdown fences or an explanation.

Cypher query:
""".strip()


class ReadOnlyCypherError(ValueError):
    """The generated statement is outside the prototype's read-only subset."""


class Text2CypherServiceError(RuntimeError):
    """A safe, user-facing Text2Cypher or Neo4j failure."""


class Text2CypherConfigurationError(Text2CypherServiceError):
    """Required environment configuration is missing or invalid."""


@dataclass(frozen=True)
class GraphQueryResult:
    question: str
    cypher: str | None
    records: list[dict[str, Any]]
    error: str | None = None


_FORBIDDEN = re.compile(
    r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|YIELD|UNWIND|UNION|"
    r"LOAD\s+CSV|FOREACH|USE|SHOW|TERMINATE|ALTER|GRANT|DENY|REVOKE|INSERT|"
    r"PROFILE|EXPLAIN|START|FINISH|ORDER\s+BY|SKIP|LIMIT)\b",
    re.IGNORECASE,
)
_ALLOWED_START = re.compile(r"^(?:OPTIONAL\s+MATCH|MATCH|RETURN)\b", re.IGNORECASE)


def _code_without_literals(query: str) -> str:
    """Blank strings/backtick identifiers so command checks ignore their contents."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(query):
        char = query[index]
        following = query[index + 1] if index + 1 < len(query) else ""
        if quote is None:
            if char in ("'", '"', '`'):
                quote = char
                output.append(" ")
            elif char == "/" and following in ("/", "*"):
                raise ReadOnlyCypherError("Cypher comments are not allowed")
            elif char == ";":
                raise ReadOnlyCypherError("Only one Cypher statement is allowed")
            else:
                output.append(char)
        else:
            output.append(" ")
            if char == "\\" and quote != '`' and following:
                output.append(" ")
                index += 1
            elif char == quote:
                if following == quote:
                    output.append(" ")
                    index += 1
                else:
                    quote = None
        index += 1
    if quote is not None:
        raise ReadOnlyCypherError("Generated Cypher contains an unterminated literal")
    return "".join(output)


def validate_read_only_cypher(query: str) -> str:
    """Accept the deliberately small read-only Cypher subset used by this prototype."""
    if not isinstance(query, str) or not query.strip():
        raise ReadOnlyCypherError("Generated Cypher is empty")
    normalized = query.strip()
    if len(normalized) > 20_000:
        raise ReadOnlyCypherError("Generated Cypher is too long")
    code = _code_without_literals(normalized)
    if not _ALLOWED_START.match(code.lstrip()):
        raise ReadOnlyCypherError(
            "Cypher must start with MATCH, OPTIONAL MATCH or RETURN"
        )
    forbidden = _FORBIDDEN.search(code)
    if forbidden:
        command = " ".join(forbidden.group(0).upper().split())
        raise ReadOnlyCypherError(f"Cypher command is not allowed: {command}")
    if not re.search(r"\bRETURN\b", code, re.IGNORECASE):
        raise ReadOnlyCypherError("Cypher must contain RETURN")
    return normalized


class _ValidatingLLM:
    """Validate the generated statement before the retriever can execute it."""

    def __init__(self, delegate):
        self.delegate = delegate

    def invoke(self, prompt):
        response = self.delegate.invoke(prompt)
        validate_read_only_cypher(extract_cypher(response.content))
        return response


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        return {str(key): _json_value(item) for key, item in dict(value).items()}
    except (TypeError, ValueError):
        return str(value)


class Text2CypherService:
    """Own a Text2CypherRetriever and expose raw records for inspection."""

    def __init__(self, driver, llm, *, database: str = "neo4j", owns_driver: bool = False):
        self.driver = driver
        self.database = database
        self.owns_driver = owns_driver
        self.retriever = Text2CypherRetriever(
            driver=driver,
            llm=_ValidatingLLM(llm),
            neo4j_schema=FINMIND_NEO4J_SCHEMA,
            examples=TEXT2CYPHER_EXAMPLES,
            custom_prompt=TEXT2CYPHER_PROMPT,
            neo4j_database=database,
        )

    @classmethod
    def from_environment(cls) -> "Text2CypherService":
        values: dict[str, Any] = {}
        if Path(ENV_FILE).is_file():
            from dotenv import dotenv_values
            values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        api_key = os.environ.get("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
        model = os.environ.get("GRAPH_LLM_MODEL") or values.get("GRAPH_LLM_MODEL")
        if not api_key:
            raise Text2CypherConfigurationError("OPENAI_API_KEY is required in the environment or .env")
        if not model:
            raise Text2CypherConfigurationError("GRAPH_LLM_MODEL is required in the environment or .env")

        store = GraphStore.from_environment()
        try:
            llm = OpenAILLM(
                model_name=str(model),
                api_key=str(api_key),
                model_params={"temperature": 0},
            )
            return cls(store.driver, llm, database=store.database, owns_driver=True)
        except Exception:
            store.close()
            raise

    def close(self) -> None:
        if self.owns_driver:
            self.driver.close()

    def query(self, question: str) -> GraphQueryResult:
        question = question.strip()
        try:
            result = self.retriever.get_search_results(query_text=question)
            metadata = result.metadata or {}
            cypher = validate_read_only_cypher(metadata.get("cypher", ""))
            records = [
                {str(key): _json_value(value) for key, value in dict(record).items()}
                for record in result.records
            ]
            return GraphQueryResult(question=question, cypher=cypher, records=records)
        except ReadOnlyCypherError:
            raise
        except Neo4jGraphRagError as exc:
            raise Text2CypherServiceError(f"Text2Cypher failed: {exc}") from exc
        except Exception as exc:
            raise Text2CypherServiceError(
                "Neo4j query failed; check the generated Cypher, database connection and LLM settings"
            ) from exc
