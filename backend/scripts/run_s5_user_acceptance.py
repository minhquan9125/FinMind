"""Execute frozen external-user routing scenarios against 07.2, without changing gold.

Real pinned BGE-M3 and installed IntentClassifier. Controlled provider responses and
recording data adapters; this measures routing/clarification, not factual answers.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
ORACLE=ROOT/'docs/sprint5/user-acceptance-073-v1/scenarios.jsonl'
FROZEN_SHA='b9fc8f2eaf509bfb8309b9f64d37f6712532e32c42eb3e11fb23d9b373fbc3e6'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases():
    if sha(ORACLE)!=FROZEN_SHA: raise ValueError('Frozen business expectations changed')
    rows=[json.loads(line) for line in ORACLE.read_text(encoding='utf-8').splitlines() if line.strip()]
    if {r['id'] for r in rows}!={f'USER-{i:03d}' for i in range(1,33)} or len(rows)!=32:
        raise ValueError('Incomplete independent scenario set')
    return rows


def judge(case,observed):
    errors=[]
    expected=set(case['expected_objectives']); behavior=case['expected_behavior']
    if observed.get('exception'): errors.append('Execution error: '+observed['exception'])
    if behavior=='SERVE':
        if not observed['dispatch_calls']: errors.append('No retrieval/market dispatch for user request')
        corpus_retains_question=any('query' in d and case['question'] in d['query'] for d in observed.get('dispatches',[]))
        if not expected<=set(observed['dispatch_objectives']) and not (len(expected)>1 and corpus_retains_question):
            errors.append('Dispatched objectives do not preserve all requested objectives')
    elif behavior=='ASK':
        if (observed['status'] not in {'ASK_CLARIFICATION','CLARIFICATION_STALLED'}
                or not observed.get('clarification') or observed['dispatch_calls']):
            errors.append('Expected clarification message and no retrieval')
    elif behavior=='REFUSE':
        if observed['status']!='UNSUPPORTED' or observed['dispatch_calls']:
            errors.append('Expected refusal before retrieval')
    elif behavior=='GREETING':
        if observed['status']!='GREETING' or observed['dispatch_calls']:
            errors.append('Expected greeting without retrieval')
    # Scope matters for an actionable request or the next clarification turn.
    if behavior in {'SERVE','ASK'}:
        if case['required_company'] and observed['companies']!=[case['required_company']]:
            errors.append('Required company not preserved')
        if case['required_period'] and case['required_period'] not in observed['periods']:
            errors.append('Required period not preserved')
    if case['fallback_expectation']=='NEVER' and observed['fallback_calls']:
        errors.append('Clear user request called classification AI')
    reached=case['provider_scenario']=='NORMAL' or observed['injected_scenario_reached']
    status='PASS' if not errors else 'FAIL'
    return dict(status=status,passed=status=='PASS',baseline_status='FAIL' if errors else 'PASS',
        injection_exercised=reached,mismatches=errors,
        injection_status='NOT_APPLICABLE' if case['provider_scenario']=='NORMAL' else 'EXERCISED' if reached else 'NOT_EXERCISED',
        classifier_matches_gold=set(observed['classification_objectives'])==expected,
        full_user_answer_verified=False,manual_review_required=True,
        multi_objective_content_verified=False if len(expected)>1 else None)


def dispatch_objectives(scope):
    source=scope.get('source_type')
    if source=='PRICE': return ['PRICE']
    if source=='MARKET_ANALYSIS': return ['ANALYSIS']
    if source=='COMPANY_PROFILE': return ['COMPANY_OVERVIEW']
    if source=='BCTN': return ['REPORT_CONTENT']
    if scope.get('metric_code'): return ['NUMERIC']
    if source=='NEWS' and scope.get('topic')=='RELATIONSHIP_LOOKUP':
        return ['PERSON_ROLE','ENTITY_RELATION']  # shared retrieval target, classifier is checked separately
    if source=='NEWS': return ['NEWS']
    return []


class RecordingRetriever:
    def __init__(self): self.calls=[]
    async def retrieve(self,query,scope):
        self.calls.append(dict(query=query,scope=deepcopy(scope)))
        return dict(query_id='user-test-no-facts',items=[])


class RecordingMarket:
    def __init__(self): self.calls=[]
    async def lookup(self,scope,**kwargs):
        self.calls.append(dict(scope=deepcopy(scope)))
        return dict(status='NO_DATA',reason_code='TEST_ADAPTER_NO_FACTS',message='Recording adapter: no factual answer supplied.',evidence_pack=None)


class ControlledProvider:
    def __init__(self,case): self.case=case; self.calls=[]; self.cancelled=False
    async def count_tokens(self,request): return 100
    async def generate(self,request):
        import asyncio
        from src.b1_answering.providers.gemini import GeminiError
        wire=json.loads(request['contents'][0]['parts'][0]['text'])
        self.calls.append(wire)
        scenario=self.case['provider_scenario']
        if scenario=='TIMEOUT':
            try: await asyncio.sleep(1)
            except asyncio.CancelledError: self.cancelled=True; raise
        if scenario=='UNAVAILABLE': raise GeminiError('GEMINI_UNAVAILABLE')
        code={'PRICE':'GIA','NUMERIC':'SO_LIEU','ANALYSIS':'PHAN_TICH','NEWS':'NEWS',
            'REPORT_CONTENT':'BCTC_BCTN','PERSON_ROLE':'CHUC_VU','ENTITY_RELATION':'QUAN_HE',
            'COMPANY_OVERVIEW':'TONG_QUAN','REFUSE':'NGOAI_PHAM_VI','ASK':'CLARIFY','GREETING':'HOI_THOAI'}
        objectives=self.case['expected_objectives']
        # This is an explicit controlled correct-response fixture, not a claim that Gemini inferred gold.
        label='KET_HOP' if len(objectives)>1 else code[objectives[0]]
        label={'WRONG_PRICE':'GIA','WRONG_NEWS':'NEWS','UNKNOWN_LABEL':'NOT_A_LABEL'}.get(scenario,label)
        reply=dict(intent_label=label,confidence=.2 if scenario=='LOW_CONFIDENCE' else .9,
            reason='Controlled user-test provider response',extracted_company=None)
        return dict(payload=reply,usage=dict(input_tokens=100,output_tokens=20,total_tokens=120))


async def execute_case(case,classifier):
    from src.retrieval_orchestration.live_research import LiveResearchService
    from src.retrieval_orchestration import intent_gate_v2 as gate
    retriever,market,provider=RecordingRetriever(),RecordingMarket(),ControlledProvider(case)
    classifications=[]
    def classify(question,context=None):
        result=classifier.classify(question,context=context)
        classifications.append(deepcopy(result))
        return result
    class ProbeService(LiveResearchService):
        async def _missing_companies(self,companies): return [],[]
        async def _absent_from_corpus(self,scope): return [],[]
    service=ProbeService(retriever,provider=provider,market=market,intent_classifier=classify)
    # Deadline override only for injected timeouts. Production default remains eight seconds.
    original=gate.ask_fallback
    async def injected_deadline(*args,**kwargs): return await original(*args,**kwargs,timeout=.02)
    context=None; previous=None; prior_observation=None
    if case['prior_user_context']:
        prior_case=dict(case,provider_scenario='NORMAL')
        prior_provider=ControlledProvider(prior_case)
        service.provider=prior_provider
        previous=await service.answer(case['prior_user_context'],'external-user-test',today=date(2026,11,16))
        context=deepcopy(previous.get('scope') or {})
        prior_observation=dict(question=case['prior_user_context'],scope=context,status=previous.get('status'),
            clarification=previous.get('clarification'),provider_calls=len(prior_provider.calls))
        service.provider=provider
        retriever.calls.clear(); market.calls.clear(); classifications.clear()
    if case['provider_scenario']=='TIMEOUT': gate.ask_fallback=injected_deadline
    result={}; error=None
    started=time.perf_counter()
    try:
        result=await service.answer(case['question'],'external-user-test',context,previous_result=previous,today=date(2026,11,16))
    except Exception as exc: error=f'{type(exc).__name__}: {exc}'
    finally: gate.ask_fallback=original
    dispatches=retriever.calls+market.calls
    scopes=[call['scope'] for call in dispatches]
    final_scope=result.get('scope') or {}
    companies=list(final_scope.get('companies') or [])
    periods=list(final_scope.get('periods') or [])
    for scope in scopes:
        companies=list(dict.fromkeys(companies+list(scope.get('companies') or [])))
        periods=list(dict.fromkeys(periods+list(scope.get('periods') or [])))
    if final_scope.get('_pending_year') is not None: periods.append(str(final_scope['_pending_year']))
    resolution=classifications[-1]['resolution'] if classifications else {}
    objectives=resolution.get('component_labels',[]) if resolution.get('intent_label')=='MIXED' else [resolution['intent_label']] if resolution else []
    observation=dict(status=result.get('status'),classification_objectives=objectives,
        dispatch_objectives=sorted({kind for scope in scopes for kind in dispatch_objectives(scope)}),
        companies=companies,periods=periods,fallback_calls=len(provider.calls),dispatch_calls=len(dispatches),
        clarification=result.get('clarification'),exception=error,
        injected_scenario_reached=bool(provider.calls) and case['provider_scenario']!='NORMAL',
        provider_cancelled=provider.cancelled,prior_turn=prior_observation,
        intent_trace=result.get('intent'),scope=final_scope,dispatches=dispatches,
        classifier_resolution=resolution,provider_requests=provider.calls,
        test_elapsed_seconds=time.perf_counter()-started,result_message=result.get('message'))
    return dict(case=case,observed=observation,verdict=judge(case,observation))


def cell(value):
    if isinstance(value,(dict,list)): value=json.dumps(value,ensure_ascii=False)
    return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value


def apply_response_review(row,review):
    row['external_response_review']=deepcopy(review)
    if review.get('response_relevance')=='FAIL':
        row['verdict']['mismatches'].append('External user review: '+review['rationale'])
        row['verdict'].update(status='FAIL',passed=False,baseline_status='FAIL')
    # A relevance review cannot establish numeric/citation correctness without actual evidence.
    row['verdict']['full_user_answer_verified']=False
    return row


def workbook(path,rows,method):
    from openpyxl import Workbook,load_workbook
    from openpyxl.styles import Alignment,Font,PatternFill
    book=Workbook();book.remove(book.active)
    counts=Counter(r['verdict']['status'] for r in rows)
    def sheet(name,headers,values,widths):
        ws=book.create_sheet(name);ws.append(headers);ws.freeze_panes='C2' if len(headers)>4 else 'A2'
        for row in values: ws.append([cell(v) for v in row])
        ws.auto_filter.ref=ws.dimensions
        for c in ws[1]: c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='155E75');c.alignment=Alignment(wrap_text=True)
        from openpyxl.utils import get_column_letter
        for i,width in enumerate(widths,1): ws.column_dimensions[get_column_letter(i)].width=width
        for row in ws.iter_rows(min_row=2):
            ws.row_dimensions[row[0].row].height=76
            for c in row:
                c.alignment=Alignment(wrap_text=True,vertical='top')
                if c.value in {'PASS','FAIL','NOT_EXERCISED'}: c.font=Font(bold=True,color={'PASS':'166534','FAIL':'991B1B','NOT_EXERCISED':'92400E'}[c.value])
    sheet('Tong_quan',['Mục','Giá trị','Diễn giải'],[
        ['Kỳ vọng','32 câu nghiệp vụ soạn độc lập','Agent soạn không xem source/test/report; gold khóa trước chạy'],
        ['PASS tại biên định tuyến',counts['PASS'],'Không phải chứng minh trả lời đầy đủ/số liệu/citation đúng'],
        ['FAIL tại biên định tuyến',counts['FAIL'],'Giữ nguyên kỳ vọng, không chỉnh gold theo output'],
        ['Tình huống lỗi chưa tới',sum(r['verdict']['injection_status']=='NOT_EXERCISED' for r in rows),'Tách khỏi PASS/FAIL nghiệp vụ; vẫn giữ lỗi hành vi nếu có'],
        ['BGE-M3','Inference thật từ cache','Không ép top-1 bằng encoder giả hoặc đưa gold vào classifier'],
        ['AI fallback','Response fixture kiểm soát','NORMAL mô phỏng trả đúng theo nghiệp vụ; không đo độ đúng Gemini'],
        ['Dữ liệu trả lời','Adapter chỉ ghi nhận dispatch','Không có dữ liệu thị trường/DB thật; không nghiệm thu câu trả lời cuối'],
        ['Giới hạn cấu hình','Thiếu adapter giá lịch sử / hybrid / admin-news','FAIL trong harness chưa đủ chứng minh lỗi toàn ứng dụng; cần kiểm lại trên stack được cấu hình đủ'],
        ['Lời hỏi lại','Được review độc lập sau chạy','Có ca hỏi loại nợ/vốn trong khi người dùng hỏi nhân sự/quan hệ'],
        ['must_preserve','Cần review nội dung thủ công','Chỉ tự chấm mục tiêu, mã, kỳ, hỏi lại, refusal và số lần fallback'],
    ],[38,42,120])
    headers=['ID','Nhóm','Câu hỏi','Lượt trước','Kỳ vọng hành vi','Mục tiêu yêu cầu','Mã cần giữ','Kỳ cần giữ','Fallback kỳ vọng',
        'Mô phỏng AI','Classifier thực tế','Đích dispatch thực tế','Mã thực tế','Kỳ thực tế','Status thực tế','Số gọi AI phân loại',
        'Lỗi đã tới?','Kết quả định tuyến','Sai lệch','Điều cần giữ / review tay','Nội dung đã review?']
    def values(r):
        c,o,v=r['case'],r['observed'],r['verdict']
        return [c['id'],c['group'],c['question'],c['prior_user_context'],c['expected_behavior'],c['expected_objectives'],
            c['required_company'],c['required_period'],c['fallback_expectation'],c['provider_scenario'],o['classification_objectives'],
            o['dispatch_objectives'],o['companies'],o['periods'],o['status'],o['fallback_calls'],v['injection_status'],v['status'],v['mismatches'],c['must_preserve'],r.get('external_response_review')]
    widths=[17,20,80,65,20,34,18,22,24,25,35,35,22,30,28,22,24,23,100,100,100]
    sheet('Chi_tiet',headers,[values(r) for r in rows],widths)
    sheet('Ca_FAIL',headers,[values(r) for r in rows if r['verdict']['status']=='FAIL'],widths)
    sheet('Chua_thuc_thi',headers,[values(r) for r in rows if r['verdict']['injection_status']=='NOT_EXERCISED'],widths)
    sheet('Gold_da_khoa',['ID','Lý do nghiệp vụ','Điều cần giữ'],[[r['case']['id'],r['case']['rationale'],r['case']['must_preserve']] for r in rows],[20,110,110])
    sheet('Trace',['ID','Quan sát thực thi'],[[r['case']['id'],r['observed']] for r in rows],[20,180])
    sheet('Phuong_phap',['Mục','Giá trị'],list(method.items()),[45,150])
    book.save(path)
    check=load_workbook(path)
    assert len(check.sheetnames)==7 and check['Chi_tiet'].max_row==33
    assert all(c.data_type!='f' for ws in check for row in ws for c in row)
    check.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',type=Path,help='Rejudge saved observations without another BGE run')
    parser.add_argument('--review',type=Path,help='Post-run external response relevance review')
    args=parser.parse_args();output=args.output.resolve()
    if output.exists(): raise FileExistsError('Choose new output; preserve prior evidence')
    cases=load_cases()
    if args.replay:
        rows=json.loads((args.replay/'results.json').read_text(encoding='utf-8'))
        method=json.loads((args.replay/'method.json').read_text(encoding='utf-8'))
        if [r['case'] for r in rows]!=cases or method['gold_sha256']!=FROZEN_SHA:
            raise ValueError('Replay does not match frozen oracle')
        if any(sha(ROOT/p)!=value for p,value in method['source_sha256'].items()):
            raise ValueError('Production snapshot changed since observations')
        reviews={}
        if args.review:
            content=json.loads(args.review.read_text(encoding='utf-8'))
            items=content if isinstance(content,list) else content['annotations']
            reviews={r['id']:r for r in items}
            if set(reviews)!={c['id'] for c in cases} or len(items)!=32:
                raise ValueError('Incomplete external relevance review')
        for row in rows:
            row['verdict']=judge(row['case'],row['observed'])
            if reviews: apply_response_review(row,reviews[row['case']['id']])
        method.update(rejudged_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
            reused_observations_from=str(args.replay),fresh_inference_in_this_export=False,
            review_sha256=sha(args.review) if args.review else None,
            review_method='Post-run isolated user-QA relevance review; no changes to frozen gold',
            absent_optional_adapters=['prices:PriceAnalytics','hybrid_router','admin_news'],
            environment_limit='Observed failures apply to isolated 07.2 harness. Historical-price and graph/person cases require full-stack retest before attributing a deployed-product defect.',
            exact_normalized_overlap_with_library_development=0,
            judging_notes='Unused classifier mismatch is diagnostic; broad corpus dispatch cannot establish full multi-objective answer content')
        output.mkdir(parents=True)
        summary=dict(counts=dict(Counter(r['verdict']['status'] for r in rows)),total=len(rows),
            oracle_unchanged=True,production_unchanged=True,full_user_acceptance='NOT_ESTABLISHED',
            not_exercised=[r['case']['id'] for r in rows if r['verdict']['injection_status']=='NOT_EXERCISED'],
            factual_answers_verified=0)
        for name,value in [('results.json',rows),('method.json',method),('summary.json',summary)]:
            (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        workbook(output/'S5_WBS07_3_USER_VIEW_20261116.xlsx',rows,method)
        print(json.dumps(summary,ensure_ascii=True))
        return 1 if summary['counts'].get('FAIL') or summary['not_exercised'] else 0
    from src.documents.embeddings import EmbeddingService
    from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier,DEFAULT_ARTIFACT
    production=['intent_v2_classifier.py','intent_v2_rules.py','intent_gate_v2.py','intent_routing.py','intent_fallback_contract.py','live_research.py']
    paths=[ROOT/'backend/src/retrieval_orchestration'/p for p in production]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if subprocess.check_output(['git','diff','HEAD','--',*[str(p) for p in paths]],cwd=ROOT,text=True).strip():
        raise ValueError('Production source changed')
    output.mkdir(parents=True)
    model=json.loads((DEFAULT_ARTIFACT/'library/manifest.json').read_text(encoding='utf-8'))['model']
    method=dict(gold_sha256=FROZEN_SHA,source_sha256=hashes,
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        oracle_author='Isolated AI user-QA author, no implementation/test/dataset/report access',
        independence_limit='Coordinator has seen code; this is not a human-held blind acceptance set',
        created_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),model=model,
        classifier='Real pinned BGE-M3 inference and installed artifact, no refit/no gold input',
        provider='Controlled responses only, NORMAL uses explicit gold-derived good-response fixture; not Gemini accuracy',
        data='Own recording adapters; optional hybrid router and admin-news adapters absent; no DB/market facts',
        scope='Routing/clarification at adapter boundary. Factual answer correctness and all must_preserve text unverified',
        time='2026-11-16 Asia/Saigon',production_changed=False)
    (output/'method.json').write_text(json.dumps(method,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Loading real BGE-M3; 32 frozen external-user cases',flush=True)
    encoder=EmbeddingService(model['name'],revision=model['revision'],device='cpu',batch_size=4)
    classifier=IntentClassifier.load(DEFAULT_ARTIFACT,encoder)
    classifier.classify('Warm up model before timed chat calls')
    import asyncio
    rows=[]
    for case in cases:
        row=asyncio.run(execute_case(case,classifier));rows.append(row)
        print(case['id']+' '+row['verdict']['status'],flush=True)
        (output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    assert sha(ORACLE)==FROZEN_SHA and hashes=={str(p.relative_to(ROOT)):sha(p) for p in paths}
    summary=dict(counts=dict(Counter(r['verdict']['status'] for r in rows)),total=len(rows),
        oracle_unchanged=True,production_unchanged=True,full_user_acceptance='NOT_ESTABLISHED',
        not_exercised=[r['case']['id'] for r in rows if r['verdict']['injection_status']=='NOT_EXERCISED'])
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    workbook(output/'S5_WBS07_3_USER_VIEW_20261116.xlsx',rows,method)
    print(json.dumps(summary,ensure_ascii=True),flush=True)
    return 1 if any(not r['verdict']['passed'] for r in rows) else 0

if __name__=='__main__': raise SystemExit(main())
