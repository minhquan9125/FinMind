"""Answer explicit article questions from approved, ACTIVE admin News indices."""
import asyncio
import re
import uuid
import time

from .admin_ingestion import Queue


class TimedProvider:
    def __init__(self, delegate, limits, timeout):
        self.delegate, self.limits, self.timeout = delegate, limits, timeout

    async def _call(self, method, request):
        from ..b1_answering.providers.gemini import GeminiError
        try:
            return await asyncio.wait_for(method(request), self.timeout)
        except TimeoutError:
            raise GeminiError('GEMINI_TIMEOUT') from None

    async def count_tokens(self, request):
        return await self._call(self.delegate.count_tokens, request)

    async def generate(self, request):
        return await self._call(self.delegate.generate, request)


class AdminNewsChat:
    def __init__(self, pool, embedder, settings, *, retriever=None):
        self.pool, self.embedder, self.settings = pool, embedder, settings
        self.retrievers = {}
        self.shared_retriever = retriever

    def select(self, question, refs=None):
        # Financial questions without an explicit article reference keep their BCTC route.
        if not re.search(r'\b(bài|tin|news|pdf|giải trình|công bố)\b', question, re.I): return None
        matches = []
        words = set(re.findall(r'\w+', question.lower()))
        if refs is None: refs=Queue(self.settings.admin_ingestion_directory).published_article_refs()
        for ref in refs:
            symbols = ref['symbols']
            matched = [s for s in symbols if re.search(r'\b'+re.escape(s)+r'\b', question, re.I)]
            linked = bool(ref['url'] and ref['url'] in question)
            if not matched and linked: matched = symbols[:1]
            if matched:
                score = len(words & set(re.findall(r'\w+', (ref['title'] or '').lower()))) + 1000*linked
                matches.append((score, matched[0], ref['url']))
        if matches:
            _, symbol, url = max(matches,key=lambda x:x[0])
            return symbol, url
        return None

    async def answer(self, question, session_id, *, provider, limits, budget):
        started = time.perf_counter()
        if not re.search(r'\b(bài|tin|news|pdf|giải trình|công bố)\b',question,re.I): return None
        corpus = Queue(self.settings.admin_ingestion_directory).serving_corpus(self.settings.research_corpus_version_id)
        # The serving DB corpus is authoritative, including on a fresh checkout
        # whose local crawl/review history is empty.
        async with self.pool.acquire() as conn:
            rows=await conn.fetch('''SELECT DISTINCT d.document_id::text AS id,d.title,
                t.locator_json->>'url' AS url,coalesce(c.symbol,t.locator_json->>'symbol') AS symbol
                FROM public.corpus_versions cv JOIN public.index_versions iv USING(index_version_id)
                JOIN public.corpus_documents cd USING(corpus_version_id)
                JOIN public.documents d USING(document_id)
                JOIN public.text_chunks t ON t.document_id=d.document_id AND t.index_version_id=iv.index_version_id
                LEFT JOIN public.companies c ON c.company_id=d.company_id
                WHERE cv.corpus_version_id=$1::uuid AND cv.status='FROZEN' AND iv.status='ACTIVE'
                  AND cd.document_hash=d.sha256 AND d.doc_type='NEWS' AND t.superseded_at IS NULL
                  AND t.locator_json ? 'admin_news_snapshot' ''',uuid.UUID(corpus))
        refs=[dict(row,symbols=[row['symbol']] if row['symbol'] else []) for row in rows]
        selected = self.select(question,refs)
        if not selected: return None
        from ..retrieval_orchestration.live_research import DenseEvidenceRetriever
        from ..b1_answering.application.service import complete_retrieval
        symbol, source_url = selected
        if corpus not in self.retrievers:
            if len(self.retrievers) >= 10: self.retrievers.pop(next(iter(self.retrievers)))
            self.retrievers[corpus] = DenseEvidenceRetriever(self.pool, self.embedder,
                corpus_version_id=corpus, model_ref=self.settings.embedding_model_ref,
                backend=self.settings.research_retrieval_backend)
        # A News publication can compare several reporting years; those years are
        # not publication-date filters. Keep them in the question and source checks.
        scope = {'companies':[symbol], 'periods':['LATEST_AVAILABLE_PERIOD'],
                 'source_type':'NEWS', '_allow_source_extract':True,
                 '_admin_source_url':source_url,
                 '_market_request':{'action':'DETAIL'}, '_admin_news_corpus':corpus}
        result = {'request_id':str(uuid.uuid4()),'execution_mode':'LIVE','b1_decision':'SEARCH',
                  'scope':scope,'status':'NO_DATA','reason_code':'NO_DATA',
                  'message':'Không tìm thấy nội dung phù hợp trong bài đã xử lý.',
                  'evidence_pack':None,'errors':[],'clarification':None,'clarification_options':[]}
        try:
            retriever = self.shared_retriever or self.retrievers[corpus]
            pack = await asyncio.wait_for(retriever.retrieve(question,scope),
                                          self.settings.research_retrieval_timeout_seconds)
        except Exception:
            result.update(status='SYSTEM_UNAVAILABLE',reason_code='ADMIN_NEWS_RETRIEVAL_UNAVAILABLE',
                          message='Chưa đọc lại được dữ liệu bài đã xử lý. Vui lòng thử lại.')
            return result
        if not pack['items']: return result
        result.update(status='EVIDENCE_READY', reason_code='EVIDENCE_READY', evidence_pack=pack,
                      query_id=pack['query_id'],retrieval_backend=pack.get('retrieval_backend'),
                      message='Đã tìm thấy nguồn đã duyệt trong dữ liệu tìm kiếm chung.')
        retrieved = time.perf_counter()
        result['timings'] = {'retrieval_seconds':round(retrieved-started,3)}
        bounded = TimedProvider(provider,limits,self.settings.admin_news_generation_timeout_seconds) if provider else None
        result = await complete_retrieval(question,result,provider=bounded,limits=limits,budget=budget)
        result['timings'].update(answer_seconds=round(time.perf_counter()-retrieved,3),
                                 total_seconds=round(time.perf_counter()-started,3))
        return result
