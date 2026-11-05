"""Fail-closed WBS06 checks. Quote membership alone is never entailment."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
import unicodedata

from pydantic import ValidationError

from .models import Candidate, Entity, ReviewResult, SourceProblem, digest
from .sources import SourceReader, compare_source

DIRECTIONS = {
    "HAS_SUBSIDIARY": ("company", {"Company"}, {"Company"}),
    "HAS_ASSOCIATE": ("company", {"Company"}, {"Company"}),
    "OWNS_SHARES": ("company", {"Company", "Person"}, {"Company"}),
    "COOPERATES_WITH": ("company", {"Company"}, {"Company"}),
    "HOLDS_ROLE": ("person", {"Person"}, {"Company"}),
    "APPOINTS": ("person", {"Company"}, {"Person"}),
    "DISMISSES": ("person", {"Company"}, {"Person"}),
    "INVOLVES": ("event", {"Event"}, {"Company", "Person"}),
}
REQUIRED_ATTRIBUTES = {
    "HAS_SUBSIDIARY": ("consolidation_basis",), "HAS_ASSOCIATE": ("accounting_basis",),
    "OWNS_SHARES": ("ownership_percent", "holding_basis"),
    "COOPERATES_WITH": ("cooperation_scope",), "HOLDS_ROLE": ("position",),
    "APPOINTS": ("position",), "DISMISSES": ("position",), "INVOLVES": ("participant_role", "event_type"),
}
METADATA = {"inference_basis", "assertion_status", "position_code", "organization_link_verified",
            "organization_basis", "proposed_stage", "person_mention_id", "company_mention_id",
            "review_item_id", "limitations", "date_mentions", "evidence_start", "evidence_end",
            "event_status", "needs_followup", "event_date_derived", "name_source", "confidence"}
PLANNED = re.compile(r"\b(?:dự kiến|kế hoạch|sẽ|đề nghị|đăng ký mua|đăng ký bán|xin từ nhiệm|có thể)\b")
NEGATED = re.compile(r"\bkhông\s+(?:phải|còn|hề|có|sở hữu|nắm giữ|hợp tác|là)\b")
RELATION_CUES = {
    "HAS_SUBSIDIARY": r"công ty con", "HAS_ASSOCIATE": r"công ty liên kết",
    "OWNS_SHARES": r"sở hữu|nắm giữ|cổ đông", "COOPERATES_WITH": r"hợp tác|ký kết",
    "HOLDS_ROLE": r"chủ tịch|giám đốc|ceo|hđqt|giữ chức",
    "APPOINTS": r"bổ nhiệm", "DISMISSES": r"miễn nhiệm",
    "INVOLVES": r"tham dự|tham gia|tổ chức|phát biểu|tài trợ|ký kết",
}
EVENT_CUES = {
    "conference_forum": r"hội nghị|diễn đàn|hội thảo|tọa đàm", "shareholder_meeting": r"đại hội.*cổ đông|đhđcđ|đhcđ",
    "agreement_signing": r"ký kết|thỏa thuận|hợp đồng", "product_launch": r"ra mắt|giới thiệu sản phẩm|khai trương",
    "appointment": r"bổ nhiệm|miễn nhiệm|từ nhiệm|bầu bổ sung",
    "corporate_action": r"cổ tức|phát hành|mua lại cổ phiếu|chia tách|chốt danh sách|ngày đăng ký cuối cùng|không hưởng quyền|chuyển sàn|niêm yết\s+(?:cổ phiếu|trên|tại|bổ sung)|chính thức giao dịch trên\s+(?:hose|hnx|upcom)",
    "exhibition_fair": r"triển lãm|hội chợ", "ceremony_other": r"lễ|khánh thành",
    "AGREEMENT_SIGNED": r"ký kết|thỏa thuận", "COLLABORATION": r"hợp tác",
    "PERSONNEL_CHANGE": r"bổ nhiệm|miễn nhiệm|từ nhiệm", "DISCLOSURE": r"công bố|thông báo",
    "DIVIDEND_OR_SHARE_DELIVERY": r"cổ tức|cổ phiếu thưởng",
}


def text_key(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


class IdentityRegistry:
    """Trusted WBS01/02 registry; candidate aliases cannot redefine an identity."""
    def __init__(self, rows):
        self.rows = {}
        for row in rows:
            if row.get("verified") is not True:
                continue
            key = row["entity_id"]
            if key in self.rows and self.rows[key] != row:
                raise ValueError("Conflicting registry identity")
            self.rows[key] = row
        self.sha256 = digest(list(self.rows.values()))

    def names(self, entity: Entity, errors, warnings):
        row = self.rows.get(entity.entity_id)
        if entity.resolution_status != "resolved" or not entity.identity_key:
            warnings.add("WARN_AMBIGUOUS_FACT")
        if row is None:
            warnings.add("WARN_ENTITY_UNVERIFIED")
            return [x for x in [entity.canonical_name, *entity.aliases] if x]
        if (entity.entity_type != row["entity_type"] or entity.identity_key != row.get("identity_key")
                or text_key(entity.canonical_name or "") != text_key(row["canonical_name"])):
            errors.add("ERR_ENTITY_IDENTITY_MISMATCH")
        return list({row["canonical_name"], *row.get("aliases", []), *row.get("ticker_aliases", [])})


def name_pattern(names):
    names = sorted({text_key(n) for n in names if n and n.strip()}, key=len, reverse=True)
    return r"(?<!\w)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w)" if names else r"(?!)"


def proof_patterns(kind, subject, target, attributes):
    gap = r"[^.!?;]{0,100}?"
    if kind == "HAS_SUBSIDIARY":
        return [rf"{target}\s+(?:là\s+)?công ty con\s+của\s+{subject}",
                rf"{subject}\s+(?:có|bao gồm)\s+(?:các\s+)?công ty con\s+(?:là\s+)?{target}"]
    if kind == "HAS_ASSOCIATE":
        return [rf"{target}\s+(?:là\s+)?công ty liên kết\s+của\s+{subject}",
                rf"{subject}\s+có\s+(?:các\s+)?công ty liên kết\s+(?:là\s+)?{target}"]
    if kind == "OWNS_SHARES":
        return [rf"{subject}\s+(?:hiện\s+|đang\s+)?(?:sở hữu|nắm giữ){gap}{target}",
                rf"{target}\s+(?:là\s+công ty\s+)?do\s+{subject}\s+sở hữu"]
    if kind == "COOPERATES_WITH":
        return [rf"{subject}\s+(?:đã\s+|đang\s+)?(?:hợp tác|ký kết thỏa thuận hợp tác)\s+(?:với\s+)?{target}",
                rf"{target}\s+(?:đã\s+|đang\s+)?hợp tác\s+(?:với\s+)?{subject}"]
    position = re.escape(text_key(attributes.get("position", ""))) or r"(?!)"
    if kind == "HOLDS_ROLE":
        return [rf"{subject}\s*(?:[-–,]\s*)?(?:(?:là|giữ chức|giữ chức vụ|đảm nhiệm chức vụ)\s+)?{position}\s+(?:của\s+|tại\s+)?{target}"]
    if kind in ("APPOINTS", "DISMISSES"):
        cue = "bổ nhiệm" if kind == "APPOINTS" else "miễn nhiệm"
        return [rf"{subject}\s+(?:đã\s+)?{cue}\s+(?:ông\s+|bà\s+)?{target}{gap}{position}",
                rf"{target}{gap}{subject}\s+{cue}{gap}{position}"]
    role = attributes.get("participant_role")
    cue = {"participant": "tham dự|tham gia", "organizer": "tổ chức", "co_organizer": "đồng tổ chức",
           "speaker": "phát biểu tại|diễn giả", "sponsor": "tài trợ", "counterparty": "ký kết"}.get(role)
    if kind == "INVOLVES" and cue:
        return [rf"{target}\s+(?:đã\s+)?(?:{cue})\s+(?:tại\s+)?{subject}"]
    return []


def date_supported(value, quote):
    if value in quote:
        return True
    y, m, d = value.split("-")
    return bool(re.search(rf"(?<!\d)0?{int(d)}[/.\-]0?{int(m)}[/.\-]{y}(?!\d)|"
                          rf"\bngày\s+0?{int(d)}\s+tháng\s+0?{int(m)}\s+năm\s+{y}\b", quote))


class ReviewEngine:
    def __init__(self, reader: SourceReader, registry: IdentityRegistry, *, today=None):
        self.reader, self.registry = reader, registry
        self.today = today or datetime.now(timezone.utc).date()

    async def evaluate(self, raw: dict) -> ReviewResult:
        errors, warnings, verified = set(), set(), []
        fingerprint = hashlib.sha256(repr(raw).encode()).hexdigest()
        try:
            fingerprint = digest(raw)
            candidate = Candidate.model_validate(raw)
        except (ValidationError, ValueError, TypeError):
            return ReviewResult(candidate_id=str(raw.get("candidate_id", "invalid")) if isinstance(raw, dict) else "invalid",
                candidate_sha256=fingerprint, status="REJECTED",
                reasons=["ERR_REQUIRED_FIELD"], checked_at=datetime.now(timezone.utc))
        rule = DIRECTIONS.get(candidate.relation_type)
        errors.update(code if isinstance(code, str) and code.startswith("ERR_") else "ERR_CONTRACT_INVALID"
                      for code in candidate.extractor_metadata.get("input_errors", []))
        if rule is None or rule[0] != candidate.group:
            errors.add("ERR_RELATION_UNSUPPORTED")
        elif candidate.subject.entity_type not in rule[1] or candidate.object.entity_type not in rule[2]:
            errors.add("ERR_RELATION_INVALID_DIRECTION")
        if candidate.subject.entity_id == candidate.object.entity_id:
            errors.add("ERR_RELATION_SELF_LOOP")
        if candidate.relation_type == "COOPERATES_WITH" and candidate.subject.entity_id > candidate.object.entity_id:
            errors.add("ERR_RELATION_INVALID_DIRECTION")
        names_s = self.registry.names(candidate.subject, errors, warnings)
        names_o = self.registry.names(candidate.object, errors, warnings)
        if not candidate.evidence:
            errors.add("ERR_EVIDENCE_MISSING")
        for ref in candidate.evidence:
            try:
                actual = await self.reader.resolve(ref)
                compare_source(ref, actual)
                verified.append(actual)
            except SourceProblem as exc:
                errors.add(exc.code)
            except Exception:
                # Connectivity/service failures are not successful verification.
                errors.add("ERR_SOURCE_UNAVAILABLE")
        quotes = [text_key(e.quote) for e in candidate.evidence]
        quote = " \n ".join(quotes)
        attrs = candidate.attributes
        for field in REQUIRED_ATTRIBUTES.get(candidate.relation_type, ()):
            if attrs.get(field) is None or attrs.get(field) == "":
                warnings.add("WARN_MISSING_REQUIRED_ATTRIBUTE")
        # These optional facts are checked explicitly below, even on relation
        # types where they are not mandatory (e.g. a subsidiary's ownership %).
        checked_optional=({'ownership_percent'} if candidate.relation_type in
                          {'HAS_SUBSIDIARY','HAS_ASSOCIATE'} else set())
        if 'relation_label' in attrs:
            # Validate the subtype against its quote instead of treating an
            # arbitrary label as unchecked metadata. This does not establish
            # a parent/child link or authorize joint-venture contract mapping.
            checked_optional.add('relation_label')
            label = text_key(attrs['relation_label']) if isinstance(attrs['relation_label'], str) else ''
            if (candidate.relation_type != 'HAS_ASSOCIATE'
                    or label not in {'công ty liên doanh', 'công ty liên kết'}
                    or not any(label in q for q in quotes)):
                errors.add('ERR_FACT_UNSUPPORTED')
        for field in set(attrs) - METADATA - set(REQUIRED_ATTRIBUTES.get(candidate.relation_type, ())) - checked_optional:
            warnings.add("WARN_UNCHECKED_ATTRIBUTE")
        if attrs.get("organization_link_verified") is False or attrs.get("inference_basis") == "document_issuer":
            warnings.add("WARN_AMBIGUOUS_FACT")
        if candidate.conflicts:
            warnings.add("WARN_CONFLICTING_SOURCES")
        assertion_state = candidate.assertion_status or attrs.get("assertion_status") or attrs.get("event_status", "")
        if PLANNED.search(quote) or str(assertion_state).upper() in {
                "PLANNED", "UNCERTAIN", "UNCONFIRMED", "RUMOR_OR_FORECAST", "CONDITIONAL", "APPROVED", "CANCELLED"}:
            # Event status 'approved' means an approved plan, not completed execution.
            warnings.add("WARN_AMBIGUOUS_FACT")
        if attrs.get("event_date_derived") or attrs.get("needs_followup"):
            warnings.add("WARN_AMBIGUOUS_FACT")
        if NEGATED.search(quote) or str(assertion_state).upper() == "NEGATED":
            errors.add("ERR_EVIDENCE_NEGATED")
        if candidate.relation_type == "HOLDS_ROLE" and re.search(r"\b(?:nguyên|từng|từ nhiệm|miễn nhiệm|đã thôi)\b", quote):
            warnings.add("WARN_HISTORICAL_ROLE")
        periods = candidate.temporal
        if not periods.get("as_of") and not periods.get("valid_from"):
            warnings.add("WARN_TEMPORAL_BASIS_MISSING")
        for key, value in periods.items():
            if key not in {"as_of", "valid_from", "valid_to"}:
                errors.add("ERR_REQUIRED_FIELD")
            if value is None:
                continue
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError()
            except (ValueError, TypeError):
                errors.add("ERR_TEMPORAL_INVALID")
                continue
            if not any(date_supported(value, q) for q in quotes):
                errors.add("ERR_FACT_UNSUPPORTED")
            if parsed > self.today:
                warnings.add("WARN_FUTURE_FACT")
        if periods.get("valid_from") and periods.get("valid_to") and periods["valid_from"] > periods["valid_to"]:
            errors.add("ERR_TEMPORAL_INVALID")
        if "ownership_percent" in attrs:
            try:
                percent = Decimal(str(attrs["ownership_percent"]))
                found = {Decimal(v.replace(",", ".")) for v in re.findall(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*%", quote)}
                if not percent.is_finite() or not 0 <= percent <= 100 or percent not in found:
                    errors.add("ERR_FACT_UNSUPPORTED")
            except (InvalidOperation, ValueError):
                errors.add("ERR_FACT_UNSUPPORTED")
            if 'ownership_percent' in checked_optional:
                # Number presence/range is checked above, but linking a number
                # in a table/list to THIS company still needs evidence review.
                warnings.add('WARN_EVIDENCE_INSUFFICIENT')
        for field in ("position", "cooperation_scope", "consolidation_basis", "accounting_basis"):
            if attrs.get(field) and text_key(str(attrs[field])) not in quote:
                errors.add("ERR_FACT_UNSUPPORTED")
        if "holding_basis" in attrs:
            phrase = {"direct": "trực tiếp", "indirect": "gián tiếp"}.get(attrs["holding_basis"])
            if phrase is None or phrase not in quote:
                errors.add("ERR_FACT_UNSUPPORTED")
        s, o = name_pattern(names_s), name_pattern(names_o)
        patterns = proof_patterns(candidate.relation_type, s, o, attrs)
        supported = any(re.search(pattern, q) for q in quotes for pattern in patterns)
        reverse = any(re.search(pattern, q) for q in quotes
                      for pattern in proof_patterns(candidate.relation_type, o, s, attrs))
        if not supported:
            if reverse and candidate.relation_type != "COOPERATES_WITH":
                errors.add("ERR_RELATION_INVALID_DIRECTION")
            elif (any(re.search(s, q) and re.search(o, q) for q in quotes)
                  and not re.search(RELATION_CUES.get(candidate.relation_type, r"(?!)"), quote)):
                errors.add("ERR_COOCCURRENCE_ONLY")
            else:
                warnings.add("WARN_EVIDENCE_INSUFFICIENT")
        if candidate.group == "event":
            event_type = attrs.get("event_type")
            if event_type not in EVENT_CUES:
                warnings.add("WARN_EVENT_TYPE_UNSUPPORTED")
            elif quotes and not re.search(EVENT_CUES[event_type], quote):
                errors.add("ERR_EVENT_TYPE_UNGROUNDED")
            role = attrs.get("participant_role")
            if role == "mentioned_only":
                errors.add("ERR_COOCCURRENCE_ONLY")
            elif role in (None, "unspecified"):
                warnings.add("WARN_AMBIGUOUS_FACT")
        mode = ("LIVE" if verified and all(s.verification_mode == "LIVE" for s in verified)
                else "FIXTURE" if verified and all(s.verification_mode == "FIXTURE" for s in verified)
                else "UNVERIFIED")
        all_verified = len(verified) == len(candidate.evidence) and bool(verified)
        reasons = sorted(errors or warnings)
        return ReviewResult(candidate_id=candidate.candidate_id, candidate_sha256=fingerprint,
            status="REJECTED" if errors else "PENDING" if warnings else "APPROVED", reasons=reasons,
            source_verified=all_verified, verification_mode=mode, checked_at=datetime.now(timezone.utc),
            checks={"warnings": sorted(warnings), "registry_sha256": self.registry.sha256,
                    "direct_relation_supported": supported, "verified_sources": len(verified)})

    async def evaluate_batch(self, candidates):
        results = [await self.evaluate(c) for c in candidates]
        # Compare the SAME proposition and period, never different report years.
        groups = {}
        for raw, result in zip(candidates, results):
            try:
                c = Candidate.model_validate(raw)
            except ValidationError:
                continue
            # Two positions/scopes can coexist. A missing date also does not
            # prove two facts describe the same time. Only compare quantified
            # ownership claims on the same holding basis and explicit period.
            if c.relation_type != 'OWNS_SHARES' or not any(c.temporal.values()):
                continue
            key = (c.subject.entity_id, c.relation_type, c.object.entity_id,
                   c.attributes.get('holding_basis'), digest(c.temporal))
            groups.setdefault(key, []).append((c, result))
        for rows in groups.values():
            viable = [(c,r) for c,r in rows if r.status != "REJECTED"]
            values = {Decimal(str(c.attributes['ownership_percent'])) for c, _ in viable
                      if c.attributes.get('ownership_percent') is not None}
            if len(values) > 1:
                for _, result in viable:
                    result.status = "PENDING"
                    result.reasons = sorted(set(result.reasons) | {"WARN_CONFLICTING_SOURCES"})
                    result.checks['conflicting_candidates'] = sorted({c.candidate_id for c,_ in viable})
        return results
