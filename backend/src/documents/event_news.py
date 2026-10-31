"""WBS16 News Event Extractor v0.2 (rule-based, evidence-grounded).
 
Thay đổi so với v0.1 (xem phần review):
- Chuẩn hóa Unicode NFC một lần ở đầu vào; ngày đăng quy về giờ Việt Nam (UTC+7).
- Bên liên quan lấy từ chính câu; không còn gán cứng "organizer" từ metadata.
- Các câu cùng (loại sự kiện, chủ thể) trong một bài được gom thành một sự kiện.
- Ngày: nhiều định dạng, suy năm có quy tắc, nhiều ngày khác nhau -> đánh dấu mơ hồ.
- Trạng thái: phủ định, "hủy niêm yết", "hoãn", loại trừ "dự kiến doanh thu...", tín hiệu lẫn.
- Dedup: không gộp khi thiếu chủ thể/ngày (merge_uncertain), giữ mọi nguồn, chuyển trạng thái
  hợp lệ (planned -> occurred) không bị báo conflict, giữ trích xuất theo từng nguồn.
- Bộ chạy theo lô: extract / dedupe, checkpoint, ghi file theo lô (chạy lại không trùng).
 
Mặc định chỉ chạy 1 lô (chưa full-load). Muốn chạy toàn bộ phải thêm --allow-full-load.
"""
from __future__ import annotations
 
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
 
SCHEMA_VERSION = "0.1"
EXTRACTOR_VERSION = "0.2.0"
VN_TZ = timezone(timedelta(hours=7))
 
EVENT_TYPES = frozenset({
    "conference_forum", "shareholder_meeting", "agreement_signing", "product_launch",
    "appointment", "corporate_action", "exhibition_fair", "ceremony_other", "other_relevant",
})
ROLES = frozenset({
    "organizer", "co_organizer", "participant", "speaker", "sponsor",
    "counterparty", "mentioned_only", "unspecified",
})
STATUSES = frozenset({"occurred", "planned", "cancelled", "unconfirmed"})
DATE_PRECISIONS = frozenset({"day", "month", "quarter", "year", "unknown"})
RELEVANCE = frozenset({"relevant", "not_relevant", "uncertain"})
 
log = logging.getLogger("wbs16")
 
 
# --------------------------------------------------------------------------- #
# Tiện ích văn bản
# --------------------------------------------------------------------------- #
def nfc(text: Any) -> str:
    return unicodedata.normalize("NFC", "" if text is None else str(text))
 
 
def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
 
 
def split_sentences(text: str) -> List[str]:
    """Tách câu. Hạn chế đã biết: viết tắt có dấu chấm + khoảng trắng (vd 'TP. Hồ Chí Minh')."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", nfc(text))
    return [p.strip() for p in parts if len(p.strip()) > 5]
 
 
def parse_publish_date(raw: Any) -> Optional[str]:
    """Trả về YYYY-MM-DD theo giờ Việt Nam. Timestamp không có múi giờ coi là giờ Việt Nam."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(VN_TZ)
    return dt.date().isoformat()
 
 
# --------------------------------------------------------------------------- #
# Ngày
# --------------------------------------------------------------------------- #
_DATE_FULL = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
_DATE_TEXT = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?", re.I)
_DATE_SHORT = re.compile(r"ngày\s+(\d{1,2})[/-](\d{1,2})(?![/-]?\d)", re.I)
_DATE_REL = [
    (re.compile(r"\b(?:hôm nay|sáng nay|chiều nay|tối nay)\b", re.I), 0),
    (re.compile(r"\bhôm qua\b", re.I), -1),
    (re.compile(r"\bngày mai\b", re.I), 1),
]
 
 
def _infer_year(day: int, month: int, pub: date) -> Optional[date]:
    """Ngày thiếu năm: lấy năm của ngày đăng; lệch > 180 ngày thì dịch sang năm kề."""
    try:
        cand = date(pub.year, month, day)
        if cand < pub - timedelta(days=180):
            cand = date(pub.year + 1, month, day)
        elif cand > pub + timedelta(days=180):
            cand = date(pub.year - 1, month, day)
        return cand
    except ValueError:
        return None
 
 
def find_dates(sentence: str, publish_date: Optional[str]) -> List[Dict[str, Any]]:
    pub: Optional[date] = date.fromisoformat(publish_date) if publish_date else None
    out: List[Dict[str, Any]] = []
    used: List[Tuple[int, int]] = []
 
    def free(span: Tuple[int, int]) -> bool:
        return all(span[1] <= u[0] or span[0] >= u[1] for u in used)
 
    def add(d: Optional[date], derived: bool, m: "re.Match[str]") -> None:
        if d is None:
            return
        used.append(m.span())
        out.append({"date": d.isoformat(), "derived": derived, "evidence": m.group(0),
                    "pos": m.start()})
 
    for m in _DATE_FULL.finditer(sentence):
        d, mo, y = map(int, m.groups())
        try:
            add(date(y, mo, d), False, m)
        except ValueError:
            continue
    for m in _DATE_TEXT.finditer(sentence):
        if not free(m.span()):
            continue
        d, mo = int(m.group(1)), int(m.group(2))
        if m.group(3):
            try:
                add(date(int(m.group(3)), mo, d), False, m)
            except ValueError:
                pass
        elif pub:
            add(_infer_year(d, mo, pub), True, m)
    for m in _DATE_SHORT.finditer(sentence):
        if not free(m.span()) or not pub:
            continue
        add(_infer_year(int(m.group(1)), int(m.group(2)), pub), True, m)
    if pub:
        for pat, delta in _DATE_REL:
            for m in pat.finditer(sentence):
                if free(m.span()):
                    add(pub + timedelta(days=delta), True, m)
    out.sort(key=lambda x: x["pos"])
    return out
 
 
# --------------------------------------------------------------------------- #
# Trạng thái
# --------------------------------------------------------------------------- #
_FORECAST = re.compile(
    r"dự kiến\s+(?:doanh thu|lợi nhuận|tăng trưởng|kết quả kinh doanh|kết quả|lãi|lỗ|sản lượng|giá)",
    re.I)
 
 
def _c(*patterns: str) -> List["re.Pattern[str]"]:
    return [re.compile(p, re.I) for p in patterns]
 
 
_CANC = _c(r"hủy(?!\s+niêm yết)", r"hoãn vô thời hạn", r"không tổ chức nữa", r"dừng thực hiện")
_UNCONF = _c(r"theo nguồn tin", r"nguồn tin cho biết", r"tin đồn", r"chưa được xác nhận", r"có thể sẽ")
_OCC = _c(r"đã diễn ra", r"đã tổ chức", r"đã ký", r"đã thông qua", r"vừa diễn ra", r"vừa ký",
          r"khai mạc sáng nay", r"đã hoàn tất", r"đã hoàn thành", r"đã kết thúc", r"đã bổ nhiệm",
          r"đã miễn nhiệm", r"đã công bố", r"đã chi trả", r"đã thanh toán")
_PLAN = _c(r"sẽ diễn ra", r"sẽ tổ chức", r"sẽ chi trả", r"sẽ thực hiện", r"sẽ ký", r"dự kiến",
           r"sẽ\s+(?:phối hợp|họp|công bố|triển khai|ra mắt|khai trương|bổ nhiệm|phát hành|chốt|bầu)",
           r"sẽ\s+(?:\S+\s+){1,3}?(?:tổ chức|diễn ra)",
           r"sắp diễn ra", r"sắp tổ chức", r"thông báo mời họp", r"thời gian thực hiện là",
           r"hoãn(?!\s+vô thời hạn)")
_PLAN_WEAK = _c(r"kế hoạch")
_NEG_BEFORE = re.compile(r"(?:không|chưa)\s*$", re.I)
 
 
def detect_status(sentence: str) -> Tuple[str, List[str], List[str]]:
    """Trả về (status, signals, notes). Không có tín hiệu -> ('unconfirmed', [], ['no_status_signal'])."""
    s = _FORECAST.sub(" ", nfc(sentence))
    notes: List[str] = []
 
    def hits(patterns: List["re.Pattern[str]"]) -> List[Tuple[int, str]]:
        out: List[Tuple[int, str]] = []
        for pat in patterns:
            for m in pat.finditer(s):
                if _NEG_BEFORE.search(s[max(0, m.start() - 10):m.start()]):
                    continue
                out.append((m.start(), m.group(0).casefold()))
        return sorted(out)
 
    canc, unconf, occ, plan, weak = hits(_CANC), hits(_UNCONF), hits(_OCC), hits(_PLAN), hits(_PLAN_WEAK)
    if any(cue.startswith("hoãn") for _, cue in plan):
        notes.append("postponed")
    if canc:
        return "cancelled", [c for _, c in canc], notes
    if unconf:
        return "unconfirmed", [c for _, c in unconf], notes
    if occ and plan:
        notes.append("mixed_signals")
        status = "occurred" if occ[0][0] < plan[0][0] else "planned"
        return status, [c for _, c in sorted(occ + plan)], notes
    if occ:
        return "occurred", [c for _, c in occ], notes
    if plan:
        return "planned", [c for _, c in plan], notes
    if weak:
        return "planned", [c for _, c in weak], notes + ["weak_signal"]
    return "unconfirmed", [], notes + ["no_status_signal"]
 
 
# --------------------------------------------------------------------------- #
# Loại sự kiện, chủ thể, tổ chức, địa điểm, số liệu, claims
# --------------------------------------------------------------------------- #
_TRIGGERS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("agreement_signing", re.compile(
        r"ký kết|thỏa thuận hợp tác|hợp đồng kinh tế|bắt tay hợp tác|ký (?:biên bản|hợp đồng|thỏa thuận)", re.I)),
    ("appointment", re.compile(r"bổ nhiệm|miễn nhiệm|từ nhiệm|bầu bổ sung", re.I)),
    ("shareholder_meeting", re.compile(
        r"đại hội đồng cổ đông|đại hội cổ đông|đhcđ|nghị quyết hđqt|"
        r"(?:hđqt|hội đồng quản trị)\b.{0,60}?(?:họp|thông qua|nghị quyết)", re.I)),
    ("conference_forum", re.compile(r"hội nghị|hội thảo|diễn đàn|tọa đàm", re.I)),
    ("product_launch", re.compile(r"ra mắt|khai trương", re.I)),
    ("exhibition_fair", re.compile(r"triển lãm|hội chợ", re.I)),
    ("ceremony_other", re.compile(r"lễ kỷ niệm|lễ trao giải|lễ khởi công|lễ khánh thành", re.I)),
    ("corporate_action", re.compile(
        r"cổ tức|phát hành (?:thêm )?(?:cổ phiếu|trái phiếu|chứng chỉ)|chốt danh sách|"
        r"ngày đăng ký cuối cùng|không hưởng quyền|niêm yết|chuyển sàn", re.I)),
]
 
 
def detect_event_type(sentence: str) -> Optional[Tuple[str, str]]:
    """Khớp đầu tiên theo thứ tự ưu tiên. Hạn chế: một câu chỉ cho một loại."""
    for etype, pat in _TRIGGERS:
        m = pat.search(sentence)
        if m:
            return etype, m.group(0)
    return None
 
 
def find_subjects(sentence: str, symbols: List[str]) -> Tuple[List[str], str]:
    """Mã xuất hiện trong chính câu -> 'sentence'. Bài chỉ có đúng 1 mã -> 'metadata'. Còn lại -> 'none'."""
    found = [s for s in symbols if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", sentence)]
    if found:
        return found, "sentence"
    if len(symbols) == 1:
        return list(symbols), "metadata"
    return [], "none"
 
 
def _clean_org(name: str) -> str:
    name = _ws(name)
    name = re.sub(r"^(?:do|bởi)\s+", "", name, flags=re.I)
    for _ in range(3):
        name = re.sub(r"\s+(?:sẽ|đã|đang|vừa|sắp|dự kiến|cùng)$", "", name, flags=re.I)
    return name.strip(" ,;:")
 
 
def extract_orgs(sentence: str) -> List[Tuple[str, str]]:
    """Chỉ bắt các cấu trúc nêu rõ vai trò: 'A phối hợp B tổ chức', 'do A tổ chức/chủ trì'."""
    m = re.search(r"(?P<a>[^,.;:]{2,80}?)\s+phối hợp\s+(?:với\s+)?(?P<b>[^,.;:]{2,80}?)\s+(?:tổ chức|chủ trì)",
                  sentence, re.I)
    if m:
        a, b = _clean_org(m.group("a")), _clean_org(m.group("b"))
        return [(n, r) for n, r in ((a, "organizer"), (b, "co_organizer")) if n]
    m = re.search(r"\bdo\s+(?P<o>[^,.;:]{2,80}?)\s+(?:tổ chức|chủ trì)", sentence, re.I)
    if m:
        o = _clean_org(m.group("o"))
        return [(o, "organizer")] if o else []
    return []
 
 
def extract_location(sentence: str) -> Optional[str]:
    m = re.search(r"\btại\s+(.+)", sentence)
    if not m:
        return None
    toks: List[str] = []
    for tok in m.group(1).split():
        core = tok.strip(",.;:()\"'")
        if not core or not core[0].isupper() or len(toks) >= 5:
            break
        toks.append(core)
        if tok.endswith(","):
            break
    return " ".join(toks) or None
 
 
_FIGURE = re.compile(
    r"\d+(?:[.,]\d+)*\s*(?:(?:tỷ|triệu|nghìn|ngàn)\s+)?(?:đồng|cổ phiếu|cp\b|%(?:\s*mệnh giá)?)"
    r"|\d+(?:[.,]\d+)*\s*(?:tỷ|triệu|nghìn|ngàn)\b", re.I)
 
 
def extract_financial_figures(sentence: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for m in _FIGURE.finditer(sentence):
        val = m.group(0).strip()
        if val in seen:
            continue
        seen.add(val)
        if len(sentence) <= 200:
            ctx = sentence
        else:
            start = max(0, m.start() - 80)
            if start > 0:
                sp = sentence.find(" ", start)
                if sp != -1 and sp < m.start():
                    start = sp + 1
            end = min(len(sentence), m.end() + 80)
            if end < len(sentence):
                sp = sentence.rfind(" ", m.end(), end)
                if sp != -1:
                    end = sp
            ctx = sentence[start:end].strip()
        out.append({"value_raw": val, "context": ctx, "evidence": sentence})
    return out
 
 
_CLAIM = re.compile(r"\b(?:giúp|góp phần|tạo nền tảng|nhờ đó|do đó|dẫn đến|lý do là do)\b", re.I)
 
 
def extract_claims(sentence: str) -> List[Dict[str, Optional[str]]]:
    if _CLAIM.search(sentence):
        return [{"claim": sentence, "attributed_to": None, "evidence": sentence}]
    return []
 
 
# --------------------------------------------------------------------------- #
# Extractor mức bài
# --------------------------------------------------------------------------- #
def _first_text(article: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = article.get(k)
        if v not in (None, ""):
            return str(v)
    return ""
 
 
def _norm_symbols(article: Dict[str, Any]) -> List[str]:
    syms: List[str] = []
    for k in ("symbols", "matched_symbols"):
        v = article.get(k) or []
        if isinstance(v, str):
            v = re.split(r"[,\s;]+", v)
        syms.extend(str(s).strip().upper() for s in v if str(s).strip())
    return sorted(set(syms))
 
 
def _collect_evidence(obj: Any) -> Iterator[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (k.endswith("_evidence") or k == "evidence") and isinstance(v, str):
                yield v
            else:
                yield from _collect_evidence(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _collect_evidence(x)
 
 
class WBS16EventExtractor:
    def __init__(self, as_of: Optional[date] = None):
        # as_of cố định để kết quả tái lập được (ngày dùng cho needs_followup).
        self.as_of = as_of or date.today()
 
    # ---- đầu ra ---------------------------------------------------------- #
    def _empty(self, base: Dict[str, Any], relevance: str, reason: str) -> Dict[str, Any]:
        return {**base, "relevance": relevance, "relevance_reason": reason, "events": [],
                "qa": {"evidence_unverified": []}}
 
    def extract_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        title = nfc(article.get("title"))
        body = nfc(article.get("body") or article.get("content"))
        url = _first_text(article, "url")
        article_id = _first_text(article, "article_id", "provider_id", "id")
        if not article_id:
            article_id = "UNKNOWN-" + hashlib.sha1((url + title + body).encode("utf-8")).hexdigest()[:10]
        publish_date = parse_publish_date(_first_text(article, "publish_date", "published_at"))
        base = {
            "schema_version": SCHEMA_VERSION, "extractor_version": EXTRACTOR_VERSION,
            "article_id": article_id,
            "source_name": _first_text(article, "source_name", "source") or "unknown",
            "url": url, "publish_date": publish_date,
        }
        if not title.strip() and not body.strip():
            return self._empty(base, "not_relevant", "Nội dung bài viết rỗng.")
 
        symbols = _norm_symbols(article)
        sentences = ([title] if title.strip() else []) + split_sentences(body)
 
        groups: Dict[Tuple[str, Tuple[str, ...]], List[Dict[str, Any]]] = {}
        order: List[Tuple[str, Tuple[str, ...]]] = []
        last_key: Optional[Tuple[str, Tuple[str, ...]]] = None
        last_idx = -10
        for i, sent in enumerate(sentences):
            det = detect_event_type(sent)
            if not det:
                # Câu liền kề ngay sau câu sự kiện: chỉ nhận nếu có ngày và không nhắc mã khác.
                # (Ngày thường nằm ở câu kế bên; phạm vi 1 câu để hạn chế gán nhầm.)
                if last_key is not None and i == last_idx + 1:
                    adj_dates = find_dates(sent, publish_date)
                    if adj_dates:
                        other = [s for s in symbols
                                 if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", sent)]
                        if all(s in last_key[1] for s in other):
                            a_status, a_signals, a_notes = detect_status(sent)
                            groups[last_key].append({
                                "sentence": sent, "trigger": None, "subjects": [], "subject_source": "none",
                                "status": a_status, "signals": a_signals, "status_notes": a_notes,
                                "dates": adj_dates, "figures": extract_financial_figures(sent),
                                "claims": [], "orgs": [], "location": None, "adjacent": True,
                            })
                continue
            etype, trigger = det
            subjects, subj_src = find_subjects(sent, symbols)
            status, signals, snotes = detect_status(sent)
            rec = {
                "sentence": sent, "trigger": trigger, "subjects": subjects, "subject_source": subj_src,
                "status": status, "signals": signals, "status_notes": snotes,
                "dates": find_dates(sent, publish_date),
                "figures": extract_financial_figures(sent), "claims": extract_claims(sent),
                "orgs": extract_orgs(sent), "location": extract_location(sent),
            }
            key = (etype, tuple(subjects))
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(rec)
            last_key, last_idx = key, i
 
        events = [self._build_event(i + 1, k[0], list(k[1]), groups[k], publish_date)
                  for i, k in enumerate(order)]
 
        haystack = _ws(title + "\n" + body)
        bad = sorted({e for e in _collect_evidence(events) if _ws(e) not in haystack})
        if events:
            reason = f"Khớp {len(events)} sự kiện theo bộ cụm từ v{EXTRACTOR_VERSION}."
            relevance = "relevant"
        else:
            reason = "Không khớp cụm từ sự kiện nào trong bộ từ điển hiện tại (có thể bỏ sót)."
            relevance = "not_relevant"
        return {**base, "relevance": relevance, "relevance_reason": reason, "events": events,
                "qa": {"evidence_unverified": bad}}
 
    # ---- dựng một sự kiện từ nhóm câu ------------------------------------ #
    def _build_event(self, idx: int, etype: str, tickers: List[str], recs: List[Dict[str, Any]],
                     publish_date: Optional[str]) -> Dict[str, Any]:
        notes: List[str] = []
 
        # Trạng thái: ưu tiên cancelled > unconfirmed(có tín hiệu) > occurred > planned > không tín hiệu
        def rank(r: Dict[str, Any]) -> int:
            if not r["signals"]:
                return 4
            return {"cancelled": 0, "unconfirmed": 1, "occurred": 2, "planned": 3}[r["status"]]
 
        chosen = min(recs, key=rank)
        with_sig = {r["status"] for r in recs if r["signals"]}
        if len(with_sig) > 1:
            notes.append("mixed_status_sentences")
        for n in chosen["status_notes"]:
            if n not in notes:
                notes.append(n)
        status = chosen["status"]
 
        # Ngày
        cands: List[Dict[str, Any]] = []
        for r in recs:
            for d in r["dates"]:
                cands.append({"date": d["date"], "derived": d["derived"], "evidence": d["evidence"]})
        distinct = sorted({c["date"] for c in cands})
        if len(distinct) == 1:
            first = cands[0]
            dates = {"event_date_start": distinct[0], "event_date_end": distinct[0],
                     "date_precision": "day", "date_derived": first["derived"],
                     "date_evidence": first["evidence"], "date_candidates": cands}
        else:
            dates = {"event_date_start": None, "event_date_end": None, "date_precision": "unknown",
                     "date_derived": False, "date_evidence": None, "date_candidates": cands}
            if len(distinct) > 1:
                notes.append("multiple_distinct_dates")
 
        if any(r.get("adjacent") and r["dates"] for r in recs):
            notes.append("date_from_adjacent_sentence")
 
        # Bên liên quan
        parties: List[Dict[str, Any]] = []
        seen_p = set()
 
        def add_party(name: str, role: str, evidence: Optional[str], src: str, normalized: Optional[str]) -> None:
            k = (name.casefold(), role)
            if k in seen_p:
                return
            seen_p.add(k)
            parties.append({"name_raw": name, "name_normalized": normalized, "party_type": "organization",
                            "role": role, "role_evidence": evidence, "name_source": src})
 
        for r in recs:
            for sym in r["subjects"]:
                if r["subject_source"] == "sentence":
                    role = "counterparty" if etype == "agreement_signing" else "unspecified"
                    add_party(sym, role, r["sentence"], "sentence", sym)
                else:
                    add_party(sym, "unspecified", None, "metadata", sym)
            for name, role in r["orgs"]:
                add_party(name, role, r["sentence"], "sentence", _ws(name))
 
        if tickers:
            subjects = tickers
        else:
            subjects = sorted({p["name_normalized"] for p in parties
                               if p["role"] in ("organizer", "co_organizer") and p["name_normalized"]})
 
        loc_rec = next((r for r in recs if r["location"]), None)
        figures: List[Dict[str, str]] = []
        seen_f = set()
        for r in recs:
            for f in r["figures"]:
                k = (f["value_raw"], f["evidence"])
                if k not in seen_f:
                    seen_f.add(k)
                    figures.append(f)
        claims: List[Dict[str, Any]] = []
        seen_c = set()
        for r in recs:
            for c in r["claims"]:
                if c["evidence"] not in seen_c:
                    seen_c.add(c["evidence"])
                    claims.append(c)
 
        # Theo dõi
        needs_followup = False
        start = dates["event_date_start"]
        if status == "planned" and start and start < self.as_of.isoformat():
            needs_followup = True
            notes.append("planned_date_already_passed")
        if "mixed_status_sentences" in notes or "no_status_signal" in notes:
            needs_followup = True
 
        conf = 0.5
        conf += 0.2 if chosen["signals"] else 0.0
        conf += 0.1 if start else 0.0
        conf += 0.1 if any(r["subject_source"] == "sentence" for r in recs) else 0.0
        conf -= 0.15 if ("mixed_status_sentences" in notes or "mixed_signals" in notes) else 0.0
        conf = round(max(0.05, min(conf, 0.95)), 2)
 
        first = recs[0]
        return {
            "local_event_id": f"e{idx}",
            "event_type": etype,
            "event_name": first["trigger"],
            "event_name_evidence": first["sentence"],
            "subjects": subjects,
            "location": loc_rec["location"] if loc_rec else None,
            "location_evidence": loc_rec["sentence"] if loc_rec else None,
            "dates": dates,
            "status": status,
            "status_evidence": chosen["sentence"],
            "status_signals": chosen["signals"],
            "needs_followup": needs_followup,
            "parties": parties,
            "financial_figures_stated": figures,
            "claims_by_source": claims,
            "confidence": conf,
            "notes": ",".join(notes) or None,
        }
 
 
# --------------------------------------------------------------------------- #
# Gộp bài trùng / cập nhật (mức sự kiện)
# --------------------------------------------------------------------------- #
_STATUS_RANK = {"unconfirmed": 0, "planned": 1, "occurred": 2, "cancelled": 2}
 
 
def _event_key(art: Dict[str, Any], ev: Dict[str, Any]) -> str:
    subs = sorted(s.casefold() for s in ev.get("subjects", []))
    start = ev["dates"]["event_date_start"]
    if subs and start:
        return f"{ev['event_type']}|{'+'.join(subs)}|{start}"
    return f"UNMERGED|{art['article_id']}|{ev['local_event_id']}"
 
 
def _status_conflict(a_art: Dict[str, Any], a_ev: Dict[str, Any],
                     b_art: Dict[str, Any], b_ev: Dict[str, Any]) -> bool:
    """a đứng trước b theo ngày đăng. Chuyển trạng thái hợp lệ không phải mâu thuẫn."""
    sa, sb = a_ev["status"], b_ev["status"]
    if sa == sb:
        return False
    pa, pb = a_art.get("publish_date"), b_art.get("publish_date")
    if not pa or not pb or pa == pb:
        return True
    if {sa, sb} == {"cancelled", "occurred"}:
        return True
    return _STATUS_RANK[sb] < _STATUS_RANK[sa]
 
 
def deduplicate_events(article_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any]]]] = defaultdict(list)
    dups: Dict[str, List[str]] = defaultdict(list)
    seen = set()
    for art in article_results:
        for ev in art.get("events", []):
            key = _event_key(art, ev)
            sig = (key, art["article_id"])
            if sig in seen:
                dups[key].append(art["article_id"])
                continue
            seen.add(sig)
            groups[key].append((art, ev))
 
    out: List[Dict[str, Any]] = []
    for key, items in groups.items():
        items.sort(key=lambda x: (x[0].get("publish_date") or "9999-99-99", x[0]["article_id"]))
        first_art, first_ev = items[0]
        last_art, last_ev = items[-1]
 
        sources, history, per_source = [], [], []
        for i, (art, ev) in enumerate(items):
            role = "original" if i == 0 else ("update" if ev["status"] != first_ev["status"] else "repost")
            sources.append({"article_id": art["article_id"], "url": art["url"],
                            "source_name": art["source_name"], "publish_date": art["publish_date"],
                            "source_role": role})
            history.append({"status": ev["status"], "as_of_publish_date": art["publish_date"],
                            "article_id": art["article_id"]})
            per_source.append({
                "article_id": art["article_id"], "local_event_id": ev["local_event_id"],
                "status": ev["status"], "status_evidence": ev["status_evidence"],
                "dates": ev["dates"], "location": ev["location"],
                "location_evidence": ev["location_evidence"], "parties": ev["parties"],
                "financial_figures_stated": ev["financial_figures_stated"],
                "claims_by_source": ev["claims_by_source"], "notes": ev["notes"],
            })
 
        conflicts: List[Dict[str, Any]] = []
        status_conflict = any(
            _status_conflict(items[i][0], items[i][1], items[j][0], items[j][1])
            for i in range(len(items)) for j in range(i + 1, len(items)))
        if status_conflict:
            conflicts.append({"field": "status", "values": [
                {"value": ev["status"], "article_ids": [art["article_id"]], "evidence": ev["status_evidence"]}
                for art, ev in items]})
        locs: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for art, ev in items:
            if ev["location"]:
                locs[ev["location"].casefold()].append((art["article_id"], ev["location"]))
        if len(locs) > 1:
            conflicts.append({"field": "location", "values": [
                {"value": v[0][1], "article_ids": [a for a, _ in v], "evidence": None} for v in locs.values()]})
        roles: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        for art, ev in items:
            for p in ev["parties"]:
                if p["role"] not in ("unspecified", "mentioned_only"):
                    roles[p["name_raw"].casefold()][p["role"]].append(art["article_id"])
        for name, by_role in roles.items():
            if len(by_role) > 1:
                conflicts.append({"field": f"party_role:{name}", "values": [
                    {"value": r, "article_ids": ids, "evidence": None} for r, ids in by_role.items()]})
 
        if conflicts:
            flag = "conflict"
        elif key.startswith("UNMERGED|"):
            flag = "merge_uncertain"
        elif any(ev["needs_followup"] for _, ev in items):
            flag = "needs_followup"
        else:
            flag = "none"
 
        out.append({
            "event_id": "evt-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "event_key": key,
            "event_type": last_ev["event_type"],
            "subjects": last_ev.get("subjects", []),
            "current_best": {
                "status": last_ev["status"],
                "event_date_start": last_ev["dates"]["event_date_start"],
                "event_date_end": last_ev["dates"]["event_date_end"],
                "basis": "bài có ngày đăng mới nhất (chỉ là gợi ý, xem conflicts)",
            },
            "supporting_sources": sources,
            "duplicate_article_ids": dups.get(key, []),
            "per_source_extractions": per_source,
            "conflicts": conflicts,
            "status_history": history,
            "related_event_ids": [],
            "review_flag": flag,
        })
 
    # Cùng loại + chủ thể nhưng khác ngày, đăng gần nhau -> có thể là cập nhật đổi ngày
    by_subject: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for e in out:
        if e["subjects"] and not e["event_key"].startswith("UNMERGED|"):
            by_subject[(e["event_type"], "+".join(sorted(s.casefold() for s in e["subjects"])))].append(e)
    for evs in by_subject.values():
        for i, a in enumerate(evs):
            for b in evs[i + 1:]:
                pa = a["supporting_sources"][0]["publish_date"]
                pb = b["supporting_sources"][0]["publish_date"]
                if pa and pb and abs((date.fromisoformat(pa) - date.fromisoformat(pb)).days) <= 60:
                    a["related_event_ids"].append(b["event_id"])
                    b["related_event_ids"].append(a["event_id"])
                    for e in (a, b):
                        if e["review_flag"] == "none":
                            e["review_flag"] = "merge_uncertain"
    out.sort(key=lambda e: e["event_id"])
    return out
 
 
def reconcile(article_results: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Đối soát: mọi sự kiện đầu vào phải nằm trong một nhóm hoặc được ghi là bản trùng."""
    events_in = sum(len(a.get("events", [])) for a in article_results)
    placed = sum(len(e["supporting_sources"]) + len(e["duplicate_article_ids"]) for e in events)
    counts: Dict[str, int] = defaultdict(int)
    for a in article_results:
        counts[a.get("relevance", "?")] += 1
    return {"articles_in": len(article_results), "by_relevance": dict(counts),
            "events_in": events_in, "events_placed": placed, "events_out": len(events),
            "ok": events_in == placed}
 
 
# --------------------------------------------------------------------------- #
# Chạy theo lô
# --------------------------------------------------------------------------- #
def load_manifest(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.lstrip().startswith(("[", "{")) and not text.lstrip().startswith("{\""):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("articles") or data.get("items") or []
    else:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    for row in data:
        if not (row.get("body") or row.get("content")):
            rel = row.get("content_path") or row.get("path")
            if rel and (p.parent / rel).exists():
                row["body"] = (p.parent / rel).read_text(encoding="utf-8")
    return data
 
 
def _error_record(row: Dict[str, Any], exc: Exception) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "extractor_version": EXTRACTOR_VERSION,
        "article_id": _first_text(row, "article_id", "provider_id", "id") or "UNKNOWN",
        "source_name": _first_text(row, "source_name", "source") or "unknown",
        "url": _first_text(row, "url"), "publish_date": parse_publish_date(_first_text(row, "publish_date", "published_at")),
        "relevance": "uncertain", "relevance_reason": f"extractor_error: {type(exc).__name__}: {exc}",
        "events": [], "qa": {"evidence_unverified": []},
    }
 
 
def _atomic_write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)
 
 
def cmd_extract(args: argparse.Namespace) -> int:
    rows = load_manifest(args.manifest)
    total = len(rows)
    out_dir = Path(args.output_dir)
    ckpt = out_dir / "checkpoint.json"
    offset = args.offset
    if args.resume and ckpt.exists():
        offset = json.loads(ckpt.read_text(encoding="utf-8")).get("next_offset", offset)
    max_batches = None if args.allow_full_load else args.max_batches
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    extractor = WBS16EventExtractor(as_of=as_of)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
 
    done = 0
    while offset < total and (max_batches is None or done < max_batches):
        batch = rows[offset:offset + args.batch_size]
        results, errors = [], 0
        for row in batch:
            try:
                results.append(extractor.extract_article(row))
            except Exception as exc:  # noqa: BLE001 - ghi lỗi theo bài, không bỏ bài
                errors += 1
                log.exception("Lỗi bài %s", row.get("article_id") or row.get("id"))
                results.append(_error_record(row, exc))
        n_events = sum(len(r["events"]) for r in results)
        bad = sum(len(r["qa"]["evidence_unverified"]) for r in results)
        log.info("lô offset=%d size=%d events=%d errors=%d evidence_unverified=%d dry_run=%s",
                 offset, len(batch), n_events, errors, bad, args.dry_run)
        if not args.dry_run:
            _atomic_write_jsonl(out_dir / f"batch_{offset:08d}.jsonl", results)
            ckpt.write_text(json.dumps({
                "manifest": str(args.manifest), "next_offset": offset + len(batch),
                "batch_size": args.batch_size, "total": total,
                "extractor_version": EXTRACTOR_VERSION, "as_of": as_of.isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        offset += len(batch)
        done += 1
    log.info("Dừng tại offset=%d / total=%d (full-load %s)", offset, total,
             "BẬT" if args.allow_full_load else "tắt")
    return 0
 
 
def cmd_dedupe(args: argparse.Namespace) -> int:
    in_dir = Path(args.input_dir)
    results: List[Dict[str, Any]] = []
    for f in sorted(in_dir.glob("batch_*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            results.extend(json.loads(line) for line in fh if line.strip())
    events = deduplicate_events(results)
    report = reconcile(results, events)
    flags: Dict[str, int] = defaultdict(int)
    for e in events:
        flags[e["review_flag"]] += 1
    report["review_flags"] = dict(flags)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _atomic_write_jsonl(out / "events.jsonl", events)
    (out / "reconcile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("reconcile: %s", json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1
 
 
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="WBS16 News Event Extractor")
    ap.add_argument("--log-file")
    sub = ap.add_subparsers(dest="cmd", required=True)
 
    e = sub.add_parser("extract", help="trích xuất theo lô")
    e.add_argument("--manifest", required=True)
    e.add_argument("--output-dir", required=True)
    e.add_argument("--batch-size", type=int, default=50)
    e.add_argument("--offset", type=int, default=0)
    e.add_argument("--max-batches", type=int, default=1, help="mặc định 1 lô (chưa full-load)")
    e.add_argument("--allow-full-load", action="store_true", help="CHỈ WBS16 dùng; task này không chạy")
    e.add_argument("--resume", action="store_true", help="tiếp tục từ checkpoint")
    e.add_argument("--dry-run", action="store_true")
    e.add_argument("--as-of", help="YYYY-MM-DD, ngày dùng cho needs_followup (mặc định hôm nay)")
    e.set_defaults(func=cmd_extract)
 
    d = sub.add_parser("dedupe", help="gộp bài trùng từ các file lô")
    d.add_argument("--input-dir", required=True)
    d.add_argument("--output-dir", required=True)
    d.set_defaults(func=cmd_dedupe)
    return ap
 
 
def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    return args.func(args)
 
 
if __name__ == "__main__":
    raise SystemExit(main())
