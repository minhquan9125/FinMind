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
    audit_b1_raw_answer,
    build_sample_cases,
    extract_claims_from_answer,
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
        if "market_index_bars" in sql:
            return [{
                "key": "2026-04-13",
            }]
        if "observations" in sql:
            return [{
                "key": "7890ebbc-950b-585a-9a45-59ac96c13e9f",
                "code": "CASH_AND_GOLD",
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
        self.assertIn("bctc_sources", cases)

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

    async def test_evidence_id_not_found_in_pack(self):
        """Kiem tra khi claim co evidence_id nhung pack khong co -> UNGROUNDED."""
        case = B1AnswerCase(
            case_id="B1-MISSING-PACK-KEY",
            case_type="TEST",
            query="Query",
            raw_answer="Answer [EVID-GHOST]",
            claims=[
                Claim(claim_id="C1", statement="Nhan dinh co id ao", evidence_id="EVID-GHOST")
            ],
            evidence_pack={},
        )
        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertIn("không tồn tại trong tập bằng chứng", case.claims[0].issues[0])
        self.assertTrue(report.is_clean)

    async def test_empty_claims(self):
        """Kiem tra truong hop cau tra loi khong chua claim nao."""
        case = B1AnswerCase(
            case_id="B1-EMPTY",
            case_type="TEST",
            query="Xin chao",
            raw_answer="Chao ban, toi la tro ly FinMind.",
            claims=[],
            evidence_pack={},
        )
        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_total, 0)
        self.assertEqual(report.claims_verified, 0)
        self.assertEqual(report.claims_ungrounded, 0)
        self.assertTrue(report.is_clean)
        self.assertEqual(report.revised_answer, "")

    async def test_verify_chunk_failed_mismatch_db(self):
        """Kiem tra khi DB khong tim thay dong theo locator -> UNGROUNDED."""
        class EmptyDBConn:
            async def fetch(self, sql: str, *params):
                return []  # Khong tim thay ban ghi nao

        cases = build_sample_cases()
        case_full = cases["full_sources"]
        report = await audit_b1_answer(case_full, conn=EmptyDBConn())
        self.assertEqual(report.claims_ungrounded, 2)
        self.assertEqual(report.claims_verified, 0)
        self.assertTrue(report.is_clean)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())

    async def test_mixed_claims_scenario(self):
        """Kiem tra ca tong hop gom ca 3 loai: verified, ungrounded, va conflicting."""
        cases = build_sample_cases()
        evid_profile = cases["full_sources"].evidence_pack["EVID-FPT-PROFILE"]
        evid_retail = cases["conflicting_sources"].evidence_pack["EVID-FPT-RETAIL-11"]
        evid_mirae = cases["conflicting_sources"].evidence_pack["EVID-FPT-MIRAE-AI"]

        mixed_case = B1AnswerCase(
            case_id="B1-MIXED",
            case_type="MIXED",
            query="Tong hop FPT",
            raw_answer="FPT tren HOSE. FPT lai 100k ty. FPT Shop so 1.",
            claims=[
                Claim(claim_id="C1", statement="FPT niem yet tren HOSE", evidence_id="EVID-FPT-PROFILE"),
                Claim(claim_id="C2", statement="FPT lai 100k ty nam 2026", evidence_id=None),
                Claim(claim_id="C3", statement="FPT Shop top ban le", evidence_id="EVID-FPT-RETAIL-11", conflicting_with=["EVID-FPT-MIRAE-AI"]),
                Claim(claim_id="C4", statement="Mirae luu y suc mua", evidence_id="EVID-FPT-MIRAE-AI", conflicting_with=["EVID-FPT-RETAIL-11"]),
            ],
            evidence_pack={
                "EVID-FPT-PROFILE": evid_profile,
                "EVID-FPT-RETAIL-11": evid_retail,
                "EVID-FPT-MIRAE-AI": evid_mirae,
            },
        )
        report = await audit_b1_answer(mixed_case, conn=FakeDBConn())
        self.assertEqual(report.claims_total, 4)
        self.assertEqual(report.claims_verified, 1)
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertEqual(report.claims_conflicting, 2)
        self.assertTrue(report.is_clean)
        self.assertIn("[EVID-FPT-PROFILE]", report.revised_answer)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())
        self.assertIn("thận trọng", report.revised_answer.lower())

    def test_extract_claims_from_raw_text(self):
        """Kiem tra tinh nang tu dong boc tach nhan dinh va ma bang chung tu chuoi tho bat ky."""
        raw_text = (
            "VCB la ngan hang hang dau Viet Nam [EVID-VCB-01]. "
            "Loi nhuan ca nam 2026 du kien tang truong dot pha 50.000 ty dong. "
            "Gia co phieu dat 120.000 dong [EVID-VCB-PRICE]."
        )
        claims = extract_claims_from_answer(raw_text)
        self.assertEqual(len(claims), 3)
        self.assertEqual(claims[0].evidence_id, "EVID-VCB-01")
        self.assertIsNone(claims[1].evidence_id)  # Claim vo nguon
        self.assertEqual(claims[2].evidence_id, "EVID-VCB-PRICE")

    async def test_generic_non_fpt_company_raw_answer(self):
        """Kiem tra quy trinh voi mot cong ty bat ky (VCB) va cau tra loi tho tu LLM."""
        raw_answer = (
            "Ngan hang VCB co quy mo von hoa lon nhat thi truong [EVID-VCB-PROFILE]. "
            "VCB se chia co tuc tien mat 80% trong quy toi."  # Claim vo nguon
        )
        pack = {
            "EVID-VCB-PROFILE": Evidence(
                evidence_id="EVID-VCB-PROFILE",
                locator={
                    "source_table": "companies",
                    "source_id": "08df935e-dde2-5fef-9b27-95b0356d9bd2",
                    "row_keys": ["VCB:company_name", "VCB:exchange"]
                },
                chunk_text="Hồ sơ VCB | Ngân hàng Ngoại thương | HOSE",
            )
        }

        class VcbFakeConn:
            async def fetch(self, sql: str, *params):
                return [{
                    "symbol": "VCB",
                    "company_name": "Ngân hàng Ngoại thương",
                    "exchange": "HOSE",
                    "industry_type": "Ngân hàng",
                    "sector": "Tài chính",
                    "is_active": True,
                }]

        report = await audit_b1_raw_answer(
            query="Danh gia co phieu VCB",
            raw_answer=raw_answer,
            evidence_pack=pack,
            case_id="B1-VCB-TEST",
            conn=VcbFakeConn(),
        )

        self.assertEqual(report.claims_total, 2)
        self.assertEqual(report.claims_verified, 1)
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertTrue(report.is_clean)
        self.assertIn("[EVID-VCB-PROFILE]", report.revised_answer)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())
        self.assertNotIn("FPT", report.revised_answer)  # Dam bao khong bi dinh FPT

    async def test_generic_conflicting_sources_arbitrary_stock(self):
        """Kiem tra nguon mau thuan tong quat cho mot co phieu bat ky (HPG)."""
        pack = {
            "EVID-HPG-1": Evidence(
                evidence_id="EVID-HPG-1",
                locator={
                    "source_table": "news_articles",
                    "source_id": "b5a7c781-1773-5d72-9018-4f5bc7a638a1",
                    "row_keys": ["p0"]
                },
                chunk_text="HPG khoi cong lo cao so 2",
            ),
            "EVID-HPG-2": Evidence(
                evidence_id="EVID-HPG-2",
                locator={
                    "source_table": "news_articles",
                    "source_id": "c986f3f2-dc96-56be-8c2e-cc6dad4b8640",
                    "row_keys": ["p0"]
                },
                chunk_text="Gia thep giam sau anh huong bien loi nhuan HPG",
            ),
        }
        case = B1AnswerCase(
            case_id="B1-HPG-CONFLICT",
            case_type="CONFLICTING_SOURCES",
            query="Trien vong HPG",
            raw_answer="HPG tang truong manh san luong [EVID-HPG-1] nhung gia thep giam manh [EVID-HPG-2].",
            claims=[
                Claim(
                    claim_id="C1",
                    statement="HPG tang truong san luong nho Dung Quat 2",
                    evidence_id="EVID-HPG-1",
                    conflicting_with=["EVID-HPG-2"],
                ),
                Claim(
                    claim_id="C2",
                    statement="Gia thep giam lam thu hep bien loi nhuan HPG",
                    evidence_id="EVID-HPG-2",
                    conflicting_with=["EVID-HPG-1"],
                ),
            ],
            evidence_pack=pack,
        )

        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_conflicting, 2)
        self.assertTrue(report.is_clean)
        self.assertIn("thận trọng", report.revised_answer.lower())
        self.assertIn("[EVID-HPG-1]", report.revised_answer)
        self.assertIn("[EVID-HPG-2]", report.revised_answer)
        self.assertNotIn("FPT", report.revised_answer)  # Hoan toan dong theo HPG, khong hardcode

    async def test_audit_financial_reports_bctc_offline(self):
        """Kiem tra xac minh bao cao tai chinh BCTC (financial_reports & observations)."""
        pack = {
            "EVID-BCTC-CASH": Evidence(
                evidence_id="EVID-BCTC-CASH",
                locator={
                    "source_table": "financial_reports",
                    "source_id": "3de1df00-1dff-562d-aa18-60e7b190f920",
                    "row_keys": ["7890ebbc-950b-585a-9a45-59ac96c13e9f"],
                },
                chunk_text="Khoản mục tiền mặt và vàng bạc đá quý (CASH_AND_GOLD) đạt 12.509 tỷ đồng.",
            )
        }
        case = B1AnswerCase(
            case_id="B1-BCTC-TEST",
            case_type="FINANCIAL_REPORTS",
            query="Tien mat quy 2",
            raw_answer="Khoan muc tien mat dat 12.509 ty dong [EVID-BCTC-CASH].",
            claims=[
                Claim(
                    claim_id="C1",
                    statement="Khoản mục tiền mặt đạt 12.509 tỷ đồng",
                    evidence_id="EVID-BCTC-CASH",
                )
            ],
            evidence_pack=pack,
        )
        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_verified, 1)
        self.assertEqual(report.claims_ungrounded, 0)
        self.assertTrue(report.is_clean)
        self.assertEqual(len(report.citations_opened), 1)
        self.assertEqual(report.citations_opened[0]["table"], "financial_reports")

    async def test_audit_financial_reports_metric_missing_causes_ungrounded(self):
        """Kiem tra neu chunk text thieu ma metric trong ngoac -> UNGROUNDED vi khong du can cu."""
        pack = {
            "EVID-BCTC-NO-METRIC": Evidence(
                evidence_id="EVID-BCTC-NO-METRIC",
                locator={
                    "source_table": "financial_reports",
                    "source_id": "3de1df00-1dff-562d-aa18-60e7b190f920",
                    "row_keys": ["7890ebbc-950b-585a-9a45-59ac96c13e9f"],
                },
                chunk_text="Doan van khong de cap den ma chi tieu.",  # Thieu (CASH_AND_GOLD)
            )
        }
        case = B1AnswerCase(
            case_id="B1-BCTC-BAD",
            case_type="FINANCIAL_REPORTS",
            query="Tien mat quy 2",
            raw_answer="Tien mat 12.509 ty dong [EVID-BCTC-NO-METRIC].",
            claims=[
                Claim(
                    claim_id="C1",
                    statement="Tien mat 12.509 ty dong",
                    evidence_id="EVID-BCTC-NO-METRIC",
                )
            ],
            evidence_pack=pack,
        )
        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertEqual(report.claims_verified, 0)
        self.assertTrue(report.is_clean)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())

    async def test_audit_market_index_bars_offline(self):
        """Kiem tra xac minh chi so thi truong (market_index_bars: VN30, VNINDEX)."""
        pack = {
            "EVID-VN30": Evidence(
                evidence_id="EVID-VN30",
                locator={
                    "source_table": "market_index_bars",
                    "source_id": "market_index",
                    "row_keys": ["VN30:2026-04-13"],
                },
                chunk_text="Dien bien chi so VN30 ngay 2026-04-13 tang truong tich cuc.",
            )
        }
        case = B1AnswerCase(
            case_id="B1-INDEX-TEST",
            case_type="MARKET_INDEX",
            query="Dien bien VN30",
            raw_answer="VN30 ngay 2026-04-13 tang diem [EVID-VN30].",
            claims=[
                Claim(
                    claim_id="C1",
                    statement="VN30 ngày 2026-04-13 tăng điểm",
                    evidence_id="EVID-VN30",
                )
            ],
            evidence_pack=pack,
        )
        report = await audit_b1_answer(case, conn=FakeDBConn())
        self.assertEqual(report.claims_verified, 1)
        self.assertEqual(report.claims_ungrounded, 0)
        self.assertTrue(report.is_clean)
        self.assertEqual(len(report.citations_opened), 1)
        self.assertEqual(report.citations_opened[0]["table"], "market_index_bars")

    async def test_all_five_source_types_combined_real_supabase(self):
        """Kiem tra tich hop toan dien ca 5 bang nguon du lieu tren CSDL Supabase that:
        1. companies (ho so doanh nghiep)
        2. price_bars (gia co phieu)
        3. market_index_bars (chi so thi truong)
        4. news_articles (tin tuc)
        5. financial_reports (bao cao tai chinh & observations)
        """
        import asyncpg
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / "backend" / ".env")
        load_dotenv(PROJECT_ROOT / ".env")

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            self.skipTest("DATABASE_URL khong ton tai trong moi truong")

        conn = await asyncpg.connect(db_url)
        try:
            # 1. Company
            evid_comp = Evidence(
                evidence_id="EVID-1-COMP",
                locator={"source_table": "companies", "source_id": "c1", "row_keys": ["FPT:company_name", "FPT:exchange"]},
                chunk_text="Hồ sơ FPT: CTCP FPT niêm yết trên HOSE.",
            )
            # 2. Price bar
            p_row = await conn.fetchrow(
                "SELECT p.trade_date::text as day, c.symbol FROM price_bars p "
                "JOIN companies c ON c.company_id = p.company_id LIMIT 1"
            )
            evid_price = Evidence(
                evidence_id="EVID-2-PRICE",
                locator={"source_table": "price_bars", "source_id": "p1", "row_keys": [f"{p_row['symbol']}:{p_row['day']}"]},
                chunk_text=f"Cổ phiếu {p_row['symbol']} ngày {p_row['day']} giao dịch tích cực.",
            )
            # 3. Market index bar
            i_row = await conn.fetchrow("SELECT index_symbol, trade_date::text as day FROM market_index_bars LIMIT 1")
            evid_idx = Evidence(
                evidence_id="EVID-3-INDEX",
                locator={"source_table": "market_index_bars", "source_id": "i1", "row_keys": [f"{i_row['index_symbol']}:{i_row['day']}"]},
                chunk_text=f"Chỉ số {i_row['index_symbol']} ngày {i_row['day']} tăng điểm.",
            )
            # 4. News article
            n_row = await conn.fetchrow("SELECT article_id::text, url FROM news_articles LIMIT 1")
            evid_news = Evidence(
                evidence_id="EVID-4-NEWS",
                locator={"source_table": "news_articles", "source_id": n_row["article_id"], "row_keys": ["p0"], "url": n_row["url"]},
                chunk_text="Nội dung bài viết tin tức.",
            )
            # 5. Financial report
            b_row = await conn.fetchrow(
                "SELECT o.observation_id::text, o.report_id::text, m.code FROM observations o "
                "JOIN metrics m ON m.metric_id = o.metric_id LIMIT 1"
            )
            evid_bctc = Evidence(
                evidence_id="EVID-5-BCTC",
                locator={"source_table": "financial_reports", "source_id": b_row["report_id"], "row_keys": [b_row["observation_id"]]},
                chunk_text=f"Số liệu báo cáo tài chính ({b_row['code']}) ghi nhận đúng thực tế.",
            )

            pack = {
                "EVID-1-COMP": evid_comp,
                "EVID-2-PRICE": evid_price,
                "EVID-3-INDEX": evid_idx,
                "EVID-4-NEWS": evid_news,
                "EVID-5-BCTC": evid_bctc,
            }

            mega_case = B1AnswerCase(
                case_id="B1-MEGA-5-TABLES",
                case_type="ALL_5_TABLES",
                query="Tổng hợp 5 nguồn",
                raw_answer=(
                    "FPT trên HOSE [EVID-1-COMP]. "
                    f"Giá {p_row['symbol']} ngày {p_row['day']} [EVID-2-PRICE]. "
                    f"Chỉ số {i_row['index_symbol']} ngày {i_row['day']} [EVID-3-INDEX]. "
                    "Tin tức CafeF [EVID-4-NEWS]. "
                    f"Chỉ tiêu BCTC ({b_row['code']}) [EVID-5-BCTC]."
                ),
                claims=[
                    Claim(claim_id="C1", statement="FPT trên sàn HOSE", evidence_id="EVID-1-COMP"),
                    Claim(claim_id="C2", statement=f"Giá {p_row['symbol']} ngày {p_row['day']}", evidence_id="EVID-2-PRICE"),
                    Claim(claim_id="C3", statement=f"Chỉ số {i_row['index_symbol']} ngày {i_row['day']}", evidence_id="EVID-3-INDEX"),
                    Claim(claim_id="C4", statement="Tin tức thị trường", evidence_id="EVID-4-NEWS"),
                    Claim(claim_id="C5", statement=f"Chỉ tiêu tài chính {b_row['code']}", evidence_id="EVID-5-BCTC"),
                ],
                evidence_pack=pack,
            )

            report = await audit_b1_answer(mega_case, conn=conn)
            self.assertEqual(report.claims_total, 5)
            self.assertEqual(report.claims_verified, 5)
            self.assertEqual(report.claims_ungrounded, 0)
            self.assertTrue(report.is_clean)
            self.assertEqual(len(report.citations_opened), 5)
        finally:
            await conn.close()

    def test_extract_claims_with_vietnamese_abbreviations(self):
        """Kiem tra tokenizer khong bi ngat nham cau khi gap tu viet tat tieng Viet tai chinh."""
        raw_text = (
            "Trụ sở chính của CTCP. FPT đặt tại TP. HCM [EVID-1]. "
            "Cổ tức chi trả đạt 2.500 đ/cp. trong năm 2026."
        )
        claims = extract_claims_from_answer(raw_text)
        self.assertEqual(len(claims), 2)
        # Cau 1 van giu nguyen ven ca TP. HCM va CTCP. FPT
        self.assertIn("TP. HCM", claims[0].statement)
        self.assertIn("CTCP. FPT", claims[0].statement)
        self.assertEqual(claims[0].evidence_id, "EVID-1")
        # Cau 2 giu nguyen đ/cp.
        self.assertIn("đ/cp.", claims[1].statement)
        self.assertIsNone(claims[1].evidence_id)

    async def test_parallel_cached_verification_multiple_claims_same_evidence(self):
        """Kiem tra toi uu song song va caching: nhieu claim dung chung 1 evidence."""
        call_count = 0

        class SpyDBConn:
            async def fetch(self, sql: str, *params):
                nonlocal call_count
                call_count += 1
                return [{
                    "symbol": "FPT",
                    "company_name": "CTCP FPT",
                    "exchange": "HOSE",
                    "industry_type": "CNTT",
                    "sector": "CN",
                    "is_active": True,
                }]

        ev = Evidence(
            evidence_id="EVID-SHARED",
            locator={"source_table": "companies", "source_id": "c1", "row_keys": ["FPT:exchange"]},
            chunk_text="FPT niem yet HOSE",
        )
        case = B1AnswerCase(
            case_id="B1-SHARED",
            case_type="TEST",
            query="FPT",
            raw_answer="FPT tren HOSE [EVID-SHARED]. CTCP FPT niem yet HOSE [EVID-SHARED].",
            claims=[
                Claim(claim_id="C1", statement="FPT tren HOSE", evidence_id="EVID-SHARED"),
                Claim(claim_id="C2", statement="CTCP FPT niem yet HOSE", evidence_id="EVID-SHARED"),
            ],
            evidence_pack={"EVID-SHARED": ev},
        )
        report = await audit_b1_answer(case, conn=SpyDBConn())
        self.assertEqual(report.claims_verified, 2)
        self.assertTrue(report.is_clean)
        # Nho co co che batch deduplicate theo Evidence ID, DB chi can query dung 1 lan cho ca 2 claim!
        self.assertEqual(call_count, 1)

    async def test_timeout_handling_graceful(self):
        """Kiem tra xu ly graceful degradation khi DB query bi timeout."""
        class SlowDBConn:
            async def fetch(self, sql: str, *params):
                await asyncio.sleep(0.5)  # Gia lap DB bi treo
                return []

        ev = Evidence(
            evidence_id="EVID-SLOW",
            locator={"source_table": "companies", "source_id": "c1", "row_keys": ["FPT:exchange"]},
            chunk_text="FPT niem yet HOSE",
        )
        case = B1AnswerCase(
            case_id="B1-SLOW",
            case_type="TEST",
            query="FPT",
            raw_answer="FPT tren HOSE [EVID-SLOW].",
            claims=[
                Claim(claim_id="C1", statement="FPT tren HOSE", evidence_id="EVID-SLOW"),
            ],
            evidence_pack={"EVID-SLOW": ev},
        )
        # Goi voi timeout rat ngan (0.05s) -> Phai xu ly graceful khong crash
        report = await audit_b1_answer(case, conn=SlowDBConn(), timeout=0.05)
        self.assertEqual(report.claims_ungrounded, 1)
        self.assertIn("chưa đủ bằng chứng", report.revised_answer.lower())
        self.assertTrue(report.is_clean)

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
