"""Unit tests for B1 citation and answer verifier with Vu's locator_resolver.

Written with unittest.IsolatedAsyncioTestCase to run with standard library.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.documents.b1_citation_verifier import (
    AuditReport,
    B1AnswerCase,
    Claim,
    ClaimStatus,
    Evidence,
    audit_b1_answer,
    build_sample_cases,
)
from src.documents.locator_resolver import RowRef, VerifyResult


class FakeDBConn:
    """Mock database connection for offline testing."""
    async def fetch(self, sql: str, *params):
        if "companies" in sql:
            return [{
                "symbol": "FPT",
                "company_name": "CTCP FPT",
                "exchange": "HOSE",
                "industry_type": "Công nghệ thông tin",
                "sector": "Công nghệ",
                "is_active": True,
            }]
        if "price_bars" in sql:
            return [{
                "key": "2026-09-29",
                "day": "2026-09-29",
            }]
        if "news_articles" in sql:
            return [{
                "key": str(params[0]),
                "url": "https://example.com/news",
            }]
        return []


class TestB1CitationVerifier(unittest.IsolatedAsyncioTestCase):

    def test_build_sample_cases(self):
        cases = build_sample_cases()
        self.assertIn("full_sources", cases)
        self.assertIn("missing_sources", cases)
        self.assertIn("conflicting_sources", cases)

        c_full = cases["full_sources"]
        self.assertEqual(c_full.case_type, "FULL_SOURCES")
        self.assertEqual(len(c_full.claims), 2)
        self.assertIn("EVID-FPT-PROFILE", c_full.evidence_pack)
        self.assertIn("EVID-FPT-PRICE-20260929", c_full.evidence_pack)

        c_missing = cases["missing_sources"]
        self.assertEqual(c_missing.case_type, "MISSING_SOURCES")
        self.assertTrue(any(c.evidence_id is None for c in c_missing.claims))

        c_conflicting = cases["conflicting_sources"]
        self.assertEqual(c_conflicting.case_type, "CONFLICTING_SOURCES")
        self.assertTrue(any(len(c.conflicting_with) > 0 for c in c_conflicting.claims))

    async def test_audit_case_full_sources_offline(self):
        cases = build_sample_cases()
        case_full = cases["full_sources"]
        fake_conn = FakeDBConn()

        report: AuditReport = await audit_b1_answer(case_full, conn=fake_conn)

        self.assertEqual(report.case_id, "B1-CASE-01-FULL")
        self.assertEqual(report.claims_total, 2)
        self.assertEqual(report.claims_verified, 2)
        self.assertEqual(report.claims_ungrounded, 0)
        self.assertEqual(report.claims_conflicting, 0)
        self.assertTrue(report.is_clean)
        self.assertEqual(len(report.citations_opened), 2)
        self.assertIn("[EVID-FPT-PROFILE]", report.revised_answer)
        self.assertIn("[EVID-FPT-PRICE-20260929]", report.revised_answer)

    async def test_audit_case_missing_sources_offline(self):
        cases = build_sample_cases()
        case_missing = cases["missing_sources"]
        fake_conn = FakeDBConn()

        report: AuditReport = await audit_b1_answer(case_missing, conn=fake_conn)

        self.assertEqual(report.case_id, "B1-CASE-02-MISSING")
        self.assertEqual(report.claims_total, 2)
        self.assertEqual(report.claims_verified, 1)
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertTrue(report.is_clean)  # Sau hieu chinh khong con claim vo nguon nao khang dinh sai
        self.assertEqual(len(report.citations_opened), 1)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())
        self.assertIn("[EVID-FPT-PROFILE]", report.revised_answer)

    async def test_audit_case_conflicting_sources_offline(self):
        cases = build_sample_cases()
        case_conflicting = cases["conflicting_sources"]
        fake_conn = FakeDBConn()

        report: AuditReport = await audit_b1_answer(case_conflicting, conn=fake_conn)

        self.assertEqual(report.case_id, "B1-CASE-03-CONFLICTING")
        self.assertEqual(report.claims_total, 2)
        self.assertEqual(report.claims_conflicting, 2)
        self.assertEqual(report.claims_ungrounded, 0)
        self.assertTrue(report.is_clean)
        self.assertEqual(len(report.citations_opened), 2)
        self.assertIn("thận trọng", report.revised_answer.lower())
        self.assertIn("[EVID-FPT-RETAIL-11]", report.revised_answer)
        self.assertIn("[EVID-FPT-MIRAE-AI]", report.revised_answer)

    async def test_invalid_locator_causes_ungrounded(self):
        bad_case = B1AnswerCase(
            case_id="B1-BAD-LOCATOR",
            case_type="TEST",
            query="Test query",
            raw_answer="Nhan dinh voi locator sai [EVID-BAD].",
            claims=[
                Claim(claim_id="C1", statement="Nhan dinh bat ky", evidence_id="EVID-BAD"),
            ],
            evidence_pack={
                "EVID-BAD": Evidence(
                    evidence_id="EVID-BAD",
                    locator={"source_table": "unknown_table", "row_keys": ["k1"]},
                    chunk_text="Some text",
                )
            },
        )

        report = await audit_b1_answer(bad_case, conn=FakeDBConn())
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())

    async def test_audit_with_real_supabase(self):
        import asyncpg
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / "backend" / ".env")
        load_dotenv(PROJECT_ROOT / ".env")

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            self.skipTest("DATABASE_URL khong ton tai trong moi truong")

        conn = await asyncpg.connect(db_url)
        try:
            cases = build_sample_cases()
            for _, case in cases.items():
                rep = await audit_b1_answer(case, conn=conn)
                self.assertTrue(rep.is_clean)
                self.assertGreaterEqual(len(rep.citations_opened), 1)
        finally:
            await conn.close()


if __name__ == "__main__":
    unittest.main()
