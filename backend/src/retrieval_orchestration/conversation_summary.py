"""Bounded extractive summaries of source-bound answers in one owned session.

No retrieval or generation. Each original evidence pack retains its own schema,
corpus/index/feed identity; packs are not merged into a fictitious shared corpus.
"""
import copy
import json
import uuid

from ..b1_answering.evidence.citations import CitationError, prepare_evidence, validate_draft
from ..b1_answering.evidence.grounded import validate_grounded

MAX_TURNS = 12
MAX_SOURCES = 30
MAX_EVIDENCE_BYTES = 240_000
DERIVED_MODES = {'SESSION_SUMMARY', 'SAVED_SOURCE_REFERENCE'}


def _scope_key(scope):
    fields = ('companies','periods','topic','metric_code','source_type','measure_basis',
              'reporting_entity','person_name','position_code','relation_types',
              '_source_person_name','_source_role','_source_relation','_person_graph_name','_person_graph_role',
              '_article_urls')
    identity={k:scope.get(k) for k in fields}
    request=scope.get('_market_request') or {}
    identity['market_request']={k:request.get(k) for k in ('focus','day','query','action')}
    return json.dumps(identity,sort_keys=True,ensure_ascii=False)


def _summary_topic(claim, evidence):
    text=claim['text'].strip()
    for prefix,label in [('Nhận định tổng hợp:','Kết luận'),('Tình hình tài chính:','Tình hình kinh doanh'),
                         ('Xu hướng giá:','Giá và xu hướng'),('Giá:','Giá và xu hướng')]:
        if text.startswith(prefix): return label
    labels={'COMPANY_PROFILE':'Doanh nghiệp','PRICE':'Giá và xu hướng','PRICE_HISTORY':'Giá và xu hướng',
            'PRICE_TREND':'Giá và xu hướng','FINANCIAL_HEALTH':'Tình hình kinh doanh','BCTC':'Tình hình kinh doanh',
            'NEWS':'Tin tức','BCTN':'Thông tin trong báo cáo'}
    return next(iter({labels.get(evidence[eid].get('source_type'),'Nội dung khác')
                      for eid in claim['evidence_ids']})) if len({evidence[eid].get('source_type')
                      for eid in claim['evidence_ids']})==1 else 'Nội dung tổng hợp'


def group_summary(result):
    """Group validated statements by subject, without replaying the turn order.

    This is extractive: no new conclusions, external model or factual rewriting.
    Keep claims/citations aligned with what is actually shown.
    """
    if (result.get('answering') or {}).get('status') != 'DRAFT_READY':
        return result
    evidence = saved_evidence(result)
    groups, seen = {}, set()
    omitted = 0
    contexts=result['conversation_summary'].get('claim_contexts') or [{} for _ in result['answering']['claims']]
    for claim,context in reversed(list(zip(result['answering']['claims'],contexts))):
        text = claim['text']
        identity=(text,_scope_key(context))
        if identity in seen: continue
        seen.add(identity)
        label=_summary_topic(claim,evidence)
        company=', '.join(context.get('companies') or [])
        period=', '.join(context.get('periods') or [])
        group=(company,period,label)
        bucket = groups.setdefault(group,[])
        if len(bucket)>=2 or len(text)>600:
            omitted += 1
            continue
        bucket.insert(0,(copy.deepcopy(claim),copy.deepcopy(context)))
    priority={'Kết luận':0,'Tình hình kinh doanh':1,'Giá và xu hướng':2,'Doanh nghiệp':3,
              'Tin tức':4,'Thông tin trong báo cáo':5,'Nội dung tổng hợp':6,'Nội dung khác':7}
    ordered=sorted((key for key in groups if groups[key]),key=lambda k:(k[0],k[1],priority[k[2]]))
    chosen=[]
    for key in ordered:
        for claim,context in groups[key]:
            if len(chosen)>=12:
                omitted+=1
            else: chosen.append((key,claim,context))
    claims = [claim for _,claim,_ in chosen]
    if not claims:
        return result
    out = copy.deepcopy(result)
    used = list(dict.fromkeys(eid for claim in claims for eid in claim['evidence_ids']))
    citations = [{**copy.deepcopy(evidence[eid]),'citation_number':i} for i,eid in enumerate(used,1)]
    numbers = {c['evidence_id']:c['citation_number'] for c in citations}
    parts = ['Tổng hợp chung các nội dung đã trao đổi:']
    for company,period,label in ordered:
        group_claims=[claim for key,claim,_ in chosen if key==(company,period,label)]
        if not group_claims: continue
        paragraph = ' '.join(c['text']+' '+''.join(f'[{numbers[eid]}]' for eid in c['evidence_ids']) for c in group_claims)
        heading=' · '.join(filter(None,(company,period,label)))
        parts.append(heading+':\n'+paragraph)
    cautions = out['answering'].get('cautions') or []
    if cautions: parts.append('Lưu ý: '+' '.join(dict.fromkeys(cautions)))
    if omitted: parts.append('Bản ngắn chỉ giữ các ý chính có nguồn; các chi tiết còn ở câu trả lời trước.')
    out['answering'].update(draft='\n\n'.join(parts),claims=claims,citations=citations)
    out['conversation_summary']['style']='GROUPED_BRIEF'
    out['conversation_summary']['claim_contexts']=[context for _,_,context in chosen]
    out['conversation_summary']['omitted_turns'] += omitted
    return out


def saved_evidence(result):
    """Validate independent packs and reject ambiguous reuse of an evidence ID."""
    packs = result.get('evidence_packs')
    if packs is None:
        return prepare_evidence(result.get('evidence_pack'))
    if not isinstance(packs, list) or not 1 <= len(packs) <= MAX_TURNS:
        raise CitationError('INVALID_EVIDENCE')
    evidence = {}
    identity = ('source_id', 'chunk_id', 'source_sha256', 'content_sha256', 'locator', 'passage', 'source_type')
    for pack in packs:
        for eid, item in prepare_evidence(pack).items():
            if eid in evidence and any(evidence[eid].get(k) != item.get(k) for k in identity):
                raise CitationError('INVALID_EVIDENCE')
            evidence.setdefault(eid, item)
    if len(evidence) > MAX_SOURCES:
        raise CitationError('INVALID_EVIDENCE')
    return evidence


def _bound_answer(result):
    if (result.get('execution_mode') != 'LIVE'
            or (result.get('evidence_pack') or {}).get('schema_version') not in ('1.1', '1.2', '1.3')):
        raise CitationError('INVALID_EVIDENCE')
    answer = result.get('answering') or {}
    evidence = saved_evidence(result)
    citations = answer.get('citations') or []
    if not citations:
        raise CitationError('INVALID_CITATION')
    allowed = []
    for citation in citations:
        eid = citation.get('evidence_id')
        if eid not in evidence or any(citation.get(k) != evidence[eid].get(k) for k in (
                'source_id', 'chunk_id', 'source_sha256', 'content_sha256', 'locator')):
            raise CitationError('INVALID_CITATION')
        if eid not in allowed:
            allowed.append(eid)
    claims = answer.get('claims') or []
    if claims:
        if all('support_quotes' in claim for claim in claims):
            bound = validate_grounded({'claims': claims}, evidence, result.get('scope'))
        else:
            bound = validate_draft({'claims': claims}, evidence)
    elif (answer.get('manifest') or {}).get('response_mode') in ('NEWS_LIST', 'MARKET_QUOTE'):
        # List/quote handlers bind sources without model claims. Extract only
        # an actual title/observation already in those validated sources.
        extracts = []
        for eid in allowed:
            item = evidence[eid]
            text = item.get('title') if item.get('source_type') == 'NEWS' else item['passage']
            if isinstance(text, str) and text in item['passage']:
                extracts.append({'text': text, 'evidence_ids': [eid]})
        bound = validate_draft({'claims': extracts}, evidence)
    else:
        raise CitationError('INVALID_CITATION')
    if any(eid not in allowed for claim in bound['claims'] for eid in claim['evidence_ids']):
        raise CitationError('INVALID_CITATION')
    bound['cautions'] = list(dict.fromkeys(c for c in (
        list(bound.get('cautions') or []) + list(answer.get('cautions') or []))
        if isinstance(c, str) and c.strip()))
    if (result.get('freshness') or {}).get('stale'):
        bound['cautions'].append('Nguồn ở lượt này đang dùng bản lưu; lần cập nhật mới chưa thành công.')
    return bound, evidence


def summarize_session(doc):
    messages = doc.get('messages') or []
    start = max((i+1 for i, m in enumerate(messages) if m.get('role') == 'user'
                 and m.get('content', '').strip().lower() in ('/new', '/moi')), default=0)
    candidates = []
    missing = 0
    for position, message in enumerate(messages[start:], start):
        if message.get('role') != 'assistant':
            continue
        result = message.get('result') or {}
        answer = result.get('answering') or {}
        if (result.get('b1_decision') == 'SESSION_SUMMARY'
                or (answer.get('manifest') or {}).get('response_mode') in DERIVED_MODES
                or result.get('status') == 'GREETING'):
            continue
        if answer.get('status') != 'DRAFT_READY':
            missing += 1
            continue
        try:
            bound, evidence = _bound_answer(result)
        except (CitationError, KeyError, TypeError, ValueError, AttributeError):
            missing += 1
            continue
        candidates.append((position, result, bound, evidence))

    # For the same company/topic/period retain the last verified answer, while
    # keeping different companies, periods and metrics separate.
    latest={}
    for candidate in candidates:
        latest[_scope_key(candidate[1].get('scope') or {})]=candidate
    candidates=sorted(latest.values(),key=lambda candidate:candidate[0])

    result = dict(request_id=str(uuid.uuid4()), query_id=None, execution_mode='LIVE',
                  b1_decision='SESSION_SUMMARY', status='ASK_CLARIFICATION', reason_code='NO_SOURCED_SESSION_ANSWERS',
                  message='Phiên này chưa có câu trả lời có nguồn hợp lệ để tổng hợp.',
                  scope=copy.deepcopy(doc.get('metadata', {}).get('live_context', {})), evidence_pack=None,
                  errors=[], conversation_summary={'included_turns': [], 'omitted_turns': missing,'claim_contexts':[]})
    parts, claims, citations, packs, seen_claims = [], [], {}, [], set()
    cautions = []
    omitted = missing + max(0, len(candidates)-MAX_TURNS)
    for position, previous, bound, evidence in candidates[-MAX_TURNS:]:
        scope = previous.get('scope') or {}
        kept, new_keys = [], set()
        for claim in bound['claims']:
            key = (claim['text'], json.dumps(scope, sort_keys=True, ensure_ascii=False))
            if key in seen_claims or key in new_keys:
                continue
            if len(claim['text']) > 1500:
                omitted += 1
                continue
            new_keys.add(key)
            kept.append(claim)
        if not kept:
            continue
        # Keep complete original packs, so their data-version/hash checks remain valid.
        pack = copy.deepcopy(previous['evidence_pack'])
        trial_packs = packs + [pack]
        try:
            saved_evidence({'evidence_packs': trial_packs})
        except CitationError:
            omitted += 1
            continue
        if len(json.dumps(trial_packs, ensure_ascii=False).encode('utf-8')) > MAX_EVIDENCE_BYTES:
            omitted += 1
            continue
        packs = trial_packs
        seen_claims.update(new_keys)
        heading = ' · '.join(filter(None, (', '.join(scope.get('companies') or []), ', '.join(scope.get('periods') or []))))
        parts.append(heading or 'Nội dung đã trao đổi')
        for claim in kept:
            for eid in claim['evidence_ids']:
                if eid not in citations:
                    item = evidence[eid]
                    citations[eid] = {k: copy.deepcopy(item[k]) for k in (
                        'evidence_id', 'source_id', 'chunk_id', 'source_sha256', 'content_sha256',
                        'locator', 'title', 'source_type', 'source_verified') if k in item}
                    citations[eid]['citation_number'] = len(citations)
            parts.append('- '+claim['text']+' '+''.join(f"[{citations[eid]['citation_number']}]" for eid in claim['evidence_ids']))
            claims.append(copy.deepcopy(claim))
            result['conversation_summary']['claim_contexts'].append({k:copy.deepcopy(scope[k]) for k in (
                'companies','periods','topic','metric_code','source_type','measure_basis','reporting_entity',
                'person_name','position_code','relation_types') if k in scope})
        # Preserve cautions such as unknown units or reporting scope.
        source_cautions = bound.get('cautions', [])
        omitted += max(0, len(source_cautions)-4)
        for caution in source_cautions[:4]:
            if len(caution) > 1500:
                omitted += 1
                caution = caution[:1500]+'…'
            parts.append('Lưu ý: '+caution)
            if caution not in cautions:
                cautions.append(caution)
        result['conversation_summary']['included_turns'].append(position)
    result['conversation_summary']['omitted_turns'] = omitted
    if not claims:
        if candidates:
            result.update(reason_code='SUMMARY_LIMIT_REACHED',
                          message='Chưa tạo được bản tổng hợp trong giới hạn nguồn/dung lượng. Bạn có thể xem nguồn ở từng lượt trước.')
        return result
    notice = (f'Có {omitted} lượt/ý chưa đưa vào do thiếu nguồn hợp lệ hoặc giới hạn tổng hợp.' if omitted else '')
    draft = '\n\n'.join(['Tổng hợp các ý có nguồn trong phiên hiện tại:'] + parts + ([notice] if notice else []))
    result.update(status='EVIDENCE_READY', reason_code='SESSION_SUMMARY', message='Tổng hợp từ các câu trả lời đã lưu; không tra cứu hoặc sinh thêm.',
                  evidence_packs=packs, presentation={'sources': 'USED_LINKS'},
                  answering=dict(status='DRAFT_READY', reason_code='SESSION_SUMMARY', draft=draft,
                    claims=claims, citations=list(citations.values()), cautions=cautions+([notice] if notice else []),
                    manifest={'response_mode': 'SESSION_SUMMARY', 'components': {'gemini': False, 'citation_binding': True,
                              'b3_evidence_gate': False, 'b3_answer_verification': False}},
                    trace=[{'event': 'saved_session_summary', 'source_turns': result['conversation_summary']['included_turns']}]))
    return result
