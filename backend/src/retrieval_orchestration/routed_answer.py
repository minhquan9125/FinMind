"""WBS14 source-bound, extractive answers for GRAPH and BOTH routes.

This is deliberately an extractive B2 response. It never turns an absent edge
into a negative fact and does not enable the later B3 evidence/verifier stages.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from uuid import UUID


async def replay_pinned_source(pool, source: dict, corpus_version_id: str) -> dict | None:
    """Read an indexed chunk through the existing source reconstruction path."""
    from ..documents.repository import resolve_result_rows

    try:
        chunk_id = UUID(str(source['chunk_id']))
        document_id = UUID(str(source['document_id']))
        corpus_id = UUID(str(corpus_version_id))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            row = await conn.fetchrow('''
                SELECT t.chunk_id::text, t.document_id::text, t.chunk_index,
                       t.page_number AS page, t.content_hash, t.locator_json,
                       t.index_version_id::text, i.chunker_version,
                       d.title, d.doc_type, d.sha256 AS source_sha256
                FROM public.text_chunks t
                JOIN public.index_versions i USING(index_version_id)
                JOIN public.documents d USING(document_id)
                JOIN public.corpus_versions cv USING(index_version_id)
                JOIN public.corpus_documents cd ON cd.corpus_version_id=cv.corpus_version_id
                    AND cd.document_id=d.document_id AND cd.document_hash=d.sha256
                WHERE t.chunk_id=$1 AND cv.corpus_version_id=$2
                  AND t.superseded_at IS NULL AND i.status='ACTIVE' AND cv.status='FROZEN'
            ''', chunk_id, corpus_id)
            if row is None:
                return None
            resolved = await resolve_result_rows(conn, [row])
    item = resolved[0]
    stored_document_id = str(item['document_id'])
    if stored_document_id != str(document_id):
        if item.get('doc_type') != 'ANNUAL_REPORT':
            return None
        from ..documents.release_identity import validate_document_binding
        binding = validate_document_binding(stored_document_id, item['index_version_id'],
                                            item['locator_json'])
        if binding['source_document_id'] != str(document_id):
            return None
    text = item['text']
    if sha256(text.encode('utf-8')).hexdigest() != item['content_hash'].strip():
        return None
    return {'document_id': str(document_id), 'release_document_id': stored_document_id,
            'chunk_id': item['chunk_id'],
            'corpus_version_id': str(corpus_id), 'chunk_text': text,
            'content_hash': item['content_hash'].strip(),
            'source_sha256': item['source_sha256'].strip(),
            'title': item['title'], 'doc_type': item['doc_type'],
            'locator': item['locator_json'],
            'index_version_id': item['index_version_id']}


def _manifest(response_mode: str) -> dict:
    return {'mode': 'B2', 'response_mode': response_mode,
            'components': {'gemini': False, 'citation_binding': True,
                           'source_replay': True, 'b3_evidence_gate': False,
                           'b3_answer_verification': False}}


def _extract_vector_quote(text: str, scope: dict) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    metric = scope.get('metric_code')
    if metric:
        return next((line[:500] for line in lines if f'({metric})' in line), '')
    return (lines[1] if len(lines) > 1 else lines[0])[:500] if lines else ''


def compose_routed_answer(execution, replay, *, corpus_version_id: str) -> dict:
    """Bind router evidence to replayed source text and return a chat result."""
    merged = execution.consolidation
    route = execution.decision.route
    scope = execution.decision.scope.model_dump()
    required = ('GRAPH', 'VECTOR') if route == 'BOTH' else (route,)
    branch_states = deepcopy(merged['branch_states'])
    missing = [branch for branch in required if branch_states.get(branch, {}).get('status') != 'OK']
    items, claims, citations, rejected = [], [], [], list(merged['rejected_evidence'])
    used = set()
    per_branch = {branch: 0 for branch in required}
    if execution.execution_mode == 'LIVE':
        for entry in merged['evidence']:
            for source in entry['sources']:
                if (source.get('branch') not in required or not source.get('source_verified')
                        or per_branch[source['branch']] >= 3):
                    continue
                identity = (source.get('branch'), source.get('source_id'), source.get('chunk_id'))
                if identity in used:
                    continue
                used.add(identity)
                try:
                    verified = replay(source)
                except Exception:
                    verified = None
                text = verified.get('chunk_text') if isinstance(verified, dict) else None
                quote = source.get('quote')
                if not quote and isinstance(text, str):
                    quote = _extract_vector_quote(text, scope) if source['branch'] == 'VECTOR' else ''
                passage = text[:12000] if isinstance(text, str) else ''
                if (not isinstance(text, str) or not text or not isinstance(quote, str) or not quote
                        or quote not in passage or verified.get('document_id') != source.get('document_id')
                        or verified.get('chunk_id') != source.get('chunk_id')
                        or verified.get('corpus_version_id') != corpus_version_id
                        or (source.get('index_version_id') and source['index_version_id'] != verified.get('index_version_id'))
                        or verified.get('content_hash') != sha256(text.encode('utf-8')).hexdigest()
                        or (source.get('content_hash') and source['content_hash'] != verified['content_hash'])
                        or (source.get('source_sha256') and source['source_sha256'] != verified.get('source_sha256'))):
                    rejected.append({'task_id': source.get('task_id'), 'source_id': source.get('source_id'),
                                     'reason_code': 'ANSWER_SOURCE_REPLAY_MISMATCH'})
                    continue
                number = len(citations) + 1
                evidence_id = f"{source['branch']}:{source['source_id']}"
                item = {'evidence_id': evidence_id, 'source_id': source['source_id'],
                        'source_type': verified.get('doc_type') or (
                            'ANNUAL_REPORT' if source['branch'] == 'GRAPH' else 'BCTC'),
                        'document_id': source['document_id'], 'chunk_id': source['chunk_id'],
                        'release_document_id': verified.get('release_document_id'),
                        'source_sha256': verified.get('source_sha256'),
                        'content_sha256': verified['content_hash'], 'corpus_version_id': corpus_version_id,
                        'passage_sha256': sha256(passage.encode('utf-8')).hexdigest(),
                        'index_version_id': verified.get('index_version_id'),
                        'graph_version_id': source.get('graph_version_id'),
                        'company': source.get('company'), 'period': source.get('period'),
                        'branch': source['branch'], 'provenance': source.get('provenance'),
                        'title': verified.get('title') or 'Tài liệu nguồn',
                        'locator': deepcopy(verified.get('locator') or {}),
                        'passage': passage, 'quote': quote, 'source_verified': True}
                items.append(item)
                per_branch[source['branch']] += 1
                claims.append({'text': quote, 'evidence_ids': [evidence_id],
                               'support_quotes': [{'evidence_id': evidence_id, 'quote': quote}]})
                citations.append({key: deepcopy(item[key]) for key in (
                    'evidence_id', 'source_id', 'document_id', 'release_document_id', 'chunk_id', 'source_sha256',
                    'content_sha256', 'passage_sha256', 'corpus_version_id', 'index_version_id', 'graph_version_id',
                    'branch', 'provenance', 'title', 'locator')} | {'citation_number': number})
    represented = {item['branch'] for item in items}
    missing.extend(branch for branch in required if branch not in represented and branch not in missing)
    content_tasks = [task for task in getattr(execution.decision, 'tasks', ())
                     if task.adapter in ('CONTENT', 'VECTOR')]
    if ('VECTOR' in required and any(task.params.get('company_scope_policy') == 'EXPLICIT_OR_RESOLVED'
                                     for task in content_tasks)):
        periods = [period for period in scope.get('periods') or []
                   if isinstance(period, str) and len(period) in (4, 7) and period[:4].isdigit()]
        for company in scope.get('companies') or []:
            for period in periods or [None]:
                if not any(item['branch'] == 'VECTOR' and item.get('company') == company
                           and (period is None or item.get('period') in (period, f'{period}-YEAR'))
                           for item in items):
                    missing.append(f'VECTOR {company}' + (f' {period}' if period else ''))
    if merged['alignment_warnings'] or rejected:
        missing.append('đối chiếu nguồn/phiên dữ liệu')
    missing = list(dict.fromkeys(missing))
    complete = not missing and execution.status == 'OK'
    message = ('Đã trích nguyên văn từ nguồn đã đọc lại; chỉ các đoạn trích được dẫn nguồn.'
               if complete else 'Chưa đủ bằng chứng để trả lời: thiếu ' + ', '.join(missing or required) + '.')
    draft = ('\n\n'.join(f"{item['branch']}: {claim['text']} [{index}]"
                         for index, (item, claim) in enumerate(zip(items, claims), 1))
             if complete else '')
    answer = {'status': 'DRAFT_READY' if complete else 'INSUFFICIENT_EVIDENCE',
              'reason_code': 'SOURCE_EXTRACT' if complete else 'ROUTE_EVIDENCE_INCOMPLETE',
              'message': message, 'draft': draft or None, 'claims': claims if complete else [],
              'citations': citations if complete else [], 'manifest': _manifest('SOURCE_EXTRACT'),
              'trace': [{'event': 'routed_evidence_bound', 'route': route,
                         'source_count': len(items), 'missing': missing}]}
    return {'status': 'EVIDENCE_READY' if complete else 'INSUFFICIENT_EVIDENCE',
            'reason_code': answer['reason_code'], 'message': message,
            'execution_mode': execution.execution_mode, 'route': route, 'scope': scope,
            'answering': answer,
            'evidence_pack': {'schema_version': 'router-v1', 'corpus_version_id': corpus_version_id,
                              'items': items},
            'routing': {'branch_states': branch_states, 'execution_trace': deepcopy(merged['execution_trace']),
                        'rejected_evidence': rejected,
                        'alignment_warnings': deepcopy(merged['alignment_warnings'])}}


def reference_routed_answer(saved: dict) -> dict:
    """Return only citations saved with the previous answer; never call retrieval."""
    previous = deepcopy(saved)
    answer = previous.get('answering') or {}
    pack = previous.get('evidence_pack') or {}
    rows = pack.get('items') or []
    by_id = {item.get('evidence_id'): item for item in rows if isinstance(item, dict)} if isinstance(rows, list) else {}
    citations = answer.get('citations') or []
    valid = (pack.get('schema_version') == 'router-v1' and answer.get('status') == 'DRAFT_READY'
             and isinstance(citations, list) and bool(citations) and all(
                 isinstance(citation, dict)
                 and (item := by_id.get(citation.get('evidence_id'))) is not None
                 and isinstance(item.get('passage'), str)
                 and isinstance(item.get('quote'), str)
                 and isinstance(citation.get('citation_number'), int)
                 and isinstance(citation.get('title'), str)
                 and isinstance(citation.get('branch'), str)
                 and all(citation.get(key) == item.get(key) for key in (
                     'source_id', 'document_id', 'release_document_id', 'chunk_id', 'source_sha256', 'content_sha256', 'passage_sha256',
                     'corpus_version_id', 'index_version_id', 'graph_version_id', 'locator'))
                 and item.get('passage_sha256') == sha256(item.get('passage', '').encode('utf-8')).hexdigest()
                 and item.get('quote') in item.get('passage', '')
                 for citation in citations))
    if not valid:
        return {'status': 'INSUFFICIENT_EVIDENCE', 'reason_code': 'INVALID_SAVED_ROUTED_EVIDENCE',
                'message': 'Không xác minh được nguồn đã lưu của câu trả lời trước.',
                'scope': deepcopy(previous.get('scope') or {}), 'execution_mode': 'LIVE',
                'answering': {'status': 'INSUFFICIENT_EVIDENCE', 'claims': [], 'citations': []}}
    lines = [f"[{citation['citation_number']}] {citation['title']} — {citation['branch']}"
             for citation in citations]
    previous['answering'] = {**answer, 'draft': 'Nguồn của câu trả lời trước:\n' + '\n'.join(lines),
                             'reason_code': 'SOURCE_REFERENCE', 'claims': [],
                             'manifest': {**answer.get('manifest', {}),
                                          'response_mode': 'SAVED_SOURCE_REFERENCE'},
                             'trace': [{'event': 'saved_routed_source_reference'}]}
    previous['reason_code'] = 'SOURCE_REFERENCE'
    previous.setdefault('routing', {})['saved_source_reference'] = True
    return previous
