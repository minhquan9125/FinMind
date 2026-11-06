"""Isolated backend probes for shared Excel edge cases. Never certifies UI E2E.

No database/network calls, model downloads, product patches or invented answers.
Classifier scores are fixtures; policy/scope/workflow code is the real module.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
from threading import Thread
from time import perf_counter, sleep
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from backend.scripts.wbs17_workbook import load_workbook_suite
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine, ScopeResolver, SessionScope
from src.retrieval_orchestration.hybrid_router.adapters import AdapterResult, LiveContentAdapter, LiveGraphAdapter
from src.retrieval_orchestration.hybrid_router.schemas import RouterTask

CASES=('TC_EDGE_01','TC_EDGE_03','TC_EDGE_04','TC_EDGE_05','TC_EDGE_14',
       'TC_EDGE_15','TC_EDGE_16','TC_EDGE_20','TC_EDGE_21','TC_EDGE_22')


class Predictor:
    model_version='WBS17-FIXTURE-SCORES-NOT-CLASSIFIER-EVALUATION'
    def __init__(self):self.calls=0
    def predict(self, question):
        self.calls+=1
        return .95,.1  # Does not fix a route_hint chosen by the real policy.


class FixtureAdapter:
    def __init__(self,kind,status='NO_DATA'):
        self.kind,self.status,self.calls=kind,status,[]
    def execute(self,task,*,dependency=None):
        self.calls.append({'task_id':task.id,'dependency':dependency.task_id if dependency else None})
        return AdapterResult(task.id,self.kind,self.status,'CONTROLLED_FIXTURE_'+self.status,
             data=({'company_id':'fixture:child','name':'fixture company'},) if self.status=='OK' else (),
             provenance='MOCK/FIXTURE')


def engine(registry=None,graph=None,content=None):
    return DecisionEngine(Predictor(),resolver=ScopeResolver(registry),
      graph_adapter=graph or FixtureAdapter('GRAPH'),content_adapter=content or FixtureAdapter('CONTENT'))


def probe(c,company_ids):
    cid,q=c['case_id'],c['question']
    e=engine(); expected=c['expected']; details={}; checks={}
    if cid=='TC_EDGE_01':
        e=engine({'test_trung_ten':company_ids})
        details['alias_fixture_company_ids']=company_ids
    if cid in {'TC_EDGE_01','TC_EDGE_03','TC_EDGE_20'}:
        r=e.run(q)
        checks={'asks_clarification':r.decision.decision=='ASK_CLARIFICATION',
          'clarify_route':r.decision.route=='CLARIFY','classifier_not_called':e.predictor.calls==0,
          'no_adapters':not e.graph_adapter.calls and not e.content_adapter.calls}
    elif cid in {'TC_EDGE_04','TC_EDGE_05','TC_EDGE_16'}:
        r=e.run(q)
        checks={'route':r.decision.route==expected['route'],'empty_is_not_a_fact':r.status=='NO_DATA',
          'no_content_after_empty_graph':not e.content_adapter.calls,
          'no_facts':all(not a.data and not a.evidence for a in r.adapter_results)}
        if cid=='TC_EDGE_05':checks['year_1900_preserved']=r.decision.scope.periods==['1900']
    elif cid in {'TC_EDGE_14','TC_EDGE_15'}:
        # End-to-end planning check stays separate from a forced component task.
        r=e.run(q,context=SessionScope(companies=('FPT',),periods=('2024',),confirmed=True))
        checks['both_plan']=r.decision.route=='BOTH'
        if cid=='TC_EDGE_14':
            class TimedQuery:
                def query(self,*args,**kwargs):
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        return pool.submit(lambda:(sleep(.25),[])[1]).result(timeout=.05)
            a=LiveGraphAdapter(SimpleNamespace(),TimedQuery(),('fixture:version',),{'FPT':'fixture:root'},lambda p:())
            t=RouterTask(id='g1',adapter='GRAPH',operation='find_relationships',
                        params={'companies':['FPT'],'periods':['2024']})
            start=perf_counter(); actual=a.execute(t); elapsed=perf_counter()-start
            details['injected_boundary']={'timeout_seconds':.05,'delay_seconds':.25,'elapsed_seconds':elapsed,
              'adapter_status':actual.status,'reason_code':actual.reason_code,
              'note':'Isolated query future timeout; not a Neo4j driver/network timeout test.'}
            checks['graph_timeout_component']=actual.status=='SYSTEM_UNAVAILABLE' and actual.reason_code=='GRAPH_TIMEOUT'
            checks['timeout_threshold_crossed']=elapsed>=.05
            checks['no_facts_on_timeout']=not actual.data and not actual.evidence
        else:
            loop=asyncio.new_event_loop(); thread=Thread(target=loop.run_forever,daemon=True);thread.start()
            async def delayed(*args):
                await asyncio.sleep(.25);return {'results':[]}
            a=LiveContentAdapter(delayed,loop);a.TIMEOUT_SECONDS=.05
            task=RouterTask(id='v1',adapter='CONTENT',operation='find_metric',params={'question':q,'periods':['2024']})
            dep=AdapterResult('g1','GRAPH','OK','CONTROLLED_FIXTURE_OK',
                              data=({'company_id':'fixture:child'},),provenance='MOCK/FIXTURE')
            start=perf_counter();actual=a.execute(task,dependency=dep);elapsed=perf_counter()-start
            # Let the bounded fixture coroutine finish before closing its own loop.
            asyncio.run_coroutine_threadsafe(asyncio.sleep(.26),loop).result(timeout=1)
            loop.call_soon_threadsafe(loop.stop);thread.join(timeout=1);loop.close()
            details['injected_boundary']={'timeout_seconds':.05,'delay_seconds':.25,'elapsed_seconds':elapsed,
              'adapter_status':actual.status,'reason_code':actual.reason_code,'company_sent':a.calls[-1]['company']}
            checks['content_timeout_component']=actual.status=='SYSTEM_UNAVAILABLE' and actual.reason_code=='CONTENT_TIMEOUT'
            checks['dependency_company_used']=a.calls[-1]['company']=='fixture:child'
            checks['no_fabricated_content']=not actual.data and not actual.evidence
    else:
        r=e.run(q)
        checks['route']=r.decision.route==expected['route']
        if cid=='TC_EDGE_21':
            checks['both_quarters_preserved']=r.decision.scope.periods==['2025-Q1','2025-Q2']
            details['limit']='Scope/plan only; annual-versus-quarter evidence abstention not exercised.'
        if cid=='TC_EDGE_22':
            checks['full_day_preserved']=any('2026-11-04' in str(t.params.get(k))
                 for t in r.decision.tasks for k in ('periods','date','day','trade_date','period'))
            details['raw_question_keeps_day']='04/11/2026' in q
            details['limit']='Does not test the separate price SQL endpoint; checks explicit structured day binding.'
    details['decision']=r.decision.model_dump()
    details['status']=r.status
    details['reason_code']=r.reason_code
    details['calls']={'classifier':e.predictor.calls,'graph':e.graph_adapter.calls,'content':e.content_adapter.calls}
    verdict='PASS_BACKEND' if all(checks.values()) else 'FAIL_BACKEND'
    if cid=='TC_EDGE_22' and not checks['full_day_preserved']:
        verdict='FOLLOWUP_REQUIRED'
    return {'case_id':cid,'question':q,'level':'BACKEND_COMPONENT_ONLY','fixture':True,
      'provenance':'CONTROLLED_FIXTURE_NOT_LIVE','checks':checks,
      'backend_verdict':verdict,
      'full_case_acceptance':'NOT_EVALUATED_ANSWER_AND_UI','details':details}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();suite=load_workbook_suite(args.workbook)
    args.output.mkdir(parents=True,exist_ok=False)
    selected=[c for c in suite['cases'] if c['case_id'] in CASES]
    assert len(selected)==len(CASES)
    ref=next(c for c in suite['cases'] if c['case_id']=='TC_GRAPH_01')['expected']['relations'][0]
    company_ids=(ref['subject_id'],ref['object_id'])
    rows=[]
    for c in selected:
        for repeat in range(5):
            r=probe(c,company_ids);r['repeat']=repeat;rows.append(r)
    (args.output/'results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),'utf-8')
    summary={'level':'BACKEND_COMPONENT_ONLY','full_e2e':'NOT_RUN','cases':len(selected),'repeats':5,
      'by_case':{c['case_id']:{'verdicts':dict(Counter(r['backend_verdict'] for r in rows if r['case_id']==c['case_id'])),
        'failed_checks':sorted({k for r in rows if r['case_id']==c['case_id'] for k,v in r['checks'].items() if not v}),
        'sample':next(r for r in rows if r['case_id']==c['case_id'])} for c in selected},
      'workbook_sha256':suite['workbook_sha256'],
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'note':'Fixed predictor fixture: policy/scope/workflow checks, not trained classifier accuracy or E2E.'}
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:{'verdicts':v['verdicts'],'failed_checks':v['failed_checks']} for k,v in summary['by_case'].items()}))


if __name__=='__main__':main()
