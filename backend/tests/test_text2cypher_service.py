from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from neo4j import GraphDatabase, Record
from neo4j_graphrag.llm import LLMResponse
from neo4j_graphrag.exceptions import Text2CypherRetrievalError
from neo4j_graphrag.retrievers import Text2CypherRetriever

from backend.src.graph.text2cypher_service import (
    FINMIND_NEO4J_SCHEMA,
    ReadOnlyCypherError,
    Text2CypherService,
    Text2CypherServiceError,
    validate_read_only_cypher,
)


SAFE_QUERY = """
MATCH (c:Company {symbol: 'FPT'})-[:HAS_DATASET]->(d:Dataset)
WHERE d.status = 'COMPLETE'
WITH c, d
MATCH (d)-[:HAS_REPORT]->(r:FinancialReport)
WHERE r.period_label = '2026-Q2'
RETURN c.symbol AS symbol, r.period_label AS period
"""


class FakeLLM:
    def __init__(self, cypher):
        self.cypher = cypher
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return LLMResponse(content=self.cypher)


class ReadOnlyCypherValidationTests(unittest.TestCase):
    def test_allows_only_supported_read_clauses(self):
        self.assertEqual(validate_read_only_cypher(SAFE_QUERY), SAFE_QUERY.strip())
        self.assertEqual(validate_read_only_cypher("RETURN 'CREATE' AS text"),
                         "RETURN 'CREATE' AS text")

    def test_blocks_write_commands_before_execution(self):
        blocked = (
            "CREATE (:Company {symbol: 'BAD'}) RETURN 1",
            "MATCH (n) MERGE (x:Company) RETURN x",
            "MATCH (n) DELETE n RETURN 1",
            "MATCH (n) DETACH DELETE n RETURN 1",
            "MATCH (n) SET n.symbol = 'BAD' RETURN n",
            "MATCH (n) REMOVE n.symbol RETURN n",
            "DROP CONSTRAINT finmind_company_symbol RETURN 1",
        )
        for query in blocked:
            with self.subTest(query=query), self.assertRaises(ReadOnlyCypherError):
                validate_read_only_cypher(query)

    def test_blocks_unapproved_clauses_comments_and_multiple_statements(self):
        blocked = (
            "CALL db.labels() YIELD label RETURN label",
            "MATCH (n) RETURN n LIMIT 1",
            "MATCH (n) RETURN n FINISH",
            "MATCH (n) RETURN n; MATCH (m) RETURN m",
            "MATCH (n) // hidden\nRETURN n",
            "MATCH (n) /* hidden */ RETURN n",
        )
        for query in blocked:
            with self.subTest(query=query), self.assertRaises(ReadOnlyCypherError):
                validate_read_only_cypher(query)


class Text2CypherServiceTests(unittest.TestCase):
    def setUp(self):
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test-only"))
        self.addCleanup(self.driver.close)

    def test_uses_text2cypher_with_explicit_schema_and_returns_raw_records(self):
        llm = FakeLLM(SAFE_QUERY)
        calls = []

        def execute_query(query_, **kwargs):
            calls.append((query_, kwargs))
            summary = SimpleNamespace(query_type="r")
            if query_.startswith("EXPLAIN "):
                return [], summary, []
            return [Record((("symbol", "FPT"), ("period", "2026-Q2")))], summary, ["symbol", "period"]

        with patch.object(Text2CypherRetriever, "VERIFY_NEO4J_VERSION", False), \
                patch.object(self.driver, "execute_query", side_effect=execute_query):
            service = Text2CypherService(self.driver, llm, database="neo4j")
            result = service.query("Tổng tài sản FPT quý 2/2026 là bao nhiêu?")

        self.assertEqual(result.cypher, SAFE_QUERY.strip())
        self.assertEqual(result.records, [{"symbol": "FPT", "period": "2026-Q2"}])
        self.assertIsNone(result.error)
        self.assertIn("Company {symbol: STRING}", llm.prompt)
        self.assertIn("bsa53 means total assets", llm.prompt)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].startswith("EXPLAIN "))
        self.assertTrue(calls[0][0][len("EXPLAIN "):].lstrip().startswith("MATCH"))

    def test_llm_write_query_is_rejected_before_driver_execution(self):
        llm = FakeLLM("MATCH (n) DETACH DELETE n RETURN n")
        with patch.object(Text2CypherRetriever, "VERIFY_NEO4J_VERSION", False), \
                patch.object(self.driver, "execute_query") as execute_query:
            service = Text2CypherService(self.driver, llm, database="neo4j")
            with self.assertRaises(ReadOnlyCypherError):
                service.query("Xóa dữ liệu")
        execute_query.assert_not_called()

    def test_retriever_exception_is_wrapped_for_the_api(self):
        with patch.object(Text2CypherRetriever, "VERIFY_NEO4J_VERSION", False):
            service = Text2CypherService(self.driver, FakeLLM(SAFE_QUERY), database="neo4j")
        service.retriever = MagicMock()
        service.retriever.get_search_results.side_effect = Text2CypherRetrievalError(
            "generated Cypher has invalid syntax"
        )
        with self.assertRaisesRegex(Text2CypherServiceError, "Text2Cypher failed"):
            service.query("Câu hỏi tạo Cypher lỗi")

    def test_schema_describes_only_existing_graph_elements(self):
        for label in ("Company", "Dataset", "ReportingPeriod", "FinancialReport",
                      "Metric", "Observation", "PriceBar"):
            self.assertIn(label, FINMIND_NEO4J_SCHEMA)
        for relationship in ("HAS_DATASET", "HAS_REPORT", "FOR_PERIOD",
                             "HAS_OBSERVATION", "OF_METRIC", "HAS_PRICE"):
            self.assertIn(relationship, FINMIND_NEO4J_SCHEMA)
        self.assertNotIn("industry: STRING", FINMIND_NEO4J_SCHEMA)


if __name__ == "__main__":
    unittest.main()
