"""Read-only, document-scoped personnel answers with independent source replay."""
import asyncio
import copy
import hashlib
import json
import logging
import re
from collections import defaultdict
from functools import lru_cache
from uuid import uuid4

from ..graph_review.models import Evidence
from ..graph_review.sources import PostgresSourceReader, compare_source
from ..person_role.source_claim_repairs import role_present
from .retrieval_flow.intent import _fold

SCOPE = 'SOURCE_DOCUMENT_ASSERTIONS'
PREDICATES = {'HOLDS_ROLE', 'APPOINTS', 'DISMISSES', 'FORMER_ROLE', 'RESIGNS', 'REQUESTS_RESIGNATION'}
EVENTS = {'HOLDS_ROLE': 'Chức vụ ghi trong nguồn', 'APPOINTS': 'Được bổ nhiệm theo nguồn',
          'DISMISSES': 'Được miễn nhiệm theo nguồn', 'FORMER_ROLE': 'Chức vụ trước đây theo nguồn',
          'RESIGNS': 'Từ nhiệm theo nguồn', 'REQUESTS_RESIGNATION': 'Đề nghị từ nhiệm theo nguồn'}


def personnel_role(text):
    text = _fold(text)
    for role, pattern in (
        ('SUPERVISORY', r'ban kiem soat|\bbks\b'),
        ('AUDIT', r'(?:uy ban|ban) kiem toan'),
        ('VICE_CHAIR', r'pho chu tich'),
        ('CHAIR', r'chu tich'),
        ('BOARD', r'hoi dong|\bhdqt\b|\bhdtv\b'),
        ('EXECUTIVE', r'ban dieu hanh|ban (?:tong )?giam doc|\bbgd\b|\bbdh\b'),
        ('CEO', r'tong giam doc|\bceo\b'),
        ('MANAGEMENT', r'lanh dao|nhan su quan ly'),
    ):
        if re.search(pattern, text):
            return role
    return None


def matches_role(position, role):
    value = _fold(position)
    if role == 'MANAGEMENT': return True
    if role == 'BOARD': return bool(re.search(r'hoi dong|\bhdqt\b|\bhdtv\b', value))
    if role == 'EXECUTIVE': return bool(re.search(r'giam doc|dieu hanh|\bceo\b|\bbgd\b|\bbdh\b', value))
    if role == 'CEO': return bool(re.search(r'tong giam doc|\bceo\b', value)) and 'pho' not in value
    if role == 'CHAIR': return 'chu tich' in value and 'pho' not in value
    if role == 'VICE_CHAIR': return 'pho chu tich' in value
    if role == 'SUPERVISORY': return bool(re.search(r'kiem soat|\bbks\b', value))
    if role == 'AUDIT': return 'kiem toan' in value
    return False


class SourcePersonnelReader:
    def __init__(self, store): self.store = store

    def company(self, symbol):
        # Only one newest published source version, one company, bounded rows.
        from neo4j import Query
        with self.store.driver.session(database=self.store.database, default_access_mode='READ') as session:
            rows = session.run(Query('''
                MATCH (v:SourcePersonGraphVersion {status:'READY',contract:'person-source-claims-v1',serving_scope:'SOURCE_DOCUMENT_ASSERTIONS'})
                MATCH (c:SourcePersonCompany {graph_version_id:v.key,symbol:$symbol})
                WITH v,c ORDER BY coalesce(v.created_at,'' ) DESC,v.key DESC LIMIT 1
                MATCH (c)-[r:SOURCE_PERSON_CLAIM]-(p:SourcePersonOccurrence)
                WHERE r.graph_version_id=v.key AND p.graph_version_id=v.key
                  AND r.source_review_status='APPROVED_IN_SOURCE_REPORT'
                  AND r.identity_scope='SOURCE_OCCURRENCE'
                  AND r.time_scope='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'
                  AND r.relation_type IN $types
                RETURN v.key AS version,p.name AS name,p.key AS person_id,c.key AS company_id,
                       startNode(r).key AS subject_id,properties(r) AS claim
                ORDER BY r.key LIMIT 201''', timeout=5), symbol=symbol, types=sorted(PREDICATES))
            return [dict(row) for row in rows]


@lru_cache(maxsize=1)
def get_source_personnel_reader():
    from ..graph.graph_store import GraphStore
    return SourcePersonnelReader(GraphStore.from_environment())


def close_source_personnel_reader():
    if get_source_personnel_reader.cache_info().currsize:
        get_source_personnel_reader().store.close()
        get_source_personnel_reader.cache_clear()


class PersonGraphChat:
    def __init__(self, reader_factory, pool, *, verify=None):
        self.reader_factory, self.pool = reader_factory, pool
        self.verify = verify or self._verify

    async def _verify(self, records):
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation='repeatable_read', readonly=True):
                reader = PostgresSourceReader(conn)
                grouped = defaultdict(list)
                for record in records:
                    for ref in record['refs']: grouped[ref.corpus_id].append(ref.chunk_id)
                for corpus, ids in grouped.items(): await reader.prefetch(ids, corpus)
                for record in records:
                    for ref, raw in zip(record['refs'], record['raw_refs']):
                        source = await reader.resolve(ref)
                        if source.verification_mode != 'LIVE': raise ValueError('Live replay required')
                        compare_source(ref, source)
                        start, end = raw.get('quote_start'), raw.get('quote_end')
                        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source.text)
                                or source.text[start:end] != ref.quote):
                            raise ValueError('Quote offsets changed')
                        row = reader.cache.get(('wbs06-row', str(ref.chunk_id), str(ref.corpus_id)))
                        if row is not None:
                            record.setdefault('source_metadata', {})[ref.chunk_id] = {'title': row['title'], 'url': row['source_url']}

    async def answer(self, question, result):
        scope = result['scope']
        role = scope.get('_person_role')
        if not role or scope.get('source_type') != 'NEWS' or scope.get('topic') != 'RELATIONSHIP_LOOKUP': return None
        out = copy.deepcopy(result)
        out['retrieval_backend'] = 'neo4j_source_person_claims'
        def stop(status, reason, message):
            out.update(status=status, reason_code=reason, message=message, evidence_pack=None)
            return out
        if len(scope.get('companies', [])) != 1:
            return stop('NO_DATA', 'PERSON_GRAPH_SINGLE_COMPANY', 'Vui lòng hỏi nhân sự của một công ty mỗi lần.')
        try:
            reader = await asyncio.to_thread(self.reader_factory)
            rows = await asyncio.to_thread(reader.company, scope['companies'][0])
            if len(rows) > 200: raise ValueError('Source graph exceeds bounded scope')
            periods = scope.get('periods') or ['LATEST_AVAILABLE_PERIOD']
            records = []
            for row in rows:
                claim = row['claim']
                if not matches_role(claim.get('position', ''), role): continue
                year = str(claim.get('source_report_year') or '')
                if periods != ['LATEST_AVAILABLE_PERIOD'] and year not in periods: continue
                if (claim.get('relation_type') not in PREDICATES or claim.get('graph_version_id') != row['version']
                        or claim.get('identity_scope') != 'SOURCE_OCCURRENCE'
                        or claim.get('time_scope') != 'SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'
                        or claim.get('source_review_status') != 'APPROVED_IN_SOURCE_REPORT'):
                    raise ValueError('Invalid source assertion')
                subject = row['company_id'] if claim['relation_type'] in ('APPOINTS', 'DISMISSES') else row['person_id']
                if row['subject_id'] != subject: raise ValueError('Predicate direction changed')
                raw_refs = json.loads(claim['evidence_json'])
                refs = [Evidence.model_validate({k: raw[k] for k in Evidence.model_fields}) for raw in raw_refs]
                if any(ref.locator.get('symbol') not in (None, scope['companies'][0]) for ref in refs):
                    raise ValueError('Source belongs to a different company')
                quote = '\n'.join(ref.quote for ref in refs)
                if not refs or _fold(row['name']) not in _fold(quote) or not role_present(claim['position'], quote):
                    raise ValueError('Person or role is not grounded in quotes')
                records.append({**row, 'refs': refs, 'raw_refs': raw_refs})
            if not records:
                return stop('NO_DATA', 'PERSON_GRAPH_NO_MATCH',
                            'Chưa có quan hệ nhân sự khớp nhóm chức vụ và thời điểm yêu cầu trong graph đã công bố. Điều này không khẳng định công ty không có nhân sự đó.')
            if len(records) > 50: raise ValueError('Too many claims for one answer')
            await self.verify(records)
        except Exception as error:
            logging.getLogger(__name__).warning('person_graph_source_replay_failed: %s', getattr(error, 'code', type(error).__name__))
            return stop('SYSTEM_UNAVAILABLE', 'PERSON_GRAPH_SOURCE_UNVERIFIED',
                        'Chưa đọc hoặc đối chiếu được graph nhân sự với nguồn gốc trong DB. Vui lòng thử lại sau.')
        items, citations, lines = [], [], []
        for record in records:
            claim = record['claim']; numbers = []
            for ref in record['refs']:
                number = len(items) + 1; numbers.append(f'[{number}]')
                locator = copy.deepcopy(ref.locator)
                metadata = record.get('source_metadata', {}).get(ref.chunk_id, {})
                # Source metadata comes from the replayed DB row, not a graph-supplied URL.
                item = dict(evidence_id=str(uuid4()), source_id=ref.document_id, chunk_id=ref.chunk_id,
                            source_type='GRAPH_SOURCE', source_sha256=ref.source_sha256,
                            content_sha256=hashlib.sha256(ref.quote.encode()).hexdigest(), passage=ref.quote,
                            source_verified=True, title=f"{scope['companies'][0]} · Nguồn nhân sự" + (f' · {claim["source_report_year"]}' if claim.get('source_report_year') else ''),
                            locator=locator, source_url=metadata.get('url'), source_ref=ref.model_dump(), graph_version_id=record['version'])
                if metadata.get('title'): item['title'] = metadata['title']
                items.append(item)
                citations.append({k: copy.deepcopy(item[k]) for k in ('evidence_id', 'source_id', 'chunk_id', 'source_type', 'source_sha256', 'content_sha256', 'source_verified', 'title', 'locator', 'source_url')} | {'citation_number': number})
            stamp = f"tài liệu năm {claim['source_report_year']}" if claim.get('source_report_year') else 'nguồn chưa ghi năm báo cáo'
            lines.append(f"- {record['name']} — {claim['position']}. {EVENTS[claim['relation_type']]} ({stamp}). {' '.join(numbers)}")
        caution = 'Đây là các ghi nhận trong nguồn đã lưu, chưa xác nhận chức vụ đương nhiệm hoặc ngày hiệu lực. Mỗi dòng là một lần xuất hiện trong tài liệu; không phải danh bạ đầy đủ của công ty.'
        pack = dict(schema_version='graph-source-v1', query_id=str(uuid4()),
                    data_version={'kind': 'GRAPH', 'id': records[0]['version']}, items=items)
        from ..b1_answering.evidence.citations import prepare_evidence
        try: prepare_evidence(pack)
        except Exception:
            return stop('INSUFFICIENT_EVIDENCE', 'PERSON_GRAPH_INVALID_EVIDENCE', 'Chưa xác minh được bằng chứng nhân sự để trả lời.')
        out.update(status='EVIDENCE_READY', reason_code='PERSON_GRAPH_SOURCE_CLAIMS', evidence_pack=pack,
                   query_id=pack['query_id'], message='Đã đối chiếu nhân sự theo nguồn gốc.',
                   presentation={'sources': 'GRAPH_QUOTES'},
                   answering={'status': 'DRAFT_READY', 'reason_code': 'PERSON_GRAPH_SOURCE_CLAIMS',
                              'draft': f"Thông tin nhân sự {scope['companies'][0]} theo nguồn đã lưu:\n\n" + '\n\n'.join(lines) + '\n\n' + caution,
                              'claims': [], 'citations': citations, 'cautions': [caution],
                              'manifest': {'response_mode': 'GRAPH_SOURCE_CLAIMS', 'components': {'gemini': False, 'graph': True, 'source_replay': True}}})
        return out
