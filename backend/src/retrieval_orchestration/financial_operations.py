"""Bounded financial comparisons on verified rows; the model never does math."""
import copy
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP

from .retrieval_flow.intent import _fold
from .metric_vocabulary import find_metrics, point_in_time_codes, label, without_metrics
from ..b1_answering.evidence.citations import prepare_evidence, validate_draft
from ..b1_answering.evidence.grounded import source_row_fallback


def plan_operation(question, decision):
    if decision.get('decision') in ('UNSUPPORTED','RESOLVE_REFERENCE'):return None
    scope=decision['scope']
    norm=_fold(question);metrics=find_metrics(norm)
    from .hybrid_router.intent_policy import GRAPH_TERMS,contains
    remainder=without_metrics(norm)
    remainder=re.sub(r'\brieng(?: le)?(?: cua)? cong ty me\b',' ',remainder)
    if contains(remainder,GRAPH_TERMS):return None  # the hybrid router must keep the relationship part
    slot=re.fullmatch(r'(?:(?:the )?con\s+)?(?:nam\s+)?([a-z]{2,5}|\d{4})(?:\s+(?:thi sao|cung ky))?[ ?!.]*',norm)
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    continuation=bool(slot and (slot[1].isdigit() or slot[1].upper() in scope.get('companies',[])
        or set(DEFAULT_COMPANIES.get(slot[1],())).intersection(scope.get('companies',[]))))
    if not metrics and continuation and scope.get('_financial_operation'):
        metrics=list(scope.get('_metric_codes')or[])
    if not metrics:return None
    if decision.get('reason_code') in ('AMBIGUOUS_PERIOD','CONFLICTING_PERIODS','UNSUPPORTED_PERIOD'):
        # The single-period parser may stop before resolving company/entity.
        # Reuse it for the non-time slots; time is parsed explicitly below.
        from .live_research import analyze_live
        without_time=re.sub(r'\b\d{4}-q[1-4]\b|\b(?:quy|q)\s*[1-4]\s*[/ -]\s*\d{4}\b',' ',norm)
        without_time=re.sub(r'\b(?:19|20|21)\d{2}\b',' ',without_time)
        scope=analyze_live(without_time)['scope']
    if scope.get('source_type')!='BCTC' or len(scope.get('companies')or[])!=1:return None
    if scope.get('_pending_reporting_entity'):return None
    periods=list(scope.get('periods')or[])
    operation=None
    if continuation and scope.get('_financial_operation') and periods:
        operation=scope['_financial_operation']
    elif len(metrics)==1 and re.search(r'\b(?:so sanh|so voi|chenh|tang hay giam|tang|giam)\b',norm):
        pairs=[(int(y),int(q)) for q,y in re.findall(r'\b(?:quy|q)\s*([1-4])\s*[/ -]\s*((?:19|20|21)\d{2})\b',norm)]
        pairs += [(int(y),int(q)) for y,q in re.findall(r'\b((?:19|20|21)\d{2})-q([1-4])\b',norm)]
        quarters=set(re.findall(r'\b(?:quy|q)\s*([1-4])\b',norm))
        years=set(re.findall(r'\b(?:19|20|21)\d{2}\b',norm))
        if not pairs and len(years)==1 and len(quarters)==2:
            pairs=[(int(next(iter(years))),int(q))for q in quarters]
        pairs=sorted(set(pairs))
        if len(pairs)==2:periods=[f'{y}-Q{q}'for y,q in pairs]
        elif not pairs and len(years)==2:periods=sorted(years)
        else:return None
        operation='DIFFERENCE'
    elif len(metrics)==2 and set(metrics)=={'TOTAL_LIABILITIES','TOTAL_ASSETS'} and re.search(r'\b(?:tren|ty le|phan tram)\b|%',norm):
        if len(periods)!=1:return None
        metrics=['TOTAL_LIABILITIES','TOTAL_ASSETS'];operation='RATIO'
    elif 1<len(metrics)<=3 and len(periods)==1:
        operation='VALUES'
    if not operation or not all(re.fullmatch(r'\d{4}(?:-Q[1-4])?',p) for p in periods):return None
    if operation=='DIFFERENCE' and (len(periods)!=2 or len(metrics)!=1):return None
    if operation=='RATIO' and (len(periods)!=1 or len(metrics)!=2):return None
    operands=[]
    for period in periods:
        for metric in metrics:
            basis='POINT_IN_TIME' if metric in point_in_time_codes() else ('YTD' if 'luy ke' in norm else 'STANDALONE_QUARTER') if '-Q'in period else 'FULL_YEAR'
            child={key:copy.deepcopy(scope[key])for key in ('companies','reporting_entity')if key in scope}
            child.update(source_type='BCTC',metric_code=metric,periods=[period],measure_basis=basis)
            operands.append(child)
    out=copy.deepcopy(scope)
    for key in ('_pending_metric','_metric_candidates','_pending_quarter','_pending_ytd','_clarification_state'):
        out.pop(key,None)
    out.update(periods=periods,metric_code=metrics[0] if len(metrics)==1 else None,
               _metric_codes=metrics,_financial_operation=operation)
    return {'operation':operation,'operands':operands,'scope':out}


def _operand(evidence,scope):
    row=source_row_fallback(evidence,scope,reason_code='VERIFIED_ROW')
    if row is None:return None
    claim=row['claims'][0];eid=claim['evidence_ids'][0];quote=claim['support_quotes'][0]['quote']
    raw=quote.partition('):')[2].strip()
    if not raw:return None
    match=re.fullmatch(r'([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s+(triệu VND|tỷ VND|VND|triệu USD|USD)',raw,re.I)
    header=_fold(evidence[eid]['passage'].splitlines()[0])
    report_scope=re.search(r'\bpham vi:\s*([^|]+)',header)
    report_scope=report_scope[1].strip() if report_scope else ''
    entity=('CONSOLIDATED' if report_scope.startswith(('hop nhat','consolidated'))
            else 'SEPARATE' if report_scope.startswith(('rieng','separate','parent')) else None)
    return {'claim':claim,'eid':eid,'quote':quote,'raw':raw,'scope':scope,'entity':entity,
            'cautions':row.get('cautions',[]),
            'number':Decimal(match[1].replace(',','')) if match else None,
            'unit':match[2] if match else None}


def _display(value):
    return f'{value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP):,.2f}'


async def answer_operation(question,plan,retriever,budget):
    evidence={};packs=[];values=[];missing=[]
    for scope in plan['operands']:
        pack=await retriever.retrieve(question,scope)
        if packs and (pack['corpus_version_id'],pack['data_version'])!=(packs[0]['corpus_version_id'],packs[0]['data_version']):
            raise ValueError('FINANCIAL_CORPUS_CHANGED')
        packs.append(pack)
        items=prepare_evidence(pack) if pack.get('items') else {}
        for eid,item in items.items():
            if eid in evidence and ({k:v for k,v in evidence[eid].items()if k!='score'}
                    !={k:v for k,v in item.items()if k!='score'}):raise ValueError('FINANCIAL_EVIDENCE_CONFLICT')
            evidence[eid]=item
        value=_operand(items,scope)
        if value:values.append(value)
        else:missing.append(f"{label(scope['metric_code'])} ({scope['periods'][0]})")
    result=dict(execution_mode='LIVE',request_id=str(uuid.uuid4()),query_id=None,
                b1_decision='SEARCH',status='NO_DATA',reason_code='FINANCIAL_OPERANDS_MISSING',
                scope=plan['scope'],evidence_pack=None,errors=[])
    if not values:
        result['message']='Chưa tìm đủ dòng chỉ tiêu đúng kỳ và phạm vi báo cáo để đối chiếu.'
        return result
    # Bind only original rows. Arithmetic below carries its own exact operand
    # proof and does not turn a computed number into a source quotation.
    bound=validate_draft({'claims':[{'text':v['quote'],'evidence_ids':[v['eid']]}for v in values]},evidence)
    citations=bound['citations'];numbers={c['evidence_id']:n for n,c in enumerate(citations,1)}
    for c in citations:c['citation_number']=numbers[c['evidence_id']]
    lines=[v['claim']['text']+f" [{numbers[v['eid']]}]"for v in values]
    comparable=(len(values)==len(plan['operands'])==2 and values[0]['number'] is not None
        and values[1]['number'] is not None and values[0]['unit']==values[1]['unit']
        and values[0]['entity'] is not None and values[0]['entity']==values[1]['entity'])
    calculation=None;cautions=list(dict.fromkeys(c for v in values for c in v['cautions']))
    if comparable and plan['operation']!='VALUES':
        first,second=values
        if plan['operation']=='RATIO' and second['number']!=0:
            computed=first['number']/second['number']*100
            lines.append('Tỷ lệ nợ phải trả trên tổng tài sản: '+_display(computed)+'% (làm tròn 2 chữ số thập phân) '
                         f"[{numbers[first['eid']]}][{numbers[second['eid']]}].")
            calculation={'formula':'numerator / denominator * 100','value':str(computed)}
        elif plan['operation']=='DIFFERENCE':
            computed=second['number']-first['number']
            direction='tăng' if computed>0 else 'giảm' if computed<0 else 'không đổi'
            lines.append(f"Từ {first['scope']['periods'][0]} đến {second['scope']['periods'][0]}, "
                         f"{label(first['scope']['metric_code'])} {direction} "
                         f"{_display(abs(computed))} {first['unit']} "
                         f"[{numbers[first['eid']]}][{numbers[second['eid']]}].")
            calculation={'formula':'later - earlier','value':str(computed)}
        else:cautions.append('Mẫu số bằng 0 nên không tính tỷ lệ.')
        if calculation:
            calculation.update(operands=[{'evidence_id':v['eid'],'value':str(v['number']),
                'unit':v['unit'],'period':v['scope']['periods'][0],'metric_code':v['scope']['metric_code']}for v in values],
                rounding='HALF_UP_2_DECIMALS',statement_scope=first['entity'])
    elif plan['operation']!='VALUES' and not missing:
        cautions.append('Nguồn chưa xác nhận cùng đơn vị hoặc cùng phạm vi hợp nhất/riêng lẻ; chỉ trình bày hai dòng gốc, chưa tính chênh lệch hoặc tỷ lệ.')
    if missing:lines.append('Chưa tìm thấy dòng nguồn phù hợp cho: '+', '.join(missing)+'. Không dùng chỉ tiêu khác thay thế.')
    lines.extend(cautions)
    pack={**packs[0],'query_id':str(uuid.uuid4()),'items':list(evidence.values()),'retrieval_backend':'verified_financial_rows'}
    result.update(status='EVIDENCE_READY',reason_code='FINANCIAL_ROWS_VERIFIED',query_id=pack['query_id'],evidence_pack=pack)
    result['answering']=dict(status='DRAFT_READY',reason_code='FINANCIAL_CALCULATION' if calculation else 'FINANCIAL_SOURCE_ROWS',
        draft='\n\n'.join(lines),claims=[v['claim']for v in values],citations=citations,cautions=cautions,
        calculation=calculation,budget=budget.snapshot(),trace=[{'event':'verified_financial_operation','operation':plan['operation']}],
        manifest={'mode':'B1','response_mode':'VERIFIED_FINANCIAL_OPERATION',
                  'components':{'gemini':False,'citation_binding':True,'deterministic_calculation':bool(calculation)}})
    return result
