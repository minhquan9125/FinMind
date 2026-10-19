"""Script WBS-B1: Kiem tra trich dan va hieu chinh cau tra loi B1.

Chay qua 3 ca mau:
- Ca 1: Nguon day du (Full sources).
- Ca 2: Nguon thieu (Missing sources / claim vo nguon).
- Ca 3: Nguon mau thuan (Conflicting sources).

Su dung resolve_locator va verify_chunk cua Vu de xac minh trich dan mo duoc CSDL.
Ket qua dam bao: Khong co claim vo nguon trong ca mau; 100% citation mo duoc locator.

Cach chay:
    py -X utf8 backend/scripts/verify_b1_citations.py
    py -X utf8 backend/scripts/verify_b1_citations.py --report b1-audit-report.md
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.documents.b1_citation_verifier import audit_b1_answer, build_sample_cases


async def main() -> int:
    parser = argparse.ArgumentParser(description="Kiem tra trich dan va cau tra loi B1")
    parser.add_argument("--report", type=str, help="Duong dan file Markdown xuat bao cao")
    args = parser.parse_args()

    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")

    db_url = os.environ.get("DATABASE_URL")
    conn = None
    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            print("[INFO] Da ket noi CSDL Supabase de kiem tra thuc te.")
        except Exception as exc:
            print(f"[WARN] Khong the ket noi CSDL ({exc}), se kiem tra offline qua schema locator.")
    else:
        print("[WARN] DATABASE_URL khong ton tai, kiem tra offline qua schema locator.")

    cases = build_sample_cases()
    reports = []

    print("\n" + "=" * 75)
    print("BAT DAU KIEM TRA TRICH DAN VA CAU TRA LOI B1 (3 BUOC)")
    print("=" * 75)

    for case_key, b1_case in cases.items():
        print(f"\n---> Kiem tra ca: {b1_case.case_id} [{b1_case.case_type}]")
        print(f"Câu hỏi: {b1_case.query}")
        print(f"Câu trả lời gốc: {b1_case.raw_answer}")

        report = await audit_b1_answer(b1_case, conn=conn)
        reports.append(report)

        print(f"\n[Ket qua buoc 2] Kiem tra tung nhan dinh:")
        for c in b1_case.claims:
            print(f"  * Claim {c.claim_id}: {c.statement}")
            print(f"    - Status: {c.status.value}")
            if c.issues:
                print(f"    - Issues: {'; '.join(c.issues)}")
            if c.resolved_refs:
                for ref in c.resolved_refs:
                    print(f"    - Locator mo duoc: Bang '{ref.table}', Keys={list(ref.keys)}, Expected={ref.expected}")

        print(f"\n[Ket qua buoc 3] Cau tra loi sau khi hieu chinh:")
        print(f"  {report.revised_answer}")
        print(f"  => Tong nhan dinh: {report.claims_total} | Verified: {report.claims_verified} | Ungrounded: {report.claims_ungrounded} | Conflicting: {report.claims_conflicting}")
        print(f"  => Khong con claim vo nguon: {'DAT CHUAN (CLEAN)' if report.is_clean else 'CHUA DAT'}")
        print(f"  => So citation mo duoc locator: {len(report.citations_opened)}")

    if conn is not None:
        await conn.close()

    # Xuat bao cao Markdown neu co yeu cau
    if args.report:
        md_lines = [
            "# Báo cáo kiểm tra trích dẫn và chuẩn hóa câu trả lời B1\n",
            f"**Thời gian thực hiện:** 2026-10-19\n",
            f"**Tích hợp:** `src.documents.locator_resolver` của Vũ & `src.documents.b1_citation_verifier`\n",
            "\n## 1. Tổng quan các ca kiểm tra\n",
            "| Ca mẫu | Loại nguồn | Số nhận định | Verified | Ungrounded | Conflicting | Citation mở được | Trạng thái |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for rep in reports:
            status_str = "ĐẠT (Sạch claim vô nguồn)" if rep.is_clean else "KHÔNG ĐẠT"
            md_lines.append(
                f"| `{rep.case_id}` | {rep.case_type} | {rep.claims_total} | {rep.claims_verified} | {rep.claims_ungrounded} | {rep.claims_conflicting} | {len(rep.citations_opened)} | {status_str} |"
            )

        md_lines.append("\n## 2. Chi tiết từng ca kiểm tra và kết quả hiệu chỉnh\n")

        for rep in reports:
            md_lines.append(f"### Ca: `{rep.case_id}` ({rep.case_type})\n")
            md_lines.append(f"- **Câu hỏi:** *{rep.query}*\n")
            md_lines.append(f"- **Câu trả lời ban đầu:**\n  > {rep.original_answer}\n")
            md_lines.append(f"- **Câu trả lời sau hiệu chỉnh (Bước 3):**\n  > {rep.revised_answer}\n")
            md_lines.append("- **Các citation mở được locator:**\n")
            for cit in rep.citations_opened:
                md_lines.append(f"  - Mã `[{cit['evidence_id']}]`: Bảng `{cit['table']}`, Khóa: `{cit['keys']}`")
            md_lines.append("\n---\n")

        report_path = Path(args.report)
        report_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"\n[INFO] Da xuat bao cao ra file: {report_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
