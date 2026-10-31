"""Bộ test cho wbs16_extractor v0.2. Dữ liệu là câu giả bằng tiếng Việt, không phải tin thật.

Chạy:  python -m unittest -v test_wbs16_extractor
"""
import json
import tempfile
import unicodedata
import unittest
from datetime import date
from pathlib import Path

import wbs16_extractor as w

AS_OF = date(2026, 10, 30)


def extract(body, symbols=(), title="", publish="2026-10-20", aid="A1", **kw):
    ex = w.WBS16EventExtractor(as_of=AS_OF)
    return ex.extract_article({"article_id": aid, "title": title, "body": body, "symbols": list(symbols),
                               "publish_date": publish, "url": f"http://x/{aid}", "source_name": "t", **kw})


class TestDates(unittest.TestCase):
    def test_publish_date_converted_to_vn(self):
        self.assertEqual(w.parse_publish_date("2026-10-20T20:00:00Z"), "2026-10-21")
        self.assertEqual(w.parse_publish_date("2026-10-20T08:00:00"), "2026-10-20")
        self.assertEqual(w.parse_publish_date("20/10/2026"), "2026-10-20")
        self.assertIsNone(w.parse_publish_date("không rõ"))

    def test_full_date_not_derived(self):
        d = w.find_dates("Họp vào ngày 15/11/2026.", "2026-10-20")
        self.assertEqual([(x["date"], x["derived"]) for x in d], [("2026-11-15", False)])

    def test_short_date_derived_and_not_double_counted(self):
        d = w.find_dates("Họp vào ngày 15/11.", "2026-10-20")
        self.assertEqual([(x["date"], x["derived"]) for x in d], [("2026-11-15", True)])

    def test_year_rolls_over(self):
        d = w.find_dates("Họp vào ngày 10/01.", "2026-12-20")
        self.assertEqual(d[0]["date"], "2027-01-10")
        d = w.find_dates("Đã họp vào ngày 20/12.", "2027-01-05")
        self.assertEqual(d[0]["date"], "2026-12-20")

    def test_text_format(self):
        d = w.find_dates("Vào ngày 15 tháng 11 năm 2026, công ty họp.", "2026-10-20")
        self.assertEqual((d[0]["date"], d[0]["derived"]), ("2026-11-15", False))

    def test_relative(self):
        d = w.find_dates("Lễ ký kết diễn ra hôm qua.", "2026-10-20")
        self.assertEqual((d[0]["date"], d[0]["derived"]), ("2026-10-19", True))

    def test_invalid_date_ignored(self):
        self.assertEqual(w.find_dates("ngày 31/02/2026", "2026-10-20"), [])


class TestStatus(unittest.TestCase):
    def st(self, s):
        return w.detect_status(s)[0]

    def test_basic(self):
        self.assertEqual(self.st("Hội nghị sẽ diễn ra vào ngày 15/11."), "planned")
        self.assertEqual(self.st("Lễ ký kết đã diễn ra sáng nay."), "occurred")
        self.assertEqual(self.st("Công ty thông báo hủy đại hội."), "cancelled")
        self.assertEqual(self.st("Theo nguồn tin, công ty sẽ ký thỏa thuận."), "unconfirmed")

    def test_negation_and_delisting(self):
        self.assertNotEqual(self.st("Công ty không hủy đại hội."), "cancelled")
        self.assertNotEqual(self.st("Sở thông báo hủy niêm yết cổ phiếu XYZ."), "cancelled")

    def test_forecast_is_not_plan(self):
        status, signals, _ = w.detect_status("Công ty dự kiến doanh thu 100 tỷ đồng.")
        self.assertEqual(signals, [])

    def test_postponed(self):
        s, _, notes = w.detect_status("ĐHCĐ hoãn sang ngày 20/12.")
        self.assertEqual(s, "planned")
        self.assertIn("postponed", notes)
        self.assertEqual(self.st("Hội nghị hoãn vô thời hạn."), "cancelled")

    def test_mixed_signals_earliest_wins(self):
        s, _, notes = w.detect_status("Hai bên đã ký thỏa thuận, dự kiến triển khai trong quý 2.")
        self.assertEqual(s, "occurred")
        self.assertIn("mixed_signals", notes)

    def test_no_signal_is_flagged(self):
        s, sig, notes = w.detect_status("Công ty ABC công bố cổ tức.")
        self.assertEqual((s, sig), ("unconfirmed", []))
        self.assertIn("no_status_signal", notes)


class TestExtraction(unittest.TestCase):
    def test_organizer_and_coorganizer_from_sentence(self):
        r = extract("Công ty A sẽ phối hợp Hiệp hội B tổ chức hội nghị X tại Hà Nội vào ngày 15/11.")
        self.assertEqual(r["relevance"], "relevant")
        ev = r["events"][0]
        roles = {p["name_raw"]: p["role"] for p in ev["parties"]}
        self.assertEqual(roles, {"Công ty A": "organizer", "Hiệp hội B": "co_organizer"})
        self.assertEqual(ev["event_type"], "conference_forum")
        self.assertEqual(ev["location"], "Hà Nội")
        self.assertEqual(ev["status"], "planned")
        self.assertEqual(ev["dates"]["event_date_start"], "2026-11-15")
        self.assertTrue(ev["dates"]["date_derived"])
        self.assertEqual(r["publish_date"], "2026-10-20")

    def test_no_party_invented_from_metadata_roles(self):
        # bài gắn 2 mã nhưng câu chỉ nhắc ABC -> chỉ có ABC, role không bị gán organizer
        r = extract("ABC sẽ chi trả cổ tức tỷ lệ 10% vào ngày 25/11/2026.", symbols=["ABC", "XYZ"])
        ev = r["events"][0]
        self.assertEqual([p["name_raw"] for p in ev["parties"]], ["ABC"])
        self.assertEqual(ev["parties"][0]["role"], "unspecified")
        self.assertEqual(ev["parties"][0]["name_source"], "sentence")

    def test_metadata_only_party_is_marked(self):
        r = extract("Công ty sẽ chi trả cổ tức vào ngày 25/11/2026.", symbols=["ABC"])
        p = r["events"][0]["parties"][0]
        self.assertEqual((p["name_source"], p["role_evidence"], p["role"]), ("metadata", None, "unspecified"))

    def test_two_symbols_no_symbol_in_sentence_has_no_party(self):
        r = extract("Công ty sẽ chi trả cổ tức vào ngày 25/11/2026.", symbols=["ABC", "XYZ"])
        self.assertEqual(r["events"][0]["parties"], [])
        self.assertEqual(r["events"][0]["subjects"], [])

    def test_sentences_of_same_event_merge(self):
        body = ("ABC thông báo chi trả cổ tức năm 2025. Cổ tức tỷ lệ 10% mệnh giá. "
                "ABC sẽ chi trả vào ngày 25/11/2026.")
        r = extract(body, symbols=["ABC"])
        self.assertEqual(len([e for e in r["events"] if e["event_type"] == "corporate_action"]), 1)
        ev = r["events"][0]
        self.assertEqual(ev["dates"]["event_date_start"], "2026-11-25")
        self.assertTrue(any("10%" in f["value_raw"] for f in ev["financial_figures_stated"]))

    def test_multiple_dates_are_ambiguous_not_guessed(self):
        body = "ABC chốt danh sách cổ đông vào ngày 10/11/2026 và sẽ chi trả cổ tức vào ngày 25/11/2026."
        ev = extract(body, symbols=["ABC"])["events"][0]
        self.assertIsNone(ev["dates"]["event_date_start"])
        self.assertEqual(len(ev["dates"]["date_candidates"]), 2)
        self.assertIn("multiple_distinct_dates", ev["notes"])

    def test_needs_followup_uses_as_of(self):
        ev = extract("ABC sẽ họp ĐHCĐ vào ngày 05/10/2026.", symbols=["ABC"], publish="2026-09-20")["events"][0]
        self.assertEqual(ev["status"], "planned")
        self.assertTrue(ev["needs_followup"])  # 05/10 < as_of 30/10

    def test_figures_no_duplicates(self):
        ev = extract("ABC chi trả cổ tức 10% mệnh giá, tổng 16.500 tỷ đồng và 100 triệu cổ phiếu.",
                     symbols=["ABC"])["events"][0]
        vals = [f["value_raw"] for f in ev["financial_figures_stated"]]
        self.assertEqual(len(vals), len(set(vals)))
        self.assertTrue(any("16.500 tỷ đồng" in v for v in vals))

    def test_claim_only_when_source_states_it(self):
        ev = extract("ABC đã ký thỏa thuận hợp tác, nhờ đó mở rộng thị trường.", symbols=["ABC"])["events"][0]
        self.assertEqual(len(ev["claims_by_source"]), 1)
        ev2 = extract("ABC đã ký thỏa thuận hợp tác với XYZ.", symbols=["ABC"])["events"][0]
        self.assertEqual(ev2["claims_by_source"], [])

    def test_empty_body_not_dropped(self):
        r = extract("", title="")
        self.assertEqual(r["relevance"], "not_relevant")
        self.assertEqual(r["events"], [])

    def test_non_event_article_not_dropped(self):
        r = extract("VN-Index tăng 5 điểm trong phiên sáng với thanh khoản cải thiện.")
        self.assertEqual(r["relevance"], "not_relevant")
        self.assertTrue(r["relevance_reason"])

    def test_nfd_input_matches(self):
        body = unicodedata.normalize("NFD", "Hội nghị sẽ diễn ra vào ngày 15/11.")
        r = extract(body)
        self.assertEqual(r["events"][0]["status"], "planned")

    def test_all_evidence_is_verbatim(self):
        body = ("Công ty A sẽ phối hợp Hiệp hội B tổ chức hội nghị X tại Hà Nội vào ngày 15/11.\n"
                "ABC đã ký thỏa thuận hợp tác, nhờ đó mở rộng thị trường.")
        r = extract(body, symbols=["ABC"])
        self.assertEqual(r["qa"]["evidence_unverified"], [])

    def test_deterministic_regardless_of_symbol_order(self):
        body = "ABC và XYZ sẽ chi trả cổ tức vào ngày 25/11/2026."
        a = extract(body, symbols=["ABC", "XYZ"])
        b = extract(body, symbols=["XYZ", "ABC"])
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_adjacent_sentence_date_is_flagged(self):
        body = "ABC thông báo chi trả cổ tức năm 2025. ABC sẽ chi trả vào ngày 25/11/2026."
        ev = extract(body, symbols=["ABC"])["events"][0]
        self.assertEqual(ev["dates"]["event_date_start"], "2026-11-25")
        self.assertIn("date_from_adjacent_sentence", ev["notes"])

    def test_adjacent_sentence_about_other_symbol_is_not_attached(self):
        body = "ABC thông báo chi trả cổ tức năm 2025. XYZ sẽ họp ĐHCĐ vào ngày 25/11/2026."
        r = extract(body, symbols=["ABC", "XYZ"])
        abc = [e for e in r["events"] if e["subjects"] == ["ABC"]][0]
        self.assertIsNone(abc["dates"]["event_date_start"])

    def test_future_marker_with_intervening_verb(self):
        s, _, _ = w.detect_status("Công ty A sẽ phối hợp Hiệp hội B tổ chức hội nghị X.")
        self.assertEqual(s, "planned")


def art(aid, publish, body, symbols=("ABC",)):
    return extract(body, symbols=symbols, publish=publish, aid=aid)


class TestDedupe(unittest.TestCase):
    def test_planned_then_occurred_is_transition_not_conflict(self):
        a1 = art("A1", "2026-10-01", "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        a2 = art("A2", "2026-10-16", "ABC đã ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        evs = w.deduplicate_events([a2, a1])
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual([s["article_id"] for s in e["supporting_sources"]], ["A1", "A2"])
        self.assertEqual([s["source_role"] for s in e["supporting_sources"]], ["original", "update"])
        self.assertEqual(e["conflicts"], [])
        self.assertEqual([h["status"] for h in e["status_history"]], ["planned", "occurred"])
        self.assertEqual(e["current_best"]["status"], "occurred")

    def test_status_regression_is_conflict_and_keeps_both(self):
        a1 = art("A1", "2026-10-16", "ABC đã ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        a2 = art("A2", "2026-10-20", "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        e = w.deduplicate_events([a1, a2])[0]
        self.assertEqual(e["review_flag"], "conflict")
        self.assertEqual(e["conflicts"][0]["field"], "status")
        self.assertEqual({v["value"] for v in e["conflicts"][0]["values"]}, {"occurred", "planned"})
        self.assertEqual(len(e["supporting_sources"]), 2)

    def test_cancelled_after_planned_is_transition(self):
        a1 = art("A1", "2026-10-01", "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        a2 = art("A2", "2026-10-10", "ABC hủy lễ ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        self.assertEqual(w.deduplicate_events([a1, a2])[0]["conflicts"], [])

    def test_missing_subject_or_date_is_not_merged(self):
        a1 = art("A1", "2026-10-01", "Công ty sẽ chi trả cổ tức.", symbols=())
        a2 = art("A2", "2026-10-02", "Công ty sẽ chi trả cổ tức.", symbols=())
        evs = w.deduplicate_events([a1, a2])
        self.assertEqual(len(evs), 2)
        self.assertTrue(all(e["review_flag"] == "merge_uncertain" for e in evs))

    def test_same_article_twice_kept_as_duplicate_not_lost(self):
        a1 = art("A1", "2026-10-01", "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026.")
        evs = w.deduplicate_events([a1, a1])
        self.assertEqual(len(evs), 1)
        self.assertEqual(len(evs[0]["supporting_sources"]), 1)
        self.assertEqual(evs[0]["duplicate_article_ids"], ["A1"])
        self.assertTrue(w.reconcile([a1, a1], evs)["ok"])

    def test_per_source_extractions_preserved(self):
        a1 = art("A1", "2026-10-01", "ABC sẽ ký thỏa thuận hợp tác trị giá 100 tỷ đồng vào ngày 15/10/2026.")
        a2 = art("A2", "2026-10-02", "ABC sẽ ký thỏa thuận hợp tác trị giá 120 tỷ đồng vào ngày 15/10/2026.")
        e = w.deduplicate_events([a1, a2])[0]
        figs = [f["value_raw"] for p in e["per_source_extractions"] for f in p["financial_figures_stated"]]
        self.assertIn("100 tỷ đồng", figs)
        self.assertIn("120 tỷ đồng", figs)

    def test_reschedule_links_related_events(self):
        a1 = art("A1", "2026-10-01", "ABC sẽ tổ chức ĐHCĐ vào ngày 15/11/2026.")
        a2 = art("A2", "2026-10-20", "ABC sẽ tổ chức ĐHCĐ vào ngày 20/12/2026.")
        evs = w.deduplicate_events([a1, a2])
        self.assertEqual(len(evs), 2)
        self.assertTrue(all(e["related_event_ids"] for e in evs))
        self.assertTrue(all(e["review_flag"] == "merge_uncertain" for e in evs))

    def test_reconcile_counts(self):
        arts = [art("A1", "2026-10-01", "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026."),
                art("A2", "2026-10-02", "VN-Index tăng 5 điểm trong phiên sáng.")]
        evs = w.deduplicate_events(arts)
        r = w.reconcile(arts, evs)
        self.assertTrue(r["ok"])
        self.assertEqual(r["articles_in"], 2)
        self.assertEqual(r["by_relevance"], {"relevant": 1, "not_relevant": 1})


class TestEnums(unittest.TestCase):
    def test_outputs_use_closed_value_sets(self):
        r = extract("Công ty A sẽ phối hợp Hiệp hội B tổ chức hội nghị X tại Hà Nội vào ngày 15/11. "
                    "ABC đã bổ nhiệm ông Nguyễn Văn M làm Tổng giám đốc.", symbols=["ABC"])
        self.assertIn(r["relevance"], w.RELEVANCE)
        for ev in r["events"]:
            self.assertIn(ev["event_type"], w.EVENT_TYPES)
            self.assertIn(ev["status"], w.STATUSES)
            self.assertIn(ev["dates"]["date_precision"], w.DATE_PRECISIONS)
            for p in ev["parties"]:
                self.assertIn(p["role"], w.ROLES)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        rows = [
            {"article_id": f"N{i}", "title": "", "publish_date": "2026-10-01T08:00:00+07:00",
             "url": f"http://x/{i}", "source_name": "t", "symbols": ["ABC"],
             "body": "ABC sẽ ký thỏa thuận hợp tác vào ngày 15/10/2026." if i % 2 == 0 else "VN-Index tăng 5 điểm."}
            for i in range(5)
        ]
        rows.append({"article_id": "BAD", "body": None, "title": None, "publish_date": None})
        self.manifest = self.dir / "m.jsonl"
        self.manifest.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        return w.main(list(argv))

    def test_default_runs_one_batch_only(self):
        out = self.dir / "out"
        self.run_cli("extract", "--manifest", str(self.manifest), "--output-dir", str(out),
                     "--batch-size", "2", "--as-of", "2026-10-30")
        files = sorted(p.name for p in out.glob("batch_*.jsonl"))
        self.assertEqual(files, ["batch_00000000.jsonl"])
        ck = json.loads((out / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(ck["next_offset"], 2)

    def test_resume_and_rerun_is_idempotent(self):
        out = self.dir / "out"
        common = ["extract", "--manifest", str(self.manifest), "--output-dir", str(out),
                  "--batch-size", "2", "--as-of", "2026-10-30"]
        self.run_cli(*common)
        self.run_cli(*common, "--resume")
        self.run_cli(*common, "--offset", "0")  # chạy lại lô 0 -> ghi đè, không nhân đôi
        files = sorted(p.name for p in out.glob("batch_*.jsonl"))
        self.assertEqual(files, ["batch_00000000.jsonl", "batch_00000002.jsonl"])
        n0 = len((out / "batch_00000000.jsonl").read_text(encoding="utf-8").splitlines())
        self.assertEqual(n0, 2)

    def test_dry_run_writes_nothing(self):
        out = self.dir / "out"
        self.run_cli("extract", "--manifest", str(self.manifest), "--output-dir", str(out),
                     "--batch-size", "2", "--dry-run")
        self.assertFalse(out.exists())

    def test_full_chain_no_article_lost(self):
        out, ded = self.dir / "out", self.dir / "ded"
        self.run_cli("extract", "--manifest", str(self.manifest), "--output-dir", str(out),
                     "--batch-size", "10", "--as-of", "2026-10-30")
        rc = self.run_cli("dedupe", "--input-dir", str(out), "--output-dir", str(ded))
        self.assertEqual(rc, 0)
        rep = json.loads((ded / "reconcile.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["articles_in"], 6)
        self.assertTrue(rep["ok"])


if __name__ == "__main__":
    unittest.main()