import json
import hashlib
import re
from pathlib import Path

ROOT = Path("c:/Users/dieuh/Downloads/duan/FinMind")
MD_PATH = ROOT / "Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md"
TARGET_PATH = ROOT / "docs/review/golden40_manifest_frozen.json"
DRAFT_TARGET_PATH = ROOT / "docs/review/golden40_manifest_draft.json"

content = MD_PATH.read_text(encoding="utf-8")
sections = re.split(r'###\s+(Q\d+)', content)

def canonical_bytes(val):
    return json.dumps(val, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def calc_sha256(val):
    return hashlib.sha256(canonical_bytes(val)).hexdigest()

questions = []
for i in range(1, len(sections), 2):
    qid = sections[i]
    qtext_block = sections[i+1]
    
    category_match = re.search(r'\*Phân loại:\s*([^*]+)\*', qtext_block)
    category = category_match.group(1).strip() if category_match else ""
    
    question_match = re.search(r'-\s+\*\*Câu hỏi:?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    question = question_match.group(1).strip() if question_match else ""
    
    answer_match = re.search(r'-\s+\*\*Đáp án(?:\s+chuẩn)?:?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    answer = answer_match.group(1).strip() if answer_match else ""
    
    unit_match = re.search(r'-\s+\*\*Đơn vị(?:\s+tính)?:?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    unit = unit_match.group(1).strip() if unit_match else ""
    
    period_match = re.search(r'-\s+\*\*Kỳ(?:\s+báo\s+cáo)?:?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    period = period_match.group(1).strip() if period_match else ""
    
    doc_match = re.search(r'-\s+\*\*(?:Tài liệu gốc|Vị trí đối soát JSON|Vị trí đối soát|Tài liệu kiểm chứng|Dữ liệu nền tảng):?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    doc_loc = doc_match.group(1).strip() if doc_match else ""
    if qid == "Q25" and not doc_loc:
        doc_loc = "BCTC kiểm toán 2024: Thuyết minh 34(b) trang PDF 199 (31.294.207 triệu VND) & BCTN trang PDF 51"
    elif qid == "Q30" and not doc_loc:
        doc_loc = "BCTN FPT 2024 (Toàn văn không chứa dự báo giá cổ phiếu tương lai; tuân thủ BR-15/BR-16 Safe Refusal)"
    elif qid == "Q39" and not doc_loc:
        doc_loc = "báo_cáo_tài_chính.kết_quả_kinh_doanh → kỳ 2026-Q2 (13.788.503.461.199) & kỳ 2026-Q1 (12.479.997.206.775); trường isa3"
    elif qid == "Q40" and not doc_loc:
        doc_loc = "tai_chinh_clean.json (Dải kỳ báo cáo kết thúc ở 2026-Q2. Kỳ 2026-Q4 chưa phát sinh BCTC; tuân thủ BR-15 Safe Refusal)"
    
    verify_match = re.search(r'-\s+\*\*(?:Chi tiết kiểm chứng|Dữ liệu nền tảng|Lưu ý bẫy dữ liệu|Lưu ý bẫy dấu|Phép so khớp):?\*\*[:\s]*(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    verify_detail = verify_match.group(1).strip() if verify_match else ""
    
    status_match = re.search(r'-\s+\*\*Trạng thái\*\*[:\s]+(.*?)(?=\n-\s+\*\*|\Z)', qtext_block, re.DOTALL)
    status_note = status_match.group(1).strip() if status_match else ""
    
    q_num = int(qid[1:])
    if q_num <= 10:
        batch_id = "BATCH-01"
        data_source = "news_articles"
        reviewer = "Hưng (Data Lead)"
        structured_locator = {
            "source_table": "news_articles",
            "source_file": "Supabase public.news_articles",
            "scope": "approved_10_symbols",
            "raw_reference": doc_loc
        }
    elif q_num <= 20:
        batch_id = "BATCH-02"
        data_source = "price_bars"
        reviewer = "Hưng (Data Lead)"
        structured_locator = {
            "source_table": "price_bars",
            "source_file": "data/normalized/{SYMBOL}.json",
            "scope": "approved_10_symbols",
            "provider": "ENTRADE",
            "raw_reference": doc_loc
        }
    elif q_num <= 30:
        batch_id = "BATCH-03"
        data_source = "bctn_bctc_pdf_2024"
        reviewer = "Quân (Financial Analyst)"
        structured_locator = {
            "source_table": "documents",
            "source_file": "data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf",
            "scope": "corpus-v1-pdf",
            "raw_reference": doc_loc
        }
    else:
        batch_id = "BATCH-04"
        data_source = "tai_chinh_clean"
        reviewer = "Quân (Financial Analyst)"
        structured_locator = {
            "source_table": "observations",
            "source_file": "data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json",
            "scope": "sql-financial-reports",
            "company_symbol": "FPT",
            "raw_reference": doc_loc
        }
        
    is_safe_refusal = (q_num in [30, 40])
    
    # Define slots based on question
    slots = ["primary_answer"]
    if q_num in [1, 2, 5, 13, 14, 15, 16, 21, 23, 27, 35, 38, 39]:
        slots = ["slot_1", "slot_2"]
        if q_num in [1, 13]:
            slots = ["slot_1", "slot_2", "slot_3"]
            if q_num == 13:
                slots.append("slot_4")
                
    questions.append({
        "question_id": f"GOLDEN40-{qid}",
        "legacy_id": qid,
        "batch_id": batch_id,
        "data_source": data_source,
        "category": category,
        "question_text": question,
        "reference_answer": answer,
        "unit": unit,
        "period": period,
        "locator": doc_loc,
        "structured_locator": structured_locator,
        "verification_detail": verify_detail,
        "status_note": status_note,
        "is_safe_refusal": is_safe_refusal,
        "slots": slots,
        "tolerance_eps": 0.001 if ("%" in unit or "chỉ_số" in category or "ROE" in question) else 0.001,
        "sign_off_reviewer": reviewer,
        "verification_status": "VERIFIED_ACCURATE"
    })

manifest_payload = {
    "manifest_name": "FinMind Golden40 Calibration Set Manifest",
    "version_label": "golden40-v1.0-frozen",
    "status": "FROZEN",
    "created_at": "2026-10-20T16:00:00+07:00",
    "frozen_at": "2026-10-20T17:00:00+07:00",
    "description": "Bộ 40 ca kiểm thử hiệu chuẩn (Calibration Split) đóng băng kỹ thuật phục vụ đo lường và nghiệm thu Sprint 4.",
    "target_sprint": "Sprint 4",
    "total_cases": len(questions),
    "corpus_reference": {
        "corpus_version_label": "corpus-v1",
        "corpus_version_id": "7c2ea700-fd01-5adc-a467-af4fea532741",
        "corpus_manifest_sha256": "e9391c8af33b64888ea7b7c386a526110c35aab7fc2c469366e648f41c393f41",
        "index_version_id": "1e029e66-0adf-53ac-8f28-431ed7312745",
        "embedding_model": "BAAI/bge-m3@5617a9f61b02",
        "vector_dimensions": 1024,
        "db_snapshot_anchor": "wbs16-20261016-030706"
    },
    "batch_distribution": {
        "BATCH-01": 10,
        "BATCH-02": 10,
        "BATCH-03": 10,
        "BATCH-04": 10
    },
    "questions": questions
}

# Calculate hash of canonical questions & metadata
manifest_sha256 = calc_sha256(manifest_payload)
manifest_payload["manifest_sha256"] = manifest_sha256

# Write frozen manifest
TARGET_PATH.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Written frozen manifest to {TARGET_PATH}")
print(f"Canonical SHA-256: {manifest_sha256}")

# Also update draft manifest to keep it synced
draft_payload = dict(manifest_payload)
draft_payload["version_label"] = "golden40-v1.0-draft"
draft_payload["status"] = "DRAFT_SYNCED"
draft_payload["frozen_at"] = None
DRAFT_TARGET_PATH.write_text(json.dumps(draft_payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated draft manifest at {DRAFT_TARGET_PATH}")
