"""S5-WBS13.2: frozen new questions, separate label/route metrics, no product fixes."""
import argparse
import asyncio
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
DATASET = ROOT / 'backend/tests/fixtures/s5_wbs132_cases.json'
LABELS = {'PRICE', 'NUMERIC', 'ANALYSIS', 'NEWS', 'REPORT_CONTENT', 'PERSON_ROLE',
          'ENTITY_RELATION', 'COMPANY_OVERVIEW', 'CONVERSATION', 'OUT_OF_SCOPE', 'MIXED'}
BRANCHES = {'PRICE', 'VECTOR', 'ANALYSIS', 'NEWS', 'KNOWLEDGE', 'GRAPH', 'BOTH',
            'OVERVIEW', 'CONVERSATION', 'REFUSE', 'ASK_CLARIFICATION', 'MULTI'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(text):
    folded = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in folded if not unicodedata.combining(c))).split())


def validate_cases(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError('EMPTY_DATASET')
    ids, texts = set(), set()
    for row in cases:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip()
                                               for k in ('id', 'text', 'label', 'branch', 'family', 'note')):
            raise ValueError('INVALID_CASE')
        normalized = normalize(row['text'])
        if row['id'] in ids or not normalized or normalized in texts:
            raise ValueError('DUPLICATE_CASE')
        ids.add(row['id'])
        texts.add(normalized)
        if row['label'] not in LABELS or row['branch'] not in BRANCHES:
            raise ValueError('UNKNOWN_GOLD_LABEL_OR_BRANCH')
        components = row.get('components', [])
        if (not isinstance(components, list) or any(c not in LABELS - {'MIXED'} for c in components)
                or len(set(components)) != len(components)
                or (row['label'] == 'MIXED' and len(components) < 2)
                or (row['label'] != 'MIXED' and components)):
            raise ValueError('INVALID_COMPONENTS')
        if 'context' in row and not isinstance(row['context'], dict):
            raise ValueError('INVALID_CONTEXT')


def percentile(values, fraction):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def planner_summary(cases, rows):
    """Conditional metric: only cases whose planner was actually observed."""
    mapping = dict(VECTOR='VECTOR', PRICE='VECTOR', ANALYSIS='VECTOR', NEWS='VECTOR',
                   OVERVIEW='VECTOR', KNOWLEDGE='VECTOR', GRAPH='GRAPH', BOTH='BOTH',
                   ASK_CLARIFICATION='CLARIFY')
    by_id = {row['id']: row for row in rows}
    correct, observed, absent, mismatches = 0, 0, [], []
    for case in cases:
        expected = mapping.get(case['branch'])
        if expected is None:
            continue
        row = by_id.get(case['id'], {})
        plans = row.get('planner_outputs') or []
        if not plans:
            absent.append(case['id'])
            continue
        observed += 1
        actual = plans[0]['route']
        ok = not row.get('error') and actual == expected
        correct += ok
        if not ok:
            mismatches.append(dict(id=case['id'], expected=expected, actual=actual))
    return dict(correct=correct, observed_eligible=observed,
                accuracy=correct / observed if observed else None,
                not_observed_ids=absent, mismatches=mismatches,
                limitation='Conditional on planner observed, not whole-set accuracy; specialized/early exits may skip it.')


def summarize(cases, results):
    expected, actual = {c['id']: c for c in cases}, {}
    if len(expected) != len(cases):
        raise ValueError('DUPLICATE_CASE_ID')
    for row in results:
        if row['id'] not in expected or row['id'] in actual:
            raise ValueError('UNKNOWN_OR_DUPLICATE_RESULT')
        actual[row['id']] = row
    label = branch = joint = fallback = calls = raw_model = 0
    errors, missing, failed, times, by_label = [], [], [], [], defaultdict(lambda: Counter(total=0, label_correct=0, branch_correct=0, joint_correct=0))
    confusion = Counter()
    for ident, case in expected.items():
        row = actual.get(ident)
        by_label[case['label']]['total'] += 1
        if row is None:
            missing.append(ident)
            failed.append(ident)
            continue
        count = row.get('fallback_calls', 0)
        fallback += count > 0
        calls += count
        duration = row.get('elapsed_ms')
        if isinstance(duration, (float, int)) and math.isfinite(duration) and duration >= 0:
            times.append(duration)
        if row.get('error'):
            errors.append(ident)
        valid = not row.get('error')
        groups = ((row.get('classification') or {}).get('base_ranking') or {}).get('groups') or []
        raw_model += valid and bool(groups) and groups[0].get('intent_label') == case['label']
        a, b = valid and row.get('label') == case['label'], valid and row.get('branch') == case['branch']
        components = row.get('components') or []
        c = a and b and sorted(components) == sorted(case.get('components', []))
        label += a
        branch += b
        joint += c
        by_label[case['label']].update(label_correct=int(a), branch_correct=int(b), joint_correct=int(c))
        confusion[(case['label'], row.get('label') or 'MISSING')] += 1
        if not c:
            failed.append(ident)
    total = len(cases)
    return dict(total=total, label_correct=label, label_accuracy=label / total,
                raw_model_label_correct=raw_model, raw_model_label_accuracy=raw_model / total,
                branch_correct=branch, branch_accuracy=branch / total,
                joint_correct=joint, joint_accuracy=joint / total,
                fallback_cases=fallback, fallback_calls=calls, fallback_rate=fallback / total,
                missing_ids=missing, error_ids=errors, failed_ids=failed,
                latency=dict(sample_count=len(times), p50_ms=percentile(times, .50), p95_ms=percentile(times, .95)),
                by_label=dict(by_label), confusion=[dict(expected=a, actual=b, count=n) for (a, b), n in sorted(confusion.items())])


def _questions(value):
    if isinstance(value, list):
        for item in value:
            yield from _questions(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in ('text', 'question') and isinstance(item, str):
                yield item
            elif isinstance(item, (dict, list)):
                yield from _questions(item)


def audit(cases):
    paths = set((ROOT / 'docs/sprint5').rglob('*.jsonl'))
    paths.update((ROOT / 'backend/tests/fixtures').glob('*.json'))
    paths.discard(DATASET)
    paths.update((ROOT / 'data/router/v3').glob('*.csv'))
    paths.update((ROOT / 'data/router/v3').glob('*.json'))
    known, sources = [], []
    for path in sorted(paths):
        if path.suffix == '.csv':
            with path.open(encoding='utf-8-sig', newline='') as file:
                values = [r['question'] for r in csv.DictReader(file) if r.get('question')]
        elif path.suffix == '.jsonl':
            values = [q for line in path.read_text(encoding='utf-8').splitlines() if line.strip()
                      for q in _questions(json.loads(line))]
        else:
            values = list(_questions(json.loads(path.read_text(encoding='utf-8'))))
        sources.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), questions=len(values)))
        known.extend((normalize(q), str(path.relative_to(ROOT))) for q in values)
    exact = []
    similarities = []
    for case in cases:
        text = normalize(case['text'])
        matches = [path for question, path in known if question == text]
        if matches:
            exact.append(dict(id=case['id'], sources=sorted(set(matches))))
        nearest = max(((SequenceMatcher(None, text, question).ratio(), path, question)
                       for question, path in known), default=(0, None, None))
        similarities.append(dict(id=case['id'], character_similarity=round(nearest[0], 4),
                                 nearest_source=nearest[1], nearest_normalized_question=nearest[2]))
    return dict(sources=sources, known_questions=len(known), exact_duplicates=exact,
                similarity_method='Normalized character SequenceMatcher; descriptive only, not semantic independence proof',
                nearest_questions=similarities, blind_acceptance=False)


class Boundaries:
    """Record entry to retrieval; return empty data, never pretend to answer facts."""
    def __init__(self):
        self.calls = []

    async def retrieve(self, *args):
        graph = len(args) == 1
        scope = args[-1].model_dump() if graph else args[-1]
        self.calls.append(dict(kind='GRAPH' if graph else 'VECTOR', scope=scope))
        pack = dict(items=[], query_id='evaluation-empty', retrieval_backend='evaluation_boundary',
                    corpus_version_id='00000000-0000-0000-0000-000000000001',
                    data_version=dict(kind='INDEX', id='00000000-0000-0000-0000-000000000002'))
        return (pack, []) if graph else pack

    async def lookup(self, scope, **kwargs):
        self.calls.append(dict(kind='MARKET', scope=scope))
        return dict(status='NO_DATA', reason_code='EVALUATION_EMPTY_MARKET',
                    message='Synthetic empty boundary; not a factual financial answer.', evidence_pack=None)

    async def symbols(self):
        from src.retrieval_orchestration.input_normalization import registered_symbols
        return sorted(registered_symbols())

    async def bars(self, symbol, start, end):
        self.calls.append(dict(kind='PRICE_BARS', symbol=symbol, start=str(start), end=str(end)))
        return []


class Planner:
    def __init__(self, engine):
        self.engine, self.plans = engine, []

    def decide(self, *args, **kwargs):
        plan = self.engine.decide(*args, **kwargs)
        self.plans.append(plan.model_dump())
        return plan


class MeasuredProvider:
    """Allow only intent classification, with an evaluation-wide generation limit."""
    def __init__(self, provider, maximum):
        self.provider, self.maximum, self.calls, self.events = provider, maximum, 0, []
        self.attempts = 0

    async def count_tokens(self, body):
        self.attempts += 1
        return await self.provider.count_tokens(body)

    async def generate(self, body):
        from src.b1_answering.providers.gemini import GeminiError
        if 'intent_label' not in body.get('generationConfig', {}).get('responseJsonSchema', {}).get('properties', {}):
            raise AssertionError('Evaluation permits only intent classification, never financial answer generation')
        if self.calls >= self.maximum:
            raise GeminiError('EVALUATION_GENERATION_LIMIT')
        self.calls += 1
        event = dict(outcome='STARTED')
        self.events.append(event)
        started = time.perf_counter()
        try:
            response = await self.provider.generate(body)
            event.update(outcome='RECEIVED', payload=response.get('payload'),
                         usage=response.get('usage'), model_version=response.get('model_version'))
            return response
        except asyncio.CancelledError:
            event['outcome'] = 'CANCELLED_BY_TIMEOUT'
            raise
        except Exception as exc:
            event.update(outcome='ERROR', error_type=type(exc).__name__)
            raise
        finally:
            event['generation_elapsed_ms'] = round((time.perf_counter() - started) * 1000, 3)


def branch_of(result):
    action = result.get('b1_decision')
    if action == 'GREETING':
        return 'CONVERSATION'
    if action == 'UNSUPPORTED':
        return 'REFUSE'
    if action in ('ASK_CLARIFICATION', 'CLARIFICATION_STALLED', 'RESOLVE_REFERENCE'):
        return 'ASK_CLARIFICATION'
    route = (result.get('hybrid_router') or {}).get('route')
    if route in ('GRAPH', 'BOTH'):
        return route
    if route == 'CLARIFY':
        return 'ASK_CLARIFICATION'
    if action == 'PRICE_ANALYTICS':
        return 'PRICE'
    source = result.get('scope', {}).get('source_type')
    if source in ('PRICE', 'MARKET_ANALYSIS', 'COMPANY_PROFILE', 'COMPANY_OVERVIEW'):
        return {'PRICE':'PRICE', 'MARKET_ANALYSIS':'ANALYSIS',
                'COMPANY_PROFILE':'OVERVIEW', 'COMPANY_OVERVIEW':'OVERVIEW'}[source]
    if action == 'MARKET_LOOKUP' and source == 'NEWS':
        return 'NEWS'
    if action == 'SEARCH':
        return 'VECTOR'
    return 'UNKNOWN'


async def evaluate(cases, mode, progress, max_calls):
    from src.api.routers.research_chat import _intent_classifier
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.providers.gemini import GeminiProvider
    from src.core.config import get_settings
    from src.documents.embeddings import get_embedding_service
    from src.retrieval_orchestration.hybrid_router.decision_engine import ArtifactPredictor, DecisionEngine
    from src.retrieval_orchestration.intent_gate_v2 import decide
    from src.retrieval_orchestration.intent_v2_classifier import classify_intent
    from src.retrieval_orchestration.live_research import LiveResearchService
    from src.retrieval_orchestration.price_analytics import PriceAnalytics
    from src.retrieval_orchestration.web_chat_router import WebChatRouter

    settings, limits = get_settings(), Limits.load()
    provider = None
    if mode == 'real':
        provider = MeasuredProvider(GeminiProvider(limits,
            api_key=settings.gemini_api_key.get_secret_value(),
            free_tier_confirmed=settings.b1_gemini_free_tier_confirmed), max_calls)
    embedder = get_embedding_service()
    predictor = ArtifactPredictor()
    engine = DecisionEngine(predictor, threshold=predictor.threshold)
    started = time.perf_counter()
    print('Loading local BGE-M3 and frozen classifier artifacts...', flush=True)
    classify_intent('Khởi tạo bộ đánh giá định tuyến FinMind.', embedder=embedder)
    predictor.warmup()
    cold_ms = (time.perf_counter() - started) * 1000
    rows = []
    with progress.open('x', encoding='utf-8') as stream:
        for case in cases:
            boundary, planner = Boundaries(), Planner(engine)
            service = LiveResearchService(boundary, provider=provider, limits=limits,
                market=boundary, prices=PriceAnalytics(boundary),
                hybrid_router=WebChatRouter(lambda: planner, boundary, boundary),
                intent_classifier=_intent_classifier(embedder))
            row = dict(id=case['id'], question=case['text'], label=None, branch=None, components=[],
                       fallback_calls=0, error=None, gold_label=case['label'], gold_branch=case['branch'])
            before = provider.attempts if provider else 0
            before_generation = provider.calls if provider else 0
            event_start = len(provider.events) if provider else 0
            start = time.perf_counter()
            try:
                classified = classify_intent(case['text'], embedder=embedder)
                row.update(classifier_ms=round((time.perf_counter() - start) * 1000, 3),
                           classification=classified, gate=decide(classified)['decision'],
                           label=classified['resolution']['intent_label'],
                           components=classified['resolution']['component_labels'])
                runtime_start = time.perf_counter()
                result = await asyncio.wait_for(service.answer(case['text'], 'evaluation-only',
                    case.get('context'), today=date(2026, 11, 16)), timeout=45)
                row.update(elapsed_ms=round((time.perf_counter() - runtime_start) * 1000, 3),
                           branch=branch_of(result), result=result)
            except Exception as exc:
                row.update(error=type(exc).__name__, elapsed_ms=round((time.perf_counter() - start) * 1000, 3))
            row.update(fallback_calls=(provider.attempts - before) if provider else 0,
                       fallback_generation_calls=(provider.calls - before_generation) if provider else 0,
                       fallback_events=provider.events[event_start:] if provider else [],
                       planner_outputs=planner.plans, boundary_calls=boundary.calls)
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            print(f"{case['id']}: label={row['label']}, branch={row['branch']}, fallback={row['fallback_calls']}, error={row['error']}", flush=True)
    return rows, dict(cold_start_ms=round(cold_ms, 3), model=embedder.model_name,
        revision=embedder.revision, device=embedder.device, planner_threshold=predictor.threshold,
        fallback_mode=mode, fallback_model=limits.model, generation_limit=max_calls,
        boundary_policy='Empty corpus/graph/market/price data; AdminNewsChat omitted; no DB, Neo4j or financial generation',
        latency_scope='Warm in-process Chat routing with real BGE + optional Gemini classification; standalone classification measured separately; not HTTP/UI/full-answer latency')


def render(run, output):
    cases, rows = run['cases'], run['results']
    stats = summarize(cases, rows)
    stats['planner'] = planner_summary(cases, rows)
    details = {row['id']: row for row in rows}
    def ms(value):
        return f'{value:.1f}' if value is not None else 'N/A'
    lines = ['# S5-WBS13.2 — Đánh giá router và fallback', '',
        f"Commit: `{run['commit']}`. Bộ câu: `{run['dataset_version']}`; SHA-256 `{run['dataset_sha256']}`.", '',
        '## Kết quả', '',
        '| Chỉ số | Kết quả |', '| --- | --- |',
        f"| Nhãn đề xuất v2 đúng (luật + classifier) | {stats['label_correct']}/{stats['total']} ({stats['label_accuracy']:.1%}) |",
        f"| Nhãn top-1 mô hình tuyến tính trước luật | {stats['raw_model_label_correct']}/{stats['total']} ({stats['raw_model_label_accuracy']:.1%}) |",
        f"| Planner đúng trên các ca có quan sát planner | {stats['planner']['correct']}/{stats['planner']['observed_eligible']} (chỉ số có điều kiện) |",
        f"| Nhánh chọn trong harness đúng | {stats['branch_correct']}/{stats['total']} ({stats['branch_accuracy']:.1%}) |",
        f"| Đồng thời đúng nhãn, thành phần và nhánh | {stats['joint_correct']}/{stats['total']} ({stats['joint_accuracy']:.1%}) |",
        f"| Câu thực sự bắt đầu fallback | {stats['fallback_cases']}/{stats['total']} ({stats['fallback_rate']:.1%}) |",
        f"| Lượt generation fallback | {sum(r.get('fallback_generation_calls', 0) for r in rows)} |",
        f"| Lỗi runner / thiếu kết quả | {len(stats['error_ids'])} / {len(stats['missing_ids'])} |",
        f"| p50 / p95 định tuyến ấm | {ms(stats['latency']['p50_ms'])} / {ms(stats['latency']['p95_ms'])} ms |",
        f"| Nạp model/artifact ban đầu | {run['runtime']['cold_start_ms'] / 1000:.2f} giây |", '',
        'Thời gian ấm gồm classifier gọi trong Chat, planner và fallback Gemini khi có. Không gồm HTTP/UI, '
        'truy xuất nguồn thật hoặc sinh câu trả lời. Các lỗi vẫn nằm trong mẫu số; số mẫu thời gian là '
        f"{stats['latency']['sample_count']}. Cold start tách riêng. Fallback đếm lúc bắt đầu countTokens thật, "
        'generation được đếm riêng; nhãn gate FALLBACK không đồng nghĩa đã gọi Gemini.', '',
        '## Theo nhãn kỳ vọng', '', '| Nhãn | Số câu | Đúng nhãn | Đúng nhánh | Đồng thời đúng |', '| --- | ---: | ---: | ---: | ---: |']
    for label, counts in sorted(stats['by_label'].items()):
        lines.append(f"| {label} | {counts['total']} | {counts['label_correct']} | {counts['branch_correct']} | {counts['joint_correct']} |")
    lines += ['', '## Các ca cần review', '',
        '| ID | Câu hỏi | Nhãn kỳ vọng → thực tế | Nhánh kỳ vọng → thực tế | Lý do/trạng thái |', '| --- | --- | --- | --- | --- |']
    for case in cases:
        if case['id'] not in stats['failed_ids']:
            continue
        row = details.get(case['id'], {})
        result = row.get('result') or {}
        reason = row.get('error') or (result.get('intent') or {}).get('reason') or result.get('reason_code') or 'MISSING'
        lines.append(f"| {case['id']} | {case['text'].replace('|', '/')} | {case['label']} → {row.get('label')} | {case['branch']} → {row.get('branch')} | {reason} |")
    wrong_labels = [r['id'] for r in rows if r.get('label') != next(c['label'] for c in cases if c['id'] == r['id'])]
    gates = Counter(r.get('gate', 'MISSING') for r in rows)
    fallback_rows = [r for r in rows if r.get('fallback_calls')]
    annual_mismatch = [r['id'] for r in rows if r.get('label') in ('ANALYSIS', 'NEWS')
                       and ((r.get('result') or {}).get('scope') or {}).get('source_type') == 'BCTN']
    lines += ['', '## Phân tích để bàn giao', '',
        f"- Ca nhãn classifier khác kỳ vọng: {', '.join(wrong_labels) or 'không có'}. Đối chiếu note trong fixture trước khi chốt nhãn chuẩn.",
        f"- Gate của lần phân loại độc lập: {dict(sorted(gates.items()))}. Chỉ {len(fallback_rows)} câu thực sự bắt đầu fallback trong Chat. Hai số khác nhau vì Chat chỉ áp dụng fallback khi luật hiện có hỏi lại.",
        f"- Ca có nhãn v2 ANALYSIS/NEWS nhưng scope cuối là BCTN: {', '.join(annual_mismatch) or 'không có'}. Đây là khác biệt giữa nhãn và pipeline sau đó; đối chiếu câu hỏi và scope, chưa tự sửa parser/gate.",
        '- Kế hoạch GRAPH/BOTH và nhánh cuối có thể khác sau khi graph trả rỗng; xem cả planner_outputs, boundary_calls, scope và reason_code, không quy mọi ca lệch nhánh thành lỗi classifier.', '',
        '| Ca fallback thật | Gemini trả | Chat áp dụng nhãn | Nhánh cuối | Thời gian định tuyến |', '| --- | --- | --- | --- | ---: |']
    for row in fallback_rows:
        intent = (row.get('result') or {}).get('intent') or {}
        events = row.get('fallback_events') or []
        code = ((events[-1].get('payload') or {}).get('intent_label') if events else 'NO_GENERATION_RESULT')
        lines.append(f"| {row['id']} | {code} | {intent.get('applied')} | {row.get('branch')} | {ms(row.get('elapsed_ms'))} ms |")
    lines += ['', 'Kết quả fallback được giữ nguyên, kể cả nhãn hợp lệ nhưng Chat chưa có nhánh áp dụng. '
        'Không kết luận AI sai chỉ vì Chat vẫn hỏi lại. Không điều chỉnh ngưỡng hoặc nhãn để tăng tỷ lệ.', '',
        '## Phạm vi và giới hạn', '',
        '- Nhãn kỳ vọng do người triển khai tự soạn, chờ peer review. Không phải bộ kín độc lập; không dùng số này làm bảo đảm chất lượng trên mọi câu mới.',
        '- Audit trước chạy không trùng sau chuẩn hóa với các nguồn trong dataset-audit.json; độ giống ký tự cao nhất '
        f"{run['audit_max_similarity']:.4f}. Không trùng nguyên câu không chứng minh độc lập ngữ nghĩa.",
        '- BGE-M3 và hai classifier/artifact thật; gọi Gemini thật chỉ ở fallback nếu mode là real. Không fit lại hay sửa luật/ngưỡng để tăng điểm.',
        '- Dùng LiveResearchService + WebChatRouter + DecisionEngine + PriceAnalytics thật. Corpus, graph, feed thị trường và price bars trả rỗng tại biên có ghi trace; AdminNewsChat bỏ qua. Không truy cập DB/Neo4j hoặc lịch sử thật.',
        '- GRAPH/BOTH lấy từ kế hoạch mà bridge đã chọn; biên graph rỗng có thể dừng trước VECTOR. Đúng BOTH không chứng minh cả hai loại bằng chứng đã được lấy. Xem planner_outputs/boundary_calls từng ca.',
        '- Điểm planner chỉ tính các ca có planner_outputs và có mục tiêu ánh xạ được: PRICE/NEWS/ANALYSIS/OVERVIEW/KNOWLEDGE là VECTOR ở tầng planner, GRAPH/BOTH giữ nguyên, hỏi lại là CLARIFY. Các nhánh chuyên biệt ở tầng Chat vẫn đo riêng. Không dùng tỷ lệ có điều kiện này thay tỷ lệ toàn bộ 60 câu.',
        '- PRICE, NEWS, ANALYSIS, OVERVIEW là các nhánh chuyên biệt hiện có, không đổi tên thành VECTOR. MULTI là kỳ vọng xử lý hai mục tiêu không có graph, không mặc định BOTH.',
        '- REFUSE trong bảng là phép gom action UNSUPPORTED của backend; phải xem reason_code để phân biệt từ chối yêu cầu ngoài phạm vi và chưa hỗ trợ một truy vấn giá thiếu dữ kiện.',
        '- Nhãn/gate độc lập dùng nguyên câu đã khóa; Chat có bước normalize_user_text trước khi gọi lại classifier. Không mặc định hai lần nhận đầu vào giống hệt nhau.',
        '- Score classifier chưa hiệu chỉnh; confidence Gemini tự báo chỉ là cổng 0,60 hiện có. Không gọi các điểm này là xác suất đúng.',
        '- Chỉ đánh giá định tuyến trong harness, không xác nhận số liệu, citation, quyền hoặc giao diện Web Chat. Có ca sai là kết quả task đánh giá; không tự sửa phần của Huyền/Hưng.', '',
        '## Chạy lại', '', 'Từ thư mục gốc dự án (Python môi trường backend và model đã cache):', '', '```powershell',
        'backend\\.venv\\Scripts\\python.exe -X utf8 backend/scripts/evaluate_s5_wbs132.py --fallback real --out outputs/s5_wbs132_20261116/run02',
        '```', '', 'Tái sinh báo cáo từ đầu ra đã lưu, không gọi model/Google:', '', '```powershell',
        'backend\\.venv\\Scripts\\python.exe -X utf8 backend/scripts/evaluate_s5_wbs132.py --replay outputs/s5_wbs132_20261116/run01/results.json --out outputs/s5_wbs132_20261116/replay01',
        '```', '', 'Kỳ vọng được khóa trong `dataset-lock.json` ở thư mục cha. Không ghi đè lượt chạy cũ. '
        'Dùng `--fallback none` để đo khi không cấu hình provider; phải giữ kết quả chế độ đó riêng.', '']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'cases.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['id','question','expected_label','actual_label','expected_components','actual_components',
                         'expected_branch','actual_branch','label_ok','branch_ok','joint_ok','fallback_attempts',
                         'fallback_generations','classifier_ms','routing_ms','status','reason','error'])
        for case in cases:
            row = details.get(case['id'], {})
            label_ok = not row.get('error') and row.get('label') == case['label']
            branch_ok = not row.get('error') and row.get('branch') == case['branch']
            joint_ok = label_ok and branch_ok and sorted(row.get('components') or []) == sorted(case.get('components', []))
            result = row.get('result') or {}
            writer.writerow([case['id'], case['text'], case['label'], row.get('label'),
                ','.join(case.get('components', [])), ','.join(row.get('components') or []), case['branch'], row.get('branch'),
                int(label_ok), int(branch_ok), int(joint_ok), row.get('fallback_calls', 0), row.get('fallback_generation_calls', 0),
                row.get('classifier_ms'), row.get('elapsed_ms'), result.get('status'), result.get('reason_code'), row.get('error')])
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fallback', choices=('real','none'), default='none')
    parser.add_argument('--max-generation-calls', type=int, default=60)
    parser.add_argument('--replay', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Choose a new output directory; never overwrite evaluation evidence')
    if not 1 <= args.max_generation_calls <= 60:
        raise ValueError('Evaluation call limit must be 1..60')
    if args.replay:
        run = json.loads(args.replay.read_text(encoding='utf-8'))
        if run['dataset_sha256'] != sha(DATASET):
            raise ValueError('DATASET_CHANGED_SINCE_RUN')
        validate_cases(run['cases'])
        run['analysis_replayed_from_sha256'] = sha(args.replay)
        run['analysis_runner_sha256'] = sha(Path(__file__))
        args.out.mkdir(parents=True)
    else:
        lock_path = args.out.parent / 'dataset-lock.json'
        audit_path = args.out.parent / 'dataset-audit.json'
        lock = json.loads(lock_path.read_text(encoding='utf-8'))
        audited = json.loads(audit_path.read_text(encoding='utf-8'))
        if lock['dataset_sha256'] != sha(DATASET) or lock['audit_sha256'] != sha(audit_path) or audited['exact_duplicates']:
            raise ValueError('INVALID_DATASET_LOCK')
        dataset = json.loads(DATASET.read_text(encoding='utf-8'))
        validate_cases(dataset['cases'])
        watched = ['backend/src/retrieval_orchestration/' + name for name in
            ('live_research.py','intent_v2_classifier.py','intent_v2_rules.py','intent_gate_v2.py',
             'web_chat_router.py','price_analytics.py','hybrid_router/decision_engine.py')]
        watched += ['models/router_manifest.json','models/router_classifier.joblib',
                    'outputs/s5_intent_v2_20261113/artifact-v2/manifest.json',
                    'outputs/s5_intent_v2_20261113/artifact-v2/classifier.npz', 'docs/sprint5/intent-labels.v2.json']
        hashes = {name: sha(ROOT / name) for name in watched}
        args.out.mkdir(parents=True)
        rows, runtime = asyncio.run(evaluate(dataset['cases'], args.fallback, args.out / 'progress.jsonl', args.max_generation_calls))
        if hashes != {name: sha(ROOT / name) for name in watched} or lock['dataset_sha256'] != sha(DATASET):
            raise ValueError('SOURCE_OR_DATASET_CHANGED_DURING_RUN')
        run = dict(task='S5-WBS13.2', dataset_version=dataset['version'], dataset_sha256=sha(DATASET),
            cases=dataset['cases'], results=rows, runtime=runtime, source_sha256=hashes,
            commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            audit_max_similarity=max(r['character_similarity'] for r in audited['nearest_questions']),
            gold_status=dataset['annotation_status'], blind_acceptance=False)
    (args.out / 'results.json').write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    stats = render(run, args.out)
    print(json.dumps({key: stats[key] for key in ('total','label_correct','branch_correct','joint_correct','fallback_cases','error_ids')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
