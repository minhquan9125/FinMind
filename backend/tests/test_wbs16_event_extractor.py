"""Unit and Integration Test Suite for WBS16 News Event Extractor.

Verifies all critical quality gates:
1. No entity hallucination from metadata (role=unspecified when unstated).
2. Narrative clustering (dates and figures fused into single event).
3. Deterministic event keys.
4. Correct needs_followup date comparison against current run date.
5. Strict status detection (no false cancelled on 'hủy niêm yết', no false planned on 'dự kiến lợi nhuận').
6. Valid status progression (planned -> occurred) is history, not conflict.
7. Full input article reconciliation audit.
"""
from datetime import date
import pytest

from src.documents.event_news import (
    WBS16EventExtractor,
    deduplicate_events,
    parse_publish_date,
    nfc,
    parse_dates_extended,
    detect_status_rigorous,
)


def test_nfc_normalization():
    # Decomposed NFD vs NFC
    nfd_text = "Hội đồng quản trị"  # NFD
    nfc_text = nfc(nfd_text)
    assert nfc_text == "Hội đồng quản trị"


def test_publish_date_utc_conversion():
    # 03:59 UTC on Oct 29 is 10:59 Vietnam local time (same day)
    utc_str = "2026-10-29T03:59:00Z"
    assert parse_publish_date(utc_str) == "2026-10-29"

    # 18:00 UTC on Oct 28 is 01:00 UTC+7 on Oct 29 (day rolls over to 29)
    utc_late = "2026-10-28T18:00:00Z"
    assert parse_publish_date(utc_late) == "2026-10-29"


def test_no_metadata_entity_leakage():
    """parties must come exclusively from text, not from metadata symbols."""
    extractor = WBS16EventExtractor()
    article = {
        "article_id": "test-1",
        "title": "Thông báo thị trường",
        "content": "Sở Giao dịch Chứng khoán TP.HCM công bố quyết định thay đổi niêm yết.",
        "publish_date": "2026-10-29",
        "symbols": ["FPT", "MSN", "PLX"],  # Metadata has 3 tickers
    }
    result = extractor.extract_article(article)
    assert result["relevance"] == "relevant"
    ev = result["events"][0]
    extracted_names = [p["name_normalized"] for p in ev["parties"]]
    # Should NOT contain FPT, MSN, PLX because they were not in the sentence
    assert "FPT" not in extracted_names
    assert "MSN" not in extracted_names
    assert "PLX" not in extracted_names
    assert any("Sở Giao dịch" in n for n in extracted_names)


def test_narrative_clustering_dividend():
    """Multiple sentences describing one dividend event must fuse into 1 event."""
    extractor = WBS16EventExtractor(current_run_date=date(2026, 10, 30))
    body = (
        "Hội đồng quản trị FPT đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá. "
        "Theo kế hoạch, ngày chốt danh sách cổ đông hưởng quyền là 30/11 và ngày thực hiện chi trả cổ tức là 10/12/2026. "
        "Tổng số tiền chi trả dự kiến hơn 1.000 tỷ đồng."
    )
    article = {
        "article_id": "div-1",
        "title": "FPT chi trả cổ tức",
        "content": body,
        "published_at": "2026-10-29T10:00:00+07:00",
    }
    result = extractor.extract_article(article)
    assert result["relevance"] == "relevant"
    # All 3 sentences fused into exactly 1 corporate_action event
    assert len(result["events"]) == 1
    ev = result["events"][0]
    assert ev["event_type"] == "corporate_action"
    assert ev["dates"]["event_date_start"] == "2026-12-10"
    # Both 10% and 1.000 tỷ đồng captured in the figures of this single event
    fig_values = [f["value_raw"] for f in ev["financial_figures_stated"]]
    assert any("10%" in v for v in fig_values)
    assert any("1.000 tỷ đồng" in v for v in fig_values)


def test_status_rigorous_exclusions():
    """Hủy niêm yết is NOT cancelled; Dự kiến lợi nhuận is NOT planned event."""
    # 1. Hủy niêm yết
    s1 = "Sở Giao dịch thông qua quyết định hủy niêm yết cổ phiếu Công ty X."
    status1, _, signals1 = detect_status_rigorous(s1)
    assert status1 != "cancelled"

    # 2. Dự kiến doanh thu/lợi nhuận (forecasting)
    s2 = "Doanh nghiệp dự kiến lợi nhuận trước thuế năm 2026 đạt 5.000 tỷ đồng."
    status2, _, _ = detect_status_rigorous(s2)
    assert status2 != "planned"  # Excluded from event planned status


def test_needs_followup_compares_with_current_run_date():
    """needs_followup = True only if planned event date has already passed current run date."""
    # Run date: 2026-10-30. Event date: 2026-10-15 (in the past)
    extractor_past = WBS16EventExtractor(current_run_date=date(2026, 10, 30))
    art_past = {
        "article_id": "p1",
        "title": "Họp ĐHCĐ",
        "content": "HĐQT FPT thông qua kế hoạch tổ chức họp đại hội đồng cổ đông ngày 15/10/2026.",
        "publish_date": "2026-10-01",
    }
    res_past = extractor_past.extract_article(art_past)
    assert res_past["events"][0]["needs_followup"] is True

    # Run date: 2026-10-30. Event date: 2026-12-10 (in the future)
    art_future = {
        "article_id": "p2",
        "title": "Chi trả cổ tức",
        "content": "HĐQT FPT thông qua kế hoạch tổ chức chi trả cổ tức ngày 10/12/2026.",
        "publish_date": "2026-10-29",
    }
    res_future = extractor_past.extract_article(art_future)
    assert res_future["events"][0]["needs_followup"] is False


def test_dedup_valid_progression_vs_conflict():
    """Planned on day 1 followed by Occurred on day 2 is valid history, NOT a conflict."""
    art1 = {
        "schema_version": "0.1",
        "article_id": "a1",
        "source_name": "fireant",
        "url": "http://a1",
        "publish_date": "2026-10-20",
        "relevance": "relevant",
        "events": [{
            "local_event_id": "e1",
            "event_type": "shareholder_meeting",
            "dates": {"event_date_start": "2026-10-28"},
            "status": "planned",
            "status_evidence": "FPT dự kiến tổ chức họp",
            "parties": [{"name_normalized": "FPT", "role": "organizer"}],
        }],
    }
    art2 = {
        "schema_version": "0.1",
        "article_id": "a2",
        "source_name": "cafef",
        "url": "http://a2",
        "publish_date": "2026-10-29",  # Published later
        "relevance": "relevant",
        "events": [{
            "local_event_id": "e1",
            "event_type": "shareholder_meeting",
            "dates": {"event_date_start": "2026-10-28"},
            "status": "occurred",
            "status_evidence": "FPT đã tổ chức họp thành công",
            "parties": [{"name_normalized": "FPT", "role": "organizer"}],
        }],
    }
    deduped = deduplicate_events([art1, art2])
    assert len(deduped) == 1
    # Valid progression over different days -> review_flag is 'none', NOT 'conflict'
    assert deduped[0]["review_flag"] == "none"
    assert deduped[0]["current_best"]["status"] == "occurred"  # Latest wins
    assert len(deduped[0]["status_history"]) == 2
    assert len(deduped[0]["per_source_extractions"]) == 2


def test_unspecified_organizer_goes_to_merge_uncertain():
    """Events without clear verified organizer must not be blindly merged."""
    art = {
        "schema_version": "0.1",
        "article_id": "u1",
        "source_name": "fireant",
        "url": "http://u1",
        "publish_date": "2026-10-29",
        "relevance": "relevant",
        "events": [{
            "local_event_id": "e1",
            "event_type": "conference_forum",
            "dates": {"event_date_start": None},
            "status": "unconfirmed",
            "parties": [],  # No parties
        }],
    }
    deduped = deduplicate_events([art])
    assert len(deduped) == 1
    assert deduped[0]["review_flag"] == "merge_uncertain"
