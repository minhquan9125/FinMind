"""Bridge the authenticated web chat to the shared router and read-only graph.

Vector-only turns keep the existing financial/market pipeline. GRAPH/BOTH never
fall back to unrelated NEWS when Neo4j or its source replay is unavailable.
"""
import asyncio
import copy
import json
import re
import uuid

from .hybrid_router.decision_engine import SessionScope, ScopeResolver, position_matches, _normalize
from .hybrid_router.adapters import _period_window
from ..b1_answering.application.service import complete_retrieval
from ..b1_answering.evidence.citations import CitationError, prepare_evidence
from ..documents.chunk_reconstruction import ReconstructionError
from ..graph.viewer import SOURCE_SCOPE
from ..graph_review.models import Evidence, SourceProblem
from ..graph_review.sources import PostgresSourceReader, compare_source


class GraphChatError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def session_scope(context):
    values = (context or {}).get('_hybrid_context') or context or {}
    return SessionScope(**{key: values[key] for key in SessionScope.__dataclass_fields__
                           if key in values})


def anchor_graph_time(answer):
    """Resolve source-relative wording against the document, never today's date.

    Support quotes stay verbatim. Only presentation/claim wording is qualified;
    no date of departure, current-office assertion or new date is introduced.
    """
    if answer.get('status') != 'DRAFT_READY':
        return
    def anchored(text):
        text = re.sub(r'\b(?:tới|đến)\s+nay\b', 'đến thời điểm tài liệu ghi nhận', text, flags=re.I)
        return re.sub(r'\bhiện\s+(?:nay|tại)\b', 'tại thời điểm tài liệu ghi nhận', text, flags=re.I)
    before = answer['draft']
    answer['draft'] = anchored(before)
    for claim in answer.get('claims') or []:
        claim['text'] = anchored(claim['text'])
    if answer['draft'] != before:
        answer.setdefault('trace', []).append(dict(event='graph_source_relative_time_anchored'))


class Neo4jChatRetriever:
    """Reuse the viewer's READY/read-only contract and WBS06 source replay."""
    def __init__(self, retriever, reader_factory, ticker_map_factory=None):
        self.retriever = retriever
        self.reader_factory = reader_factory
        self.ticker_map_factory = ticker_map_factory

    def _query(self, scope, corpus_id, index_id, earlier_corpora=()):
        reader = self.reader_factory()
        # A graph built for an earlier frozen corpus stays usable after the serving corpus moves on (an admin
        # news run publishes a new corpus): its facts are only used when every source replays in the current one.
        versions = [v for v in reader.versions() if v['status'] == 'READY'
                    and (v.get('serving_scope') == SOURCE_SCOPE
                         or (v.get('corpus_id') == corpus_id and v.get('index_version_id') == index_id)
                         or (v.get('corpus_id') in earlier_corpora and v.get('corpus_id') != corpus_id))]
        if len(versions) > 8:
            raise GraphChatError('GRAPH_VERSION_SCOPE_AMBIGUOUS')
        tickers = (self.ticker_map_factory() if self.ticker_map_factory
                   and any(v.get('serving_scope') != SOURCE_SCOPE for v in versions) else {})
        by_ticker = {ticker: ident for ident, ticker in tickers.items()}
        facts, truncated = [], False
        name = scope.person_name
        for version in versions:
            gid = version['graph_version_id']
            source_scoped = version.get('serving_scope') == SOURCE_SCOPE
            roots = []
            if name:
                # A folded search mention never becomes a canonical identity.
                people, cut = reader.entities(gid, '', 'Person', 200)
                if cut:
                    raise GraphChatError('GRAPH_PERSON_SEARCH_TRUNCATED')
                roots = [p for p in people if _normalize(p['label']) == _normalize(name)]
            else:
                for ticker in scope.companies:
                    lookup = ticker if source_scoped else by_ticker.get(ticker, ticker)
                    candidates, cut = reader.entities(gid, lookup, 'Company', 50)
                    if cut:
                        raise GraphChatError('GRAPH_COMPANY_SEARCH_TRUNCATED')
                    roots.extend(n for n in candidates if ticker in n.get('aliases', [])
                                 or n.get('attributes', {}).get('symbol') == ticker
                                 or tickers.get(n['id']) == ticker
                                 or n['label'] == ticker)
            types = scope.relation_types or None
            periods = scope.periods
            concrete = [p for p in periods if re.fullmatch(r'\d{4}(?:-Q[1-4])?', p)]
            symbolic = [p for p in periods if p not in concrete]
            if any(p not in ('LATEST_AVAILABLE_PERIOD', 'LATEST_PUBLISHED_PERIOD', 'CURRENT') for p in symbolic):
                raise GraphChatError('GRAPH_UNSUPPORTED_PERIOD')
            if source_scoped and any('-Q' in p for p in concrete):
                continue  # A report year is not a quarter of office.
            start, end = (None, None) if source_scoped else _period_window(concrete)
            for root in roots:
                edges, cut = reader.neighborhood(gid, root['id'], hops=1,
                    relation_types=types, start=start, end=end, limit=200 if source_scoped else 100)
                truncated |= cut
                nodes = reader.nodes(gid, [ident for e in edges for ident in (e['subject_id'], e['object_id'])])
                for edge in edges:
                    if types and edge.get('relation_type') not in types:
                        continue
                    attrs = edge.get('attributes') or {}
                    if source_scoped and concrete and str(attrs.get('source_report_year')) not in concrete:
                        continue
                    if source_scoped:
                        if (edge.get('review_status') != 'SOURCE_REVIEWED'
                                or attrs.get('source_review_status') != 'APPROVED_IN_SOURCE_REPORT'
                                or attrs.get('identity_scope') != 'SOURCE_OCCURRENCE'
                                or attrs.get('time_scope') != 'SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'):
                            raise GraphChatError('GRAPH_UNREVIEWED_RELATION')
                    elif not edge.get('reviewer') or not edge.get('reviewed_at'):
                        raise GraphChatError('GRAPH_UNREVIEWED_RELATION')
                    subject, object_ = nodes.get(edge['subject_id']), nodes.get(edge['object_id'])
                    if not subject or not object_:
                        raise GraphChatError('GRAPH_ENDPOINT_MISSING')
                    companies = [n for n in (subject, object_) if n['type'] == 'Company']
                    symbols = [n.get('attributes', {}).get('symbol') or tickers.get(n['id']) or next(
                        (a for a in n.get('aliases', []) if a in scope.companies), None) for n in companies]
                    if scope.companies and not set(scope.companies).intersection(symbols):
                        continue
                    facts.append(dict(graph_version_id=gid, relation_id=edge['relation_id'],
                        origin_corpus_id=version.get('corpus_id'),
                        relation_type=edge['relation_type'], subject=subject['label'], object=object_['label'],
                        position=attrs.get('position'), source_report_year=attrs.get('source_report_year'),
                        position_code=attrs.get('position_code'),
                        source_scoped=source_scoped, companies=[s for s in symbols if s],
                        evidence=edge.get('evidence') or []))
        unique = {(f['graph_version_id'], f['relation_id']): f for f in facts}
        if truncated or len(unique) > 100:
            raise GraphChatError('GRAPH_RESULT_TRUNCATED')
        selected = list(unique.values())
        if (scope.position_code and scope.relation_types == ['HOLDS_ROLE']
                and any(p in ('LATEST_AVAILABLE_PERIOD', 'LATEST_PUBLISHED_PERIOD') for p in scope.periods)):
            # Resolve latest before filtering the requested role. Otherwise an
            # absent role in the latest report can resurrect an older holder.
            latest = {}
            for fact in selected:
                year = str(fact.get('source_report_year') or '')
                if fact['source_scoped'] and re.fullmatch(r'(?:19|20)\d{2}', year):
                    for company in fact['companies']:
                        latest[company] = max(latest.get(company, ''), year)
            selected = [f for f in selected if not f['source_scoped'] or all(
                company not in latest or str(f.get('source_report_year')) == latest[company]
                for company in f['companies'])]
        return [f for f in selected if position_matches(f.get('position'), scope.position_code, f.get('position_code'))]

    async def _replay(self, reader, raw, fact, cid, iid):
        """Rebind a release alias only after replaying the original graph source.

        An ID match or matching quote alone is insufficient: original review
        evidence, whole-source SHA, chunk SHA and logical source must agree.
        """
        origin = raw.get('corpus_id') or fact.get('origin_corpus_id')
        if not origin:
            raise GraphChatError('GRAPH_SOURCE_CORPUS_MISSING')
        if ('wbs06-row', str(raw['chunk_id']), str(origin)) not in reader.cache:
            await reader.prefetch([raw['chunk_id']], origin)
        original = await reader.read_current(raw['chunk_id'], origin)
        if fact['source_scoped']:
            ref = Evidence.model_validate({k: raw[k] for k in Evidence.model_fields})
            compare_source(ref, original)
        elif (raw.get('document_id') != original.document_id
                or raw.get('document_version') != original.document_version
                or not raw.get('quote') or raw['quote'] not in original.text):
            raise GraphChatError('GRAPH_SOURCE_MISMATCH')
        original_row = reader.cache[('wbs06-row', str(raw['chunk_id']), str(origin))]
        if str(origin) == cid and original.index_version_id == iid:
            return original, original_row
        loc = original_row['locator_json']
        loc = json.loads(loc) if isinstance(loc, str) else loc
        source_doc = (loc.get('reconstruction') or {}).get('document_id')
        if not source_doc:
            raise GraphChatError('GRAPH_SOURCE_VERSION_MISMATCH')
        matches = await reader.connection.fetch('''SELECT t.chunk_id::text AS chunk_id
            FROM text_chunks t JOIN documents d USING(document_id)
            JOIN corpus_documents cd ON cd.document_id=d.document_id AND cd.document_hash=d.sha256
            JOIN corpus_versions cv ON cv.corpus_version_id=cd.corpus_version_id AND cv.index_version_id=t.index_version_id
            JOIN index_versions i ON i.index_version_id=t.index_version_id
            WHERE cv.corpus_version_id=$1::uuid AND t.index_version_id=$2::uuid
              AND cv.status='FROZEN' AND i.status='ACTIVE' AND t.superseded_at IS NULL
              AND t.content_hash=$3 AND t.locator_json->>'source_table'=$4
              AND t.locator_json->>'source_id'=$5
              AND t.locator_json->'reconstruction'->>'document_id'=$6
            LIMIT 2''', uuid.UUID(cid), uuid.UUID(iid), original.content_hash,
            loc['source_table'], loc['source_id'], source_doc)
        if len(matches) != 1:
            raise GraphChatError('GRAPH_SOURCE_NOT_IN_ACTIVE_CORPUS')
        chunk_id = matches[0]['chunk_id']
        await reader.prefetch([chunk_id], cid)
        current = await reader.read_current(chunk_id, cid)
        if (current.index_version_id != iid or current.source_sha256 != original.source_sha256
                or current.content_hash != original.content_hash or current.text != original.text):
            raise GraphChatError('GRAPH_SOURCE_VERSION_MISMATCH')
        return current, reader.cache[('wbs06-row', chunk_id, cid)]

    async def _earlier_corpora(self, cid):
        """Other frozen corpora a graph may have been built for. Failing to list them only disables the carry-over."""
        try:
            rows = await self.retriever.pool.fetch(
                "SELECT corpus_version_id::text AS id FROM corpus_versions WHERE status='FROZEN' AND corpus_version_id<>$1::uuid", cid)
        except Exception:
            return frozenset()
        return frozenset(r['id'] for r in rows)

    async def retrieve(self, scope):
        corpus = await self.retriever._corpus()
        cid, iid = str(self.retriever.corpus_version_id), str(corpus['index_version_id'])
        earlier = await self._earlier_corpora(cid)
        facts = await asyncio.to_thread(self._query, scope, cid, iid, earlier)
        items, verified_facts, replayed_sources = {}, [], {}
        async with self.retriever.pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation='repeatable_read'):
                reader = PostgresSourceReader(conn)
                refs = [r for fact in facts for r in fact['evidence']]
                # Pin every source to the chat's current corpus, not a graph-supplied corpus.
                await reader.prefetch([r['chunk_id'] for r in refs], cid)
                for fact in facts:
                    if not fact['evidence']:
                        raise GraphChatError('GRAPH_EVIDENCE_MISSING')
                    evidence_ids = []
                    bindings = []
                    carried = fact.get('origin_corpus_id') in earlier
                    async def replay(raw):
                        # Facts of one report share their evidence; replaying a source once is enough.
                        key = (json.dumps(raw, sort_keys=True, default=str), fact['source_scoped'], fact.get('origin_corpus_id'))
                        if key not in replayed_sources:
                            replayed_sources[key] = await self._replay(reader, raw, fact, cid, iid)
                        return replayed_sources[key]
                    try:
                        replayed = [(raw, *await replay(raw)) for raw in fact['evidence']]
                        if any(source.index_version_id != iid or not source.active for _, source, _ in replayed):
                            raise GraphChatError('GRAPH_SOURCE_VERSION_MISMATCH')
                    except (GraphChatError, SourceProblem):
                        if carried:
                            continue     # an earlier graph's fact whose source is no longer identical: not used
                        raise
                    for raw, source, row in replayed:
                        loc = row['locator_json']
                        loc = json.loads(loc) if isinstance(loc, str) else copy.deepcopy(loc)
                        item = dict(evidence_id=source.chunk_id, chunk_id=source.chunk_id,
                            source_id=source.document_id, source_type={
                                'ANNUAL_REPORT': 'BCTN', 'NEWS': 'NEWS', 'FINANCIAL_STATEMENT': 'BCTC'
                            }.get(row['doc_type'], row['doc_type']), title=row['title'],
                            passage=source.text, source_sha256=source.source_sha256,
                            content_sha256=source.content_hash, source_verified=True, locator=loc,
                            source_url=row['source_url'], score=dict(type='RRF', value=1.0))
                        items[source.chunk_id] = item
                        if source.chunk_id in evidence_ids:
                            continue         # the same source quoted again adds nothing
                        evidence_ids.append(source.chunk_id)
                        bindings.append(dict(origin_chunk_id=raw['chunk_id'], chunk_id=source.chunk_id,
                            content_hash=source.content_hash, source_sha256=source.source_sha256))
                    verified_facts.append({k: v for k, v in fact.items() if k != 'evidence'}
                                          | dict(evidence_ids=list(dict.fromkeys(evidence_ids)), source_bindings=bindings))
        if len(items) > 30:
            raise GraphChatError('GRAPH_EVIDENCE_LIMIT')
        pack = dict(schema_version='1.1', query_id=str(uuid.uuid4()), corpus_version_id=cid,
                    data_version=dict(kind='INDEX', id=iid), items=list(items.values()),
                    retrieval_backend='neo4j_source_replay')
        if items:
            prepare_evidence(pack)
        return pack, verified_facts


class WebChatRouter:
    def __init__(self, planner_factory, graph_retriever, content_retriever, *, timeout=30):
        self.planner_factory = planner_factory
        self.graph_retriever = graph_retriever
        self.content_retriever = content_retriever
        self.timeout = timeout

    @staticmethod
    def _asks_for_news(question):
        padded = f' {_normalize(question)} '
        return any(f' {phrase} ' in padded for phrase in ('tin tuc', 'bai bao', 'bao chi'))

    async def _only_a_metric_question(self, question, context):
        """True when the graph route was chosen only because of words inside a metric name.

        "LNST thuộc cổ đông công ty mẹ" and "vốn chủ sở hữu" contain "cổ đông", "công ty mẹ", "sở hữu".
        Take the metric names out and ask the planner again: if it no longer wants the graph, the question
        is a plain financial one and belongs to the established pipeline.
        """
        from .metric_vocabulary import find_metrics, without_metrics
        from .retrieval_flow.intent import _fold
        folded = _fold(question)
        if not find_metrics(folded):
            return False
        rest = without_metrics(folded)
        try:
            again = await asyncio.wait_for(asyncio.to_thread(lambda: self.planner_factory().decide(
                rest, context=session_scope(context), request_id=str(uuid.uuid4()))), self.timeout)
        except Exception:
            return False
        return again.route not in ('GRAPH', 'BOTH')

    def _document_question(self, question, context):
        """True when the established parser reads this as a question about statements or the annual report:
        it would search them, or ask which statement metric is meant.

        Never true for a news request, so a relationship question cannot turn into news retrieval.
        """
        if self._asks_for_news(question):
            return False
        from .live_research import analyze_live
        try:
            decision = analyze_live(question, context)
        except Exception:
            return False
        source = decision['scope'].get('source_type')
        if decision['decision'] == 'SEARCH':
            return source in ('BCTC', 'BCTN')
        return (decision['decision'] == 'ASK_CLARIFICATION' and source == 'BCTC'
                and decision['reason_code'] in ('MISSING_METRIC', 'MULTIPLE_METRICS'))

    async def _content_fallback(self, question, scope, trace):
        """The graph holds nothing verified for a question about statements or the annual report.

        The router can read e.g. "công ty mẹ" as a relationship, so search that same source directly.
        This never reads NEWS: a relationship request must not turn into news retrieval, so an explicit
        request for news, or any other source, keeps the graph's NO_DATA answer.
        """
        source = scope.get('source_type')
        if source not in ('BCTC', 'BCTN') or not scope.get('companies'):
            return False, None
        if self._asks_for_news(question):
            return False, None
        content_scope = dict(companies=scope['companies'], periods=scope.get('periods') or [],
                             metric_code=None if source == 'BCTN' else scope.get('metric_code'),
                             reporting_entity=scope.get('reporting_entity') or 'UNKNOWN', source_type=source)
        trace['vector_calls'] += 1
        content = await asyncio.wait_for(self.content_retriever.retrieve(question, content_scope), self.timeout)
        if not content['items']:
            return True, None
        prepare_evidence(content)
        return True, content

    async def answer(self, question, context, *, provider, limits, budget):
        # Existing source-reference and new-session commands retain their contracts.
        if (_normalize(question) in ('moi', 'new') or re.fullmatch(
                r'(?:nguon(?: dau| o dau| nao| cua cau (?:tra loi )?(?:truoc|vua roi))?|xem nguon|cho (?:toi |minh |t )?xem nguon|trich dan(?: dau| nao)?)',
                _normalize(question))):
            return None
        try:
            plan = await asyncio.wait_for(asyncio.to_thread(lambda: self.planner_factory().decide(
                question, context=session_scope(context), request_id=str(uuid.uuid4()))), self.timeout)
        except Exception:
            # A failed classifier must not disable the established price/financial
            # service, nor silently turn a relationship request into NEWS retrieval.
            resolved = ScopeResolver().resolve(question, session_scope(context))
            if resolved.route_hint not in ('GRAPH', 'BOTH'):
                return None
            return dict(request_id=str(uuid.uuid4()), query_id=None, execution_mode='LIVE',
                b1_decision='SEARCH', status='SYSTEM_UNAVAILABLE', reason_code='CHAT_ROUTER_UNAVAILABLE',
                message='Bộ định tuyến tra cứu quan hệ tạm thời chưa khả dụng. Vui lòng thử lại.',
                scope=resolved.scope.model_dump(), evidence_pack=None, errors=[],
                hybrid_router=dict(route=resolved.route_hint, tasks=[], graph_calls=0, vector_calls=0))
        if plan.reason_code == 'AMBIGUOUS_COMPANY_MEMBERS':
            # The existing clarification handler supplies selectable groups and
            # persists the pending choice; do not generate from an arbitrary route.
            return None
        if plan.route not in ('GRAPH', 'BOTH'):
            if not (plan.route == 'CLARIFY' and (context or {}).get('_hybrid_context')
                    and plan.scope.topic != 'FINANCIAL_RESEARCH'):
                return None
        if plan.route in ('GRAPH', 'BOTH') and await self._only_a_metric_question(question, context):
            return None
        scope = plan.scope.model_dump()
        scope['_hybrid_context'] = copy.deepcopy(plan.scope.model_dump())
        trace = dict(route=plan.route, route_reason=plan.route_reason, model_version=plan.model_version,
                     tasks=[t.model_dump() for t in plan.tasks], graph_calls=0, vector_calls=0)
        result = dict(request_id=plan.request_id, query_id=None, execution_mode='LIVE',
            b1_decision=plan.decision, status=plan.decision, reason_code=plan.reason_code,
            message=plan.clarification_question or '', scope=scope, evidence_pack=None,
            errors=[], hybrid_router=trace)
        if plan.route == 'CLARIFY':
            result['clarification'] = plan.clarification_question
            return result
        try:
            trace['graph_calls'] += 1
            pack, facts = await asyncio.wait_for(self.graph_retriever.retrieve(plan.scope), self.timeout)
            fallback = None
            if not pack['items']:
                if self._document_question(question, context):
                    # Nothing verified in the graph and the established parser reads this as a statement or
                    # annual-report question: let that pipeline answer it with its own scope and checks.
                    return None
                searched, fallback = await self._content_fallback(question, scope, trace)
                if fallback is None:
                    if searched:
                        result.update(status='NO_DATA', reason_code='NO_DATA',
                                      message='Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.')
                    else:
                        result.update(status='NO_DATA', reason_code='GRAPH_NO_VERIFIED_RELATIONS',
                                      message='Chưa tìm thấy quan hệ có nguồn đã kiểm tra trong phạm vi bạn hỏi.')
                    return result
            if fallback is None:
                prepare_evidence(pack)
                scope['graph_relations'] = facts
                scope['graph_time_scope'] = 'SOURCE_DOCUMENT_NOT_CURRENT_OFFICE'
                if plan.route == 'BOTH':
                    for task in plan.tasks:
                        if task.adapter == 'GRAPH':
                            continue
                        requested = task.params.get('companies') or sorted({c for f in facts for c in f['companies']})
                        if task.params.get('company_scope_policy') == 'RELATED_COMPANIES':
                            # Do not invent ticker mappings from names/path endpoints.
                            raise GraphChatError('GRAPH_COMPANY_MAPPING_REQUIRED')
                        content_scope = dict(companies=requested, periods=scope['periods'],
                            metric_code=None if scope.get('source_type') == 'BCTN' else scope.get('metric_code'),
                            reporting_entity=scope.get('reporting_entity') or 'UNKNOWN',
                            source_type='COMPANY_PROFILE' if scope.get('topic') == 'COMPANY_PROFILE_WITH_RELATIONSHIPS' else 'BCTN' if scope.get('source_type') == 'BCTN' else 'BCTC' if scope.get('metric_code') else 'NEWS')
                        trace['vector_calls'] += 1
                        content = await asyncio.wait_for(self.content_retriever.retrieve(question, content_scope), self.timeout)
                        prepare_evidence(content)
                        if (content['corpus_version_id'] != pack['corpus_version_id']
                                or content['data_version'] != pack['data_version']):
                            raise GraphChatError('GRAPH_VECTOR_VERSION_MISMATCH')
                        merged = {i['evidence_id']: i for i in pack['items']}
                        for item in content['items']:
                            existing = merged.get(item['evidence_id'])
                            if existing:
                                # The same verified chunk can rank differently in
                                # graph and Vector; ranking is not source identity.
                                if any(existing.get(k) != item.get(k) for k in (
                                        'chunk_id','source_id','source_type','source_sha256',
                                        'content_sha256','locator','passage','title')):
                                    raise GraphChatError('GRAPH_VECTOR_EVIDENCE_CONFLICT')
                            else:
                                merged[item['evidence_id']] = item
                        pack['items'] = list(merged.values())
                        pack['retrieval_backend'] = 'neo4j_and_vector'
                prepare_evidence(pack)
        except TimeoutError:
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='GRAPH_CHAT_TIMEOUT',
                          message='Tra cứu quan hệ quá thời gian chờ. Vui lòng thử lại.')
            return result
        except (GraphChatError, SourceProblem, CitationError, ReconstructionError) as exc:
            result.update(status='INSUFFICIENT_EVIDENCE', reason_code=exc.code,
                          message='Chưa xác minh được quan hệ với nguồn của kho dữ liệu đang dùng.')
            return result
        except Exception:
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='GRAPH_CHAT_UNAVAILABLE',
                          message='Dịch vụ tra cứu quan hệ tạm thời chưa khả dụng. Vui lòng thử lại.')
            return result
        if fallback is not None:
            result.update(status='EVIDENCE_READY', reason_code='GRAPH_EMPTY_CONTENT_FALLBACK', query_id=fallback['query_id'],
                          evidence_pack=fallback, retrieval_backend=fallback.get('retrieval_backend', 'vector'))
            return await complete_retrieval(question, result, provider=provider, limits=limits, budget=budget)
        result.update(status='EVIDENCE_READY', reason_code='GRAPH_EVIDENCE_READY', query_id=pack['query_id'],
                      evidence_pack=pack, retrieval_backend=pack['retrieval_backend'])
        answer = await complete_retrieval(question, result, provider=provider, limits=limits, budget=budget)
        if (answer.get('answering') or {}).get('status') == 'DRAFT_READY':
            anchor_graph_time(answer['answering'])
            caution = 'Thông tin theo tài liệu được dẫn; chưa xác nhận chức vụ hiện tại hoặc toàn bộ nhân sự.'
            answer['answering']['draft'] += '\n\n' + caution
            answer['answering']['cautions'].append(caution)
        return answer
