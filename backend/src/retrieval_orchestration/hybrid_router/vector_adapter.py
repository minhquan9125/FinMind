"""WBS10 bridge to the existing read-only Vector/BM25 retriever.

No source ingestion, chunking, embedding rebuild or answer generation here.
execute runs in the router worker, retrieval runs on the application's loop.
"""
import asyncio,copy,uuid,re
from .adapters import AdapterResult
from ...b1_answering.evidence.citations import prepare_evidence,CitationError

SOURCE_TYPES={'annual_reports':'BCTN','financial_reports':'BCTC','news_articles':'NEWS','companies':'COMPANY_PROFILE'}
DOC_TYPES={'BCTN':'ANNUAL_REPORT','BCTC':'FINANCIAL_STATEMENT','NEWS':'NEWS','COMPANY_PROFILE':'COMPANY_PROFILE'}

class VectorRAGAdapter:
    def __init__(self,search,event_loop,*,corpus_version_id,timeout=30,top_k=5):
        self.search,self.loop=search,event_loop
        self.corpus_id=str(uuid.UUID(corpus_version_id))
        self.timeout,self.top_k=timeout,top_k
        self.calls=[]

    def failure(self,task,status,code):
        return AdapterResult(task.id,'CONTENT',status,code,provenance='LIVE/VECTOR')

    def execute(self,task,*,dependency=None):
        if task.adapter not in ('CONTENT','VECTOR'):raise ValueError('Content task required')
        self.calls.append(dict(task_id=task.id,operation=task.operation))
        if dependency is not None and dependency.status!='OK':
            return self.failure(task,'INSUFFICIENT_EVIDENCE','VECTOR_DEPENDENCY_NOT_READY')
        try:
            asyncio.get_running_loop()
        except RuntimeError:pass
        else:return self.failure(task,'SYSTEM_UNAVAILABLE','VECTOR_WORKER_REQUIRED')
        future=None
        try:
            if self.loop.is_closed() or not self.loop.is_running():return self.failure(task,'SYSTEM_UNAVAILABLE','VECTOR_LOOP_UNAVAILABLE')
            future=asyncio.run_coroutine_threadsafe(self.retrieve(task,dependency),self.loop)
            return future.result(timeout=self.timeout)
        except TimeoutError:
            if future is not None:future.cancel()
            return self.failure(task,'SYSTEM_UNAVAILABLE','VECTOR_TIMEOUT')
        except Exception as exc:
            code=getattr(exc,'code','VECTOR_SEARCH_UNAVAILABLE')
            integrity={'INVALID_EVIDENCE','HASH_MISMATCH','SOURCE_CHANGED','SOURCE_MISSING','INVALID_LOCATOR','SOURCE_UNAVAILABLE','VECTOR_VERSION_MISMATCH','VECTOR_SCOPE_MISMATCH','VECTOR_SOURCE_UNSUPPORTED'}
            known=integrity|{'CACHE_BUILD_REQUIRED','CACHE_EXPIRED','CACHE_STALE','CACHE_VERSION_MISMATCH','CACHE_CHECKSUM_MISMATCH','INVALID_CACHE','INDEX_NOT_FOUND','INDEX_NOT_ACTIVE','CORPUS_NOT_READY','CORPUS_INDEX_MISMATCH','VECTOR_SCOPE_REQUIRED','VECTOR_SCOPE_LIMIT','VECTOR_UNSUPPORTED_PERIOD','VECTOR_DEPENDENCY_SCOPE_UNRESOLVED'}
            return self.failure(task,'INSUFFICIENT_EVIDENCE' if code in integrity else 'SYSTEM_UNAVAILABLE',code if code in known else 'VECTOR_SEARCH_UNAVAILABLE')

    async def retrieve(self,task,dependency=None):
        scope=copy.deepcopy(task.params)
        if scope.get('corpus_version_id') not in (None,self.corpus_id):raise CitationError('VECTOR_VERSION_MISMATCH')
        companies=list(dict.fromkeys(scope.get('companies') or []))
        if dependency is not None:
            companies=list(dict.fromkeys(row.get('ticker') or row.get('symbol') or row.get('company') for row in dependency.data))
            if not companies or any(not c for c in companies):raise CitationError('VECTOR_DEPENDENCY_SCOPE_UNRESOLVED')
        periods=list(dict.fromkeys(scope.get('periods') or [])) or [None]
        if any(p is not None and not re.fullmatch(r'\d{4}(?:-Q[1-4]|-\d{2}(?:-\d{2})?)?',p) for p in periods):raise CitationError('VECTOR_UNSUPPORTED_PERIOD')
        if len(companies)>4 or len(periods)>4 or max(1,len(companies))*len(periods)>6:raise CitationError('VECTOR_SCOPE_LIMIT')
        source=scope.get('source_type')
        if source and source not in DOC_TYPES:raise CitationError('VECTOR_SOURCE_UNSUPPORTED')
        if not companies and not scope.get('topic'):raise CitationError('VECTOR_SCOPE_REQUIRED')
        question=scope.get('retrieval_question') or scope.get('question')
        items={};data={};index_id=None;missing=[]
        for company in companies or [None]:
            for period in periods:
                response=await self.search(question,company=company,period=period,doc_type=DOC_TYPES.get(source),top_k=self.top_k)
                if response.get('corpus_version_id')!=self.corpus_id or response.get('scope_mode')!='CORPUS' or response.get('index_status')!='ACTIVE':raise CitationError('VECTOR_VERSION_MISMATCH')
                current=str(uuid.UUID(response['index_version_id']))
                if (index_id and current!=index_id) or scope.get('index_version_id') not in (None,current):raise CitationError('VECTOR_VERSION_MISMATCH')
                index_id=current
                expected=dict(company=company,period=period,doc_type=DOC_TYPES.get(source))
                if any(response.get('scope',{}).get(k)!=v for k,v in expected.items()):raise CitationError('VECTOR_SCOPE_MISMATCH')
                hits=response.get('results') or []
                if not hits:missing.append(dict(company=company,period=period))
                for hit in hits:
                    loc=hit['locator'];kind=SOURCE_TYPES.get(loc.get('source_table'))
                    if not kind or source and kind!=source:raise CitationError('VECTOR_SCOPE_MISMATCH')
                    item=dict(evidence_id=hit['chunk_id'],chunk_id=hit['chunk_id'],source_id=hit['document_id'],
                        source_type=kind,title=hit['title'],passage=hit['text'],source_sha256=hit['source_sha256'],
                        content_sha256=hit['content_hash'],locator=copy.deepcopy(loc),source_verified=True,
                        score=dict(type='RRF',value=hit['rrf_score']))
                    if hit.get('source_url') or loc.get('url'):item['source_url']=hit.get('source_url') or loc['url']
                    prior=items.get(hit['chunk_id'])
                    if prior:
                        if {k:v for k,v in prior.items() if k!='score'}!={k:v for k,v in item.items() if k!='score'}:raise CitationError('SOURCE_CHANGED')
                        continue
                    items[hit['chunk_id']]=item
                    data[hit['chunk_id']]=copy.deepcopy(hit)
        if missing:
            return self.failure(task,'INSUFFICIENT_EVIDENCE' if items else 'NO_DATA','VECTOR_PARTIAL_COVERAGE' if items else 'VECTOR_NO_RESULTS')
        pack=dict(schema_version='1.1',query_id=str(uuid.uuid4()),corpus_version_id=self.corpus_id,
            data_version=dict(kind='INDEX',id=index_id),items=list(items.values()),retrieval_backend='hybrid')
        prepare_evidence(pack)
        return AdapterResult(task.id,'CONTENT','OK','VECTOR_EVIDENCE_READY',evidence=tuple(items.values()),
            data=tuple(data.values()),
            provenance='LIVE/VECTOR',evidence_pack=pack)
