import asyncio
from datetime import datetime, timezone

from src.documents.db_chunking import (
    DEFAULT_MAX_WORDS,
    chunk_document,
    chunk_documents,
    financial_documents,
    format_value,
    news_documents,
    period_text,
    section_body,
)
from src.documents.db_source import fetch_financial_documents, fetch_news_documents


def fin_rows(n=40, report="r1", value_shift=0):
    return [
        {
            "report_id": report, "symbol": "FPT", "company_name": "Công ty FPT",
            "period_code": "2026-Q2", "statement_scope": "CONSOLIDATED", "section": "INCOME_STATEMENT",
            "code": f"M{i:03d}", "canonical_name": f"Chỉ tiêu số {i}", "observation_id": f"o{report}-{i}",
            "value": (i + 1) * 1_000_000 + (value_shift if i == 7 else 0), "unit": "VND",
        }
        for i in range(n)
    ]


def test_header_is_repeated_and_every_row_stays_whole():
    doc = financial_documents(fin_rows())[0]
    chunks = chunk_document(doc)
    assert len(chunks) > 1
    header = doc.sections[0].header
    all_rows = {row.text for row in doc.sections[0].rows}
    seen = set()
    for chunk in chunks:
        lines = chunk.text.split("\n")
        assert lines[0] == header  # section header always first
        for line in lines[1:]:
            assert line in all_rows  # no row cut in the middle
            seen.add(line)
        assert chunk.token_count <= DEFAULT_MAX_WORDS + 25  # budget respected (a single row may overshoot)
    assert seen == all_rows  # nothing lost, nothing invented


def test_chunk_ids_are_stable_and_unique():
    first = chunk_documents(financial_documents(fin_rows()))
    second = chunk_documents(financial_documents(fin_rows()))
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert len({c.chunk_id for c in first}) == len(first)


def test_changing_one_value_changes_only_its_chunk():
    base = chunk_documents(financial_documents(fin_rows()))
    changed = chunk_documents(financial_documents(fin_rows(value_shift=5_000_000)))
    assert len(base) == len(changed)
    differing = [i for i, (a, b) in enumerate(zip(base, changed)) if a.chunk_id != b.chunk_id]
    assert len(differing) == 1
    assert "o" + "r1-7" in changed[differing[0]].locator["row_keys"]


def test_offsets_point_back_into_section_body():
    doc = financial_documents(fin_rows())[0]
    body = section_body(doc.sections[0])
    for chunk in chunk_document(doc):
        piece = body[chunk.char_start:chunk.char_end]
        assert piece == "\n".join(chunk.text.split("\n")[1:])


def test_locator_lists_source_rows():
    chunk = chunk_documents(financial_documents(fin_rows(5)))[0]
    assert chunk.locator["source_table"] == "financial_reports"
    assert chunk.locator["row_keys"] == ["or1-0", "or1-1", "or1-2", "or1-3", "or1-4"]
    assert chunk.locator["symbol"] == "FPT"


def test_units_and_periods_are_stated():
    assert format_value(2_500_000_000, "VND") == "2,500.00 triệu VND"
    assert format_value(1234.5, "VND_PER_SHARE") == "1,234.50 VND/cổ phiếu"
    assert format_value(0.123456, "SOURCE_NATIVE") == "0.1235"
    assert format_value(None, "VND") == "không có dữ liệu"
    assert period_text("2026-Q2", "BALANCE_SHEET") == "tại cuối quý 2/2026"
    assert period_text("2026-Q2", "INCOME_STATEMENT") == "quý 2/2026 (riêng quý)"
    assert period_text("2025-YEAR", "CASH_FLOW") == "năm 2025 (cả năm)"


def test_sections_are_separate_documents_parts():
    rows = fin_rows(3) + [dict(r, section="BALANCE_SHEET", code="B" + r["code"], observation_id="b" + r["observation_id"])
                          for r in fin_rows(3)]
    doc = financial_documents(rows)[0]
    assert [s.label.split(" · ")[0] for s in doc.sections] == ["Báo cáo Kết quả hoạt động kinh doanh", "Bảng Cân đối kế toán"]
    chunks = chunk_document(doc)
    assert {c.section_index for c in chunks} == {0, 1}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def news(content, title="FPT công bố kết quả kinh doanh"):
    return {
        "article_id": "a1", "source": "cafef", "title": title, "content": content,
        "published_at": datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc), "symbols": ["FPT"], "url": "https://x/y",
    }


def test_news_paragraphs_keep_title_in_every_chunk():
    paragraphs = [" ".join(f"từ{p}_{i}" for i in range(60)) + "." for p in range(6)]
    docs = news_documents([news("\n\n".join(paragraphs))])
    chunks = chunk_documents(docs)
    assert len(chunks) >= 3
    assert all(c.text.startswith("Tin cafef | 2026-10-01 | FPT công bố kết quả kinh doanh") for c in chunks)
    assert chunks[0].locator["url"] == "https://x/y"


def test_news_long_paragraph_is_split_on_sentences():
    sentence = " ".join(["chữ"] * 40) + "."
    docs = news_documents([news(" ".join([sentence] * 8))])
    chunks = chunk_documents(docs)
    assert len(chunks) > 1
    for chunk in chunks:
        body = chunk.text.split("\n", 1)[1]
        assert body.endswith(".")  # never cut mid-sentence here


def test_news_without_content_is_skipped():
    assert news_documents([news("   ")]) == []


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows


def test_fetch_helpers_use_connection_and_filter_symbols():
    conn = FakeConn(fin_rows(4))
    docs = asyncio.run(fetch_financial_documents(conn, ["fpt"]))
    assert len(docs) == 1
    assert conn.calls[0][1] == (["FPT"],)

    conn2 = FakeConn([news("Đoạn một.\n\nĐoạn hai.")])
    docs2 = asyncio.run(fetch_news_documents(conn2, None, limit=5))
    assert len(docs2) == 1
    assert conn2.calls[0][1] == (None, 5)
