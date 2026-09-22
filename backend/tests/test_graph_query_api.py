import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.src.graph.text2cypher_service import GraphQueryResult, Text2CypherServiceError
from backend.src.main import app


class GraphQueryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_graph_query_success_contract(self):
        service = MagicMock()
        service.query.return_value = GraphQueryResult(
            question="Tổng tài sản FPT quý 2/2026 là bao nhiêu?",
            cypher="MATCH (c:Company) RETURN c.symbol AS symbol",
            records=[{"symbol": "FPT"}],
            error=None,
        )
        with patch("backend.src.main.Text2CypherService.from_environment",
                   return_value=service):
            response = self.client.post("/api/graph/query", json={
                "question": "Tổng tài sản FPT quý 2/2026 là bao nhiêu?"
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "question": "Tổng tài sản FPT quý 2/2026 là bao nhiêu?",
            "cypher": "MATCH (c:Company) RETURN c.symbol AS symbol",
            "records": [{"symbol": "FPT"}],
            "error": None,
        })
        service.close.assert_called_once()

    def test_retriever_exception_is_returned_in_response_envelope(self):
        service = MagicMock()
        service.query.side_effect = Text2CypherServiceError(
            "Text2Cypher could not generate a valid read-only query"
        )
        with patch("backend.src.main.Text2CypherService.from_environment",
                   return_value=service):
            response = self.client.post("/api/graph/query", json={"question": "Câu hỏi lỗi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["records"], [])
        self.assertIsNone(response.json()["cypher"])
        self.assertIn("Text2Cypher", response.json()["error"])
        service.close.assert_called_once()

    def test_question_is_required_and_bounded(self):
        for body in ({}, {"question": "   "}, {"question": "x" * 1001}):
            with self.subTest(body=list(body)):
                response = self.client.post("/api/graph/query", json=body)
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
