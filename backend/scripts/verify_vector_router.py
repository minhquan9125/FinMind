"""Read-only WBS10/WBS13 acceptance: real router -> existing hybrid -> B1 evidence.

    No Gemini, database writes, chunking or document embedding generation job.
"""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TRANSFORMERS_OFFLINE','1')
import asyncio,json,time
from person_role_db import ROOT
from src.core.db import connect,disconnect
from src.api.routers.hybrid_router import get_router_engine,_build_live_content_adapter
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine,SessionScope
from src.core.config import get_settings
from src.b1_answering.evidence.citations import prepare_evidence,validate_draft

class NoGraph:
    calls=[]
    def execute(self,*args,**kwargs):raise AssertionError('VECTOR must not call graph')

async def main():
    await connect()
    try:
        settings=get_settings();loop=asyncio.get_running_loop();start=time.monotonic()
        adapter=await asyncio.to_thread(_build_live_content_adapter,loop)
        if adapter is None:raise RuntimeError('VECTOR_ADAPTER_NOT_READY')
        print('Preparing existing lexical cache; no chunk/vector rebuild.',flush=True)
        cache=await asyncio.wait_for(adapter.warmup(),600)
        print(json.dumps(cache),flush=True)
        base=await asyncio.to_thread(get_router_engine)
        engine=DecisionEngine(base.predictor,threshold=base.threshold,content_adapter=adapter,graph_adapter=NoGraph())
        question='Tóm tắt chiến lược kinh doanh FPT năm 2025.'
        context=SessionScope(source_type='BCTN',corpus_version_id=settings.research_corpus_version_id)
        result=await asyncio.to_thread(engine.run,question,context=context)
        report=dict(question=question,route=result.decision.route,status=result.status,reason_code=result.reason_code,
            execution_mode=result.execution_mode,scope=result.decision.scope.model_dump(),seconds=round(time.monotonic()-start,2),
            graph_calls=len(engine.graph_adapter.calls),adapter_results=[r.to_dict() for r in result.adapter_results],database_writes=0)
        if result.status!='OK':
            import traceback
            try:await adapter.retrieve(result.decision.tasks[0])
            except Exception as exc:
                report['diagnostic']=dict(type=type(exc).__name__,code=getattr(exc,'code',None),
                    frames=[dict(file=f.name,line=f.lineno) for f in traceback.extract_tb(exc.__traceback__)])
        if result.status=='OK':
            evidence=prepare_evidence(result.adapter_results[0].evidence_pack)
            first=next(iter(evidence.values()))
            proof=validate_draft(dict(claims=[dict(text=first['passage'],evidence_ids=[first['evidence_id']])]),evidence)
            report['b1_citation_binding']='PASS' if proof['citations'] else 'FAIL'
        out=ROOT/'outputs/vector-router-wbs10-20261104';out.mkdir(exist_ok=True)
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='adapter_results'},ensure_ascii=False),flush=True)
        assert result.decision.route=='VECTOR' and result.status=='OK'
        assert report['graph_calls']==0 and report['b1_citation_binding']=='PASS'
    finally:await disconnect()

if __name__=='__main__':asyncio.run(main())
