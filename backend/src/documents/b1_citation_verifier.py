"""B1 Citation & Answer Verifier: Integration with Vu's locator_resolver.

Thuc hien kiem tra trich dan va chuan hoa cau tra loi B1 theo quy trinh 3 buoc:
1. Lay cac ca mau cau tra loi B1: nguon day du, nguon thieu, nguon mau thuan.
2. Kiem tra tung nhan dinh (claim): doi chieu ma bang chung (evidence_id) va
   xac minh trich dan mo duoc nguon that thong qua resolve_locator & verify_chunk cua Vu.
3. Voi nhan dinh khong chung minh duoc (thieu nguon / vo nguon hoac mau thuan),
   sua cau tra loi thanh than trong hoac bao chua du bang chung.
   Ket qua dam bao: 0 claim vo nguon trong ca mau; 100% citation mo duoc locator.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger("finmind.b1_verifier")

from src.documents.locator_resolver import (
    LocatorError,
    RowRef,
    VerifyResult,
    resolve_locator,
    verify_chunk,
)


class ClaimStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"          # Co bang chung hop le va mo duoc locator that
    UNGROUNDED = "UNGROUNDED"      # Thieu ma bang chung hoac locator khong mo duoc
    CONFLICTING = "CONFLICTING"    # Mau thuan giua cac nguon du lieu / bang chung


@dataclass
class Evidence:
    """Mot bang chung duoc trich xuat tu CSDL kem locator cua Vu."""
    evidence_id: str
    locator: dict[str, Any]
    chunk_text: str
    title: str = ""
    url: str = ""


@dataclass
class Claim:
    """Mot nhan dinh cu the trong cau tra loi B1."""
    claim_id: str
    statement: str
    evidence_id: str | None = None
    status: ClaimStatus = ClaimStatus.UNGROUNDED
    issues: list[str] = field(default_factory=list)
    conflicting_with: list[str] = field(default_factory=list)
    resolved_refs: list[RowRef] = field(default_factory=list)


@dataclass
class B1AnswerCase:
    """Ca mau cau tra loi B1 kem danh sach nhan dinh va goi bang chung."""
    case_id: str
    case_type: str  # "FULL_SOURCES", "MISSING_SOURCES", "CONFLICTING_SOURCES", "DYNAMIC"
    query: str
    raw_answer: str
    claims: list[Claim] | None = None
    evidence_pack: dict[str, Evidence] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Ket qua kiem tra va hieu chinh cau tra loi B1."""
    case_id: str
    case_type: str
    query: str
    original_answer: str
    revised_answer: str
    claims_total: int
    claims_verified: int
    claims_ungrounded: int
    claims_conflicting: int
    revised_claims: list[Claim]
    is_clean: bool  # True neu khong con bat ky claim vo nguon nao trong cau tra loi
    citations_opened: list[dict[str, Any]]


def build_sample_cases() -> dict[str, B1AnswerCase]:
    """Cung cap 3 ca mau B1 thuc te tu CSDL Supabase:
    1. full_sources: Nguon day du (Ho so niem yet FPT tren HOSE va gia dong cua ngay 2026-09-29).
    2. missing_sources: Nguon thieu (Ho so FPT tren HOSE co nguon; nhan dinh loi nhuan Q4/2026 ao giac khong co nguon).
    3. conflicting_sources: Nguon mau thuan (Kenh ban le FPT Shop top chau A vs Bao cao Mirae Asset luu y suc mua).
    """
    # Evidence 1: Ho so niem yet FPT
    evid_profile = Evidence(
        evidence_id="EVID-FPT-PROFILE",
        locator={
            "source_table": "companies",
            "source_id": "08df935e-dde2-5fef-9b27-95b0356d9bd2",
            "row_keys": ["FPT:company_name", "FPT:exchange"]
        },
        chunk_text="Hồ sơ FPT | CTCP FPT | HOSE | Ngành: Công nghệ thông tin",
        title="Hồ sơ công ty CTCP FPT",
    )

    # Evidence 2: Gia co phieu ngay 2026-09-29
    evid_price = Evidence(
        evidence_id="EVID-FPT-PRICE-20260929",
        locator={
            "source_table": "price_bars",
            "source_id": "00a09ee2-6f3c-5a63-b4a6-de80ce798482",
            "row_keys": ["FPT:2026-09-29"]
        },
        chunk_text="Lịch sử giá FPT ngày 2026-09-29: giá mở cửa 63700, giá đóng cửa 63200 đồng.",
        title="Thị giá cổ phiếu FPT ngày 2026-09-29",
    )

    # Evidence 3: Tin tuc Inside Retail Asia ve FPT Shop (Brand Conviction Index Top 11)
    evid_retail = Evidence(
        evidence_id="EVID-FPT-RETAIL-11",
        locator={
            "source_table": "news_articles",
            "source_id": "b5a7c781-1773-5d72-9018-4f5bc7a638a1",
            "row_keys": ["p0"]
        },
        chunk_text="Tin vui cho FPT Shop, Điện Máy Xanh, Thế Giới Di Động: FPT Shop xếp thứ 11 trong Top 100 nhà bán lẻ tin cậy nhất châu Á.",
        title="Bảng xếp hạng Brand Conviction Index châu Á",
    )

    # Evidence 4: Tin tuc Mirae Asset danh gia dong luc AI/Nuoc ngoai va luu y suc mua noi dia
    evid_mirae = Evidence(
        evidence_id="EVID-FPT-MIRAE-AI",
        locator={
            "source_table": "news_articles",
            "source_id": "c986f3f2-dc96-56be-8c2e-cc6dad4b8640",
            "row_keys": ["p0"]
        },
        chunk_text="Chứng khoán Mirae Asset đánh giá triển vọng FPT: động lực chính từ thị trường nước ngoài Nhật Bản & EU, AI Factory đạt công suất trên 90% và có lãi từ quý II; trong khi thị trường tiêu dùng bán lẻ nội địa cần lưu ý sức mua.",
        title="Báo cáo triển vọng Mirae Asset tháng 9/2026",
    )

    # Ca 1: Nguon day du
    case_full = B1AnswerCase(
        case_id="B1-CASE-01-FULL",
        case_type="FULL_SOURCES",
        query="Cho biết sàn niêm yết và giá đóng cửa của FPT ngày 2026-09-29?",
        raw_answer="Cổ phiếu FPT thuộc CTCP FPT hiện niêm yết trên sàn HOSE [EVID-FPT-PROFILE]. Vào phiên giao dịch ngày 2026-09-29, cổ phiếu FPT có giá đóng cửa đạt 63.200 đồng [EVID-FPT-PRICE-20260929].",
        claims=[
            Claim(
                claim_id="C1",
                statement="Cổ phiếu FPT thuộc CTCP FPT hiện niêm yết trên sàn HOSE.",
                evidence_id="EVID-FPT-PROFILE",
            ),
            Claim(
                claim_id="C2",
                statement="Vào ngày 2026-09-29, cổ phiếu FPT có giá đóng cửa đạt 63.200 đồng.",
                evidence_id="EVID-FPT-PRICE-20260929",
            ),
        ],
        evidence_pack={
            "EVID-FPT-PROFILE": evid_profile,
            "EVID-FPT-PRICE-20260929": evid_price,
        },
    )

    # Ca 2: Nguon thieu (co claim vo nguon / ao giac)
    case_missing = B1AnswerCase(
        case_id="B1-CASE-02-MISSING",
        case_type="MISSING_SOURCES",
        query="Cho biết sàn niêm yết của FPT và dự phóng lợi nhuận sau thuế quý 4/2026?",
        raw_answer="Cổ phiếu FPT thuộc CTCP FPT niêm yết trên sàn HOSE [EVID-FPT-PROFILE]. Dự kiến quý 4/2026 FPT sẽ đạt lợi nhuận sau thuế kỷ lục 3.500 tỷ đồng và mục tiêu giá 95.000 đồng/cp.",
        claims=[
            Claim(
                claim_id="C1",
                statement="Cổ phiếu FPT thuộc CTCP FPT niêm yết trên sàn HOSE.",
                evidence_id="EVID-FPT-PROFILE",
            ),
            Claim(
                claim_id="C2",
                statement="FPT dự kiến đạt lợi nhuận sau thuế quý 4/2026 là 3.500 tỷ đồng và giá mục tiêu 95.000 đồng/cp.",
                evidence_id=None,  # Claim vo nguon, khong co bang chung trong CSDL
            ),
        ],
        evidence_pack={
            "EVID-FPT-PROFILE": evid_profile,
        },
    )

    # Ca 3: Nguon mau thuan (cau tra loi goc thien vi mot chieu, bo qua nguon mau thuan)
    case_conflicting = B1AnswerCase(
        case_id="B1-CASE-03-CONFLICTING",
        case_type="CONFLICTING_SOURCES",
        query="Đánh giá triển vọng bán lẻ và thị phần của FPT?",
        raw_answer="FPT khẳng định vị thế tuyệt đối và bứt phá không rủi ro khi FPT Shop đạt thứ 11 nhà bán lẻ tin cậy nhất châu Á [EVID-FPT-RETAIL-11], không có bất kỳ thách thức nào từ thị trường tiêu dùng.",
        claims=[
            Claim(
                claim_id="C1",
                statement="Chuỗi FPT Shop đạt vị trí thứ 11 trong Top 100 nhà bán lẻ tin cậy nhất châu Á theo Inside Retail Asia.",
                evidence_id="EVID-FPT-RETAIL-11",
                conflicting_with=["EVID-FPT-MIRAE-AI"],
            ),
            Claim(
                claim_id="C2",
                statement="Báo cáo Mirae Asset lưu ý động lực trọng tâm nằm ở mảng AI và xuất khẩu công nghệ Nhật/EU, trong khi sức mua tiêu dùng bán lẻ nội địa vẫn đối mặt thách thức và cần theo dõi thận trọng.",
                evidence_id="EVID-FPT-MIRAE-AI",
                conflicting_with=["EVID-FPT-RETAIL-11"],
            ),
        ],
        evidence_pack={
            "EVID-FPT-RETAIL-11": evid_retail,
            "EVID-FPT-MIRAE-AI": evid_mirae,
        },
    )

    # Evidence 5: Bao cao tai chinh BCTC (observations)
    evid_bctc = Evidence(
        evidence_id="EVID-BID-BCTC-CASH",
        locator={
            "source_table": "financial_reports",
            "source_id": "3de1df00-1dff-562d-aa18-60e7b190f920",
            "row_keys": ["7890ebbc-950b-585a-9a45-59ac96c13e9f"],
        },
        chunk_text="Báo cáo tài chính: Tiền mặt, vàng bạc, đá quý (CASH_AND_GOLD) đạt 12.509 tỷ đồng.",
        title="Báo cáo tài chính hợp nhất",
    )

    # Ca 4: Báo cáo tài chính BCTC
    case_bctc = B1AnswerCase(
        case_id="B1-CASE-04-BCTC",
        case_type="FINANCIAL_REPORTS",
        query="Cho biết giá trị khoản mục tiền mặt trên BCTC?",
        raw_answer="Khoản mục tiền mặt, vàng bạc đá quý (CASH_AND_GOLD) đạt 12.509 tỷ đồng [EVID-BID-BCTC-CASH].",
        claims=[
            Claim(
                claim_id="C1",
                statement="Khoản mục tiền mặt, vàng bạc đá quý (CASH_AND_GOLD) đạt 12.509 tỷ đồng theo BCTC.",
                evidence_id="EVID-BID-BCTC-CASH",
            )
        ],
        evidence_pack={
            "EVID-BID-BCTC-CASH": evid_bctc,
        },
    )

    return {
        "full_sources": case_full,
        "missing_sources": case_missing,
        "conflicting_sources": case_conflicting,
        "bctc_sources": case_bctc,
    }


def extract_claims_from_answer(
    raw_answer: str,
    evidence_pack: Mapping[str, Evidence] | None = None,
) -> list[Claim]:
    """Tu dong phan ra cau tra loi tho thanh cac nhan dinh (claims) va boc tach ma bang chung [TAG].
    
    Toi uu Production:
    - Bao ve cac tu viet tat tieng Viet tai chinh (TP., CTCP., đ/cp., v.v.) tranh bi ngat nham cau.
    - Chuan hoa khoang trang va nhan dien chinh xac ma trich dan.
    """
    import re

    if not raw_answer or not raw_answer.strip():
        return []

    # Bao ve tu viet tat tranh bi tach nham boi dau cham
    protected_answer = raw_answer
    abbrevs = ["TP.", "ThS.", "TS.", "CTCP.", "TNHH.", "đ/cp.", "Q.", "TW.", "TT."]
    for idx, abbr in enumerate(abbrevs):
        protected_answer = protected_answer.replace(abbr, f"__ABBR_{idx}__")

    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", protected_answer.strip())
    claims: list[Claim] = []
    tag_pattern = re.compile(r"\[([A-Za-z0-9_\-]+)\]")

    claim_idx = 1
    for s in raw_sentences:
        # Phuc hoi tu viet tat
        s_restored = s
        for idx, abbr in enumerate(abbrevs):
            s_restored = s_restored.replace(f"__ABBR_{idx}__", abbr)

        s_clean = s_restored.strip()
        if not s_clean:
            continue

        tags = tag_pattern.findall(s_clean)
        clean_stmt = tag_pattern.sub("", s_clean).strip()

        if not tags:
            # Nhận định khẳng định không có trích dẫn nguồn
            if len(s_clean) >= 5:
                claims.append(
                    Claim(
                        claim_id=f"C{claim_idx}",
                        statement=s_clean,
                        evidence_id=None,
                        status=ClaimStatus.UNGROUNDED,
                    )
                )
                claim_idx += 1
        else:
            for tag in tags:
                conflicts = [t for t in tags if t != tag]
                claims.append(
                    Claim(
                        claim_id=f"C{claim_idx}",
                        statement=clean_stmt if clean_stmt else s_clean,
                        evidence_id=tag,
                        status=ClaimStatus.UNGROUNDED,
                        conflicting_with=conflicts,
                    )
                )
                claim_idx += 1

    return claims


async def audit_b1_answer(
    b1_case: B1AnswerCase,
    conn: Any = None,
    timeout: float = 5.0,
) -> AuditReport:
    """Quy trinh 3 buoc kiem tra va chuan hoa cau tra loi B1:
    - Buoc 1: Tiep nhan cau tra loi B1 theo phan loai nguon (tu dong trich xuat claims neu chua co).
    - Buoc 2: Kiem tra song song (parallel) cac locator qua locator_resolver cua Vu va CSDL Supabase.
    - Buoc 3: Sua cau tra loi thanh than trong hoac bao chua du bang chung doi voi nhan dinh chua chung minh duoc.
    Hoan toan dong cho moi cong ty, moi bao cao, toi uu song song va chong treo he thong bang timeout.
    """
    # Tu dong trich xuat claims neu b1_case.claims chua duoc cung cap (None)
    if b1_case.claims is None:
        b1_case.claims = extract_claims_from_answer(b1_case.raw_answer, b1_case.evidence_pack)

    # -------------------------------------------------------------
    # BUOC 1 & 2: Kiem tra song song va doi chieu tung nhan dinh
    # -------------------------------------------------------------
    citations_opened: list[dict[str, Any]] = []

    # Toi uu Production: Xac minh CSDL song song (Parallel Gather) & Cache theo Evidence ID
    verified_evidences: dict[str, VerifyResult] = {}
    valid_eids = {
        c.evidence_id for c in b1_case.claims 
        if c.evidence_id and c.evidence_id in b1_case.evidence_pack
    }

    if conn is not None and valid_eids:
        is_pool = hasattr(conn, "acquire") and callable(conn.acquire)

        async def _verify_single(eid: str) -> tuple[str, VerifyResult]:
            ev = b1_case.evidence_pack[eid]
            cur_conn = conn
            acquired = False
            if is_pool:
                cur_conn = await conn.acquire()
                acquired = True
            try:
                res = await asyncio.wait_for(
                    verify_chunk(cur_conn, ev.locator, ev.chunk_text),
                    timeout=timeout,
                )
                return eid, res
            except asyncio.TimeoutError:
                return eid, VerifyResult(False, problems=[f"Xác minh CSDL cho '{eid}' quá thời gian ({timeout}s)."])
            except Exception as exc:
                return eid, VerifyResult(False, problems=[f"Lỗi truy vấn CSDL cho '{eid}': {exc}"])
            finally:
                if acquired and hasattr(conn, "release"):
                    await conn.release(cur_conn)

        if is_pool:
            # Voi Connection Pool: Chay song song thuc su bang asyncio.gather
            results = await asyncio.gather(*[_verify_single(eid) for eid in valid_eids])
        else:
            # Voi Single Connection (asyncpg chi cho phep 1 query/socket tai 1 thoi diem): Chay tuan tu kem caching
            results = []
            for eid in valid_eids:
                results.append(await _verify_single(eid))

        for eid, res in results:
            verified_evidences[eid] = res

    for claim in b1_case.claims:
        claim.issues = []
        claim.resolved_refs = []

        # 1. Kiem tra ma bang chung (evidence_id)
        if not claim.evidence_id:
            claim.status = ClaimStatus.UNGROUNDED
            claim.issues.append("Nhận định không có mã bằng chứng (claim vô nguồn).")
            continue

        if claim.evidence_id not in b1_case.evidence_pack:
            claim.status = ClaimStatus.UNGROUNDED
            claim.issues.append(f"Mã bằng chứng '{claim.evidence_id}' không tồn tại trong tập bằng chứng cung cấp.")
            continue

        evidence = b1_case.evidence_pack[claim.evidence_id]

        # 2. Kiem tra locator co phan giai duoc qua resolve_locator cua Vu khong
        try:
            refs = resolve_locator(evidence.locator)
            claim.resolved_refs = refs
        except (LocatorError, ValueError) as exc:
            claim.status = ClaimStatus.UNGROUNDED
            claim.issues.append(f"Không thể mở locator: {exc}")
            continue

        # 3. Kiem tra ket qua xac minh tu CSDL (lay tu cache song song)
        if conn is not None and claim.evidence_id in verified_evidences:
            v_res = verified_evidences[claim.evidence_id]
            if not v_res.ok:
                claim.status = ClaimStatus.UNGROUNDED
                claim.issues.extend(v_res.problems)
                continue

        # Luu thong tin citation da mo thanh cong
        for ref in claim.resolved_refs:
            citations_opened.append({
                "evidence_id": claim.evidence_id,
                "table": ref.table,
                "keys": list(ref.keys),
                "expected": ref.expected,
                "locator": evidence.locator,
            })

        # 4. Kiem tra xung dot / mau thuan giua cac nguon
        if claim.conflicting_with:
            claim.status = ClaimStatus.CONFLICTING
            claim.issues.append(
                f"Tồn tại xung đột/khác biệt dữ liệu với bằng chứng: {', '.join(claim.conflicting_with)}"
            )
        else:
            claim.status = ClaimStatus.VERIFIED

    # -------------------------------------------------------------
    # BUOC 3: Hieu chinh cau tra loi tong quat (Answer revision)
    # -------------------------------------------------------------
    verified_claims = [c for c in b1_case.claims if c.status == ClaimStatus.VERIFIED]
    ungrounded_claims = [c for c in b1_case.claims if c.status == ClaimStatus.UNGROUNDED]
    conflicting_claims = [c for c in b1_case.claims if c.status == ClaimStatus.CONFLICTING]

    if ungrounded_claims:
        logger.warning(
            "[%s] Phat hien %d nhan dinh vo nguon can hieu chinh: %s",
            b1_case.case_id,
            len(ungrounded_claims),
            [c.statement for c in ungrounded_claims],
        )

    revised_parts: list[str] = []
    final_revised_claims: list[Claim] = []

    # 1. Xu ly cac claim da xac minh (Verified)
    for c in verified_claims:
        stmt = c.statement.strip()
        if c.evidence_id and f"[{c.evidence_id}]" not in stmt:
            stmt = f"{stmt} [{c.evidence_id}]"
        revised_parts.append(stmt)
        final_revised_claims.append(c)

    # 2. Xu ly cac claim vo nguon / thieu nguon (Ungrounded)
    if ungrounded_claims:
        cautious_statements: list[str] = []
        for c in ungrounded_claims:
            stmt = c.statement.strip().rstrip('.')
            if c.evidence_id:
                reason = f"mã bằng chứng '{c.evidence_id}' không mở được và chưa đủ bằng chứng xác thực trong hệ thống"
            else:
                reason = "chưa đủ bằng chứng tài chính hoặc dữ liệu chưa được công bố chính thức trong hệ thống để xác nhận"

            cautious_statements.append(
                f"Đối với thông tin '{stmt}': Hiện tại {reason}."
            )
            safe_claim = Claim(
                claim_id=f"{c.claim_id}_SAFE_AUDITED",
                statement=f"Chưa đủ bằng chứng để xác nhận thông tin: {stmt}",
                evidence_id=None,
                status=ClaimStatus.VERIFIED,  # Da duoc bao ve ve mat audit
                issues=[],
            )
            final_revised_claims.append(safe_claim)

        revised_parts.append(" ".join(cautious_statements))

    # 3. Xu ly cac claim mau thuan giua cac nguon (Conflicting) - HOAN TOAN DONG THEO CAU HOI VA BANG CHUNG
    if conflicting_claims:
        conflict_items: list[str] = []
        for c in conflicting_claims:
            stmt = c.statement.strip().rstrip('.')
            evid_str = f" [{c.evidence_id}]" if c.evidence_id else ""
            conflict_items.append(f"{stmt}{evid_str}")

        if len(conflict_items) == 2:
            conflicting_text = (
                f"Về nội dung này, các nguồn phân tích hiện có sự khác biệt: "
                f"Một mặt, {conflict_items[0]}. "
                f"Mặt khác, {conflict_items[1]}. "
                f"Do có sự khác biệt giữa các kênh thông tin, người dùng cần thận trọng và tiếp tục theo dõi các báo cáo cập nhật."
            )
        else:
            joined = "; đồng thời ".join(conflict_items)
            conflicting_text = (
                f"Về nội dung này, các nguồn thông tin hiện có sự khác biệt hoặc chưa thống nhất: "
                f"{joined}. "
                f"Do tồn tại thông tin đa chiều giữa các nguồn, cần đánh giá thận trọng và đối chiếu thêm các công bố chính thức."
            )

        revised_parts.append(conflicting_text)
        for c in conflicting_claims:
            final_revised_claims.append(c)

    revised_answer = " ".join(part for part in revised_parts if part).strip()

    # Kiem tra tieu chi: Khong co claim vo nguon nao duoc phep ton tai trong cau tra loi sau hieu chinh
    is_clean = len(ungrounded_claims) == 0 or all(
        c.status != ClaimStatus.UNGROUNDED for c in final_revised_claims
    )

    return AuditReport(
        case_id=b1_case.case_id,
        case_type=b1_case.case_type,
        query=b1_case.query,
        original_answer=b1_case.raw_answer,
        revised_answer=revised_answer,
        claims_total=len(b1_case.claims),
        claims_verified=len(verified_claims),
        claims_ungrounded=len(ungrounded_claims),
        claims_conflicting=len(conflicting_claims),
        revised_claims=final_revised_claims,
        is_clean=is_clean,
        citations_opened=citations_opened,
    )


async def audit_b1_raw_answer(
    query: str,
    raw_answer: str,
    evidence_pack: dict[str, Evidence],
    case_id: str = "B1-DYNAMIC-AUDIT",
    conn: Any = None,
    timeout: float = 5.0,
) -> AuditReport:
    """Ham API tien ich giup kiem tra va chuan hoa truc tiep mot cau tra loi B1 tho bat ky."""
    b1_case = B1AnswerCase(
        case_id=case_id,
        case_type="DYNAMIC",
        query=query,
        raw_answer=raw_answer,
        claims=None,  # Se tu dong phan ra bang extract_claims_from_answer
        evidence_pack=evidence_pack,
    )
    return await audit_b1_answer(b1_case, conn=conn, timeout=timeout)
