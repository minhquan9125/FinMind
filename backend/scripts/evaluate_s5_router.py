"""Huyen 04.3 v2: evaluate the installed classifier without training or changing gold.

Default corpus is public DEVELOPMENT regression, never blind acceptance.
Historical 80-question v1 gold remains in router-acceptance-v1 for audit only.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
DEFAULT_CORPUS=ROOT/'docs/sprint5/intent-v2/development.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_corpus(path):
    from src.retrieval_orchestration.intent_routing import V2_INTENT_ROUTES
    rows=[json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows or len({row['id'] for row in rows})!=len(rows):
        raise ValueError('Empty corpus or duplicate IDs')
    for row in rows:
        if (not isinstance(row.get('text'),str) or not row['text'].strip()
                or row.get('intent_label') not in V2_INTENT_ROUTES
                or not isinstance(row.get('component_intents'),list)):
            raise ValueError('Invalid v2 gold row')
        parts=row['component_intents']
        if (any(c not in V2_INTENT_ROUTES or c=='MIXED' for c in parts)
                or len(set(parts))!=len(parts)
                or (row['intent_label']=='MIXED' and len(parts)<2)
                or (row['intent_label']!='MIXED' and parts)):
            raise ValueError('Invalid component gold')
    return rows


def prediction_matches(case,resolution):
    return (case['intent_label']==resolution.get('intent_label')
            and sorted(case['component_intents'])==sorted(resolution.get('component_labels',[])))


def verdict_v2(rows,*,independent=False):
    rate=sum(row['passed'] for row in rows)/len(rows) if rows else 0
    return dict(status=('NOT_INDEPENDENT_ACCEPTANCE' if not independent else 'PASS' if rows and rate>=.9 else 'FAIL'),
                success=rate,count=len(rows),threshold=.9,metric='label_and_components_only')


def safe_cell(value):
    return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value


def write_workbook(path,verdict,rows,method):
    from openpyxl import Workbook
    book=Workbook(); book.remove(book.active)
    def sheet(name,headers,values):
        ws=book.create_sheet(name); ws.append(headers)
        for row in values:
            ws.append([safe_cell(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for v in row])
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    keys=['id','question','expected_label','actual_label','expected_components','actual_components',
          'decision','route','source','reason_code','model_top_1_score','model_score_gap','passed','error']
    sheet('Tong_quan',['metric','value'],list(verdict.items())+[['scope','Module evaluation; no Chat/DB/provider calls']])
    sheet('Cau_hoi',keys,[[r.get(k) for k in keys] for r in rows])
    sheet('Policy_04_2',['decision','count'],list(Counter(r['decision'] for r in rows).items()))
    sheet('Coverage',['metric','value'],[['line_coverage',None],['branch_coverage',None],
        ['note','Not measured by classifier inference. Use pytest coverage for contract tests.']])
    sheet('Ca_sai',keys,[[r.get(k) for k in keys] for r in rows if not r['passed']])
    sheet('Method',['key','value'],list(method.items()))
    book.save(path)


def evaluate(cases,classifier):
    from src.retrieval_orchestration.intent_routing import decide_intent_route_v2
    results=[]
    for case in cases:
        try:
            prediction=classifier.classify(case['text'])
            # Neutral scope fixture isolates intent/policy. Not a ticker resolver test.
            scope=case.get('scope',dict(company_ticker='FPT',period=None))
            decision=decide_intent_route_v2(prediction,question=case['text'],**scope)
            resolved=prediction['resolution']
            passed=prediction_matches(case,resolved)
            results.append(dict(id=case['id'],question=case['text'],expected_label=case['intent_label'],
                actual_label=resolved['intent_label'],expected_components=case['component_intents'],
                actual_components=resolved['component_labels'],decision=decision['decision'],route=decision['route'],
                source=decision.get('source'),reason_code=decision['reason_code'],
                model_top_1_score=decision.get('model_top_1_score'),model_score_gap=decision.get('model_score_gap'),
                passed=passed,error=None if passed else 'Label or components differ from frozen gold',
                resolution=resolved,model_ranking=decision.get('model_ranking')))
        except Exception as error:
            results.append(dict(id=case['id'],question=case['text'],expected_label=case['intent_label'],
                expected_components=case['component_intents'],actual_label=None,actual_components=[],
                decision='ERROR',route=None,source=None,reason_code='EVALUATION_ERROR',
                passed=False,error=f'{type(error).__name__}: {error}'))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,default=DEFAULT_CORPUS)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():
        raise FileExistsError('Choose a new output directory; preserve prior evidence')
    cases=load_corpus(args.corpus)
    from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier,DEFAULT_ARTIFACT
    from src.documents.embeddings import EmbeddingService
    manifest_path=DEFAULT_ARTIFACT/'library/manifest.json'
    model=json.loads(manifest_path.read_text(encoding='utf-8'))['model']
    protected=[args.corpus,Path(__file__),ROOT/'backend/src/retrieval_orchestration/intent_routing.py',
        ROOT/'backend/src/retrieval_orchestration/intent_fallback_contract.py',
        ROOT/'backend/src/retrieval_orchestration/intent_v2_classifier.py',
        ROOT/'backend/src/retrieval_orchestration/intent_v2_rules.py',DEFAULT_ARTIFACT/'manifest.json']
    before={str(p):sha(p) for p in protected}
    output.mkdir(parents=True)
    method=dict(corpus=str(args.corpus),corpus_sha256=sha(args.corpus),model=model,
        created_at=datetime.now(timezone.utc).isoformat(),independent_acceptance=False,
        corpus_purpose='Public development regression' if args.corpus.resolve()==DEFAULT_CORPUS.resolve() else 'Caller-supplied corpus; independence not verified',
        scope_fixture='FPT/period=null unless explicitly supplied per row; not a resolver benchmark',
        fresh_model_inference=True,provider_called=False,webchat_tested=False,no_fit=True,input_hashes=before)
    (output/'method.json').write_text(json.dumps(method,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"Loading {model['name']} and evaluating {len(cases)} v2 questions",flush=True)
    started=time.perf_counter()
    encoder=EmbeddingService(model['name'],revision=model['revision'],device='cpu',batch_size=4)
    classifier=IntentClassifier.load(DEFAULT_ARTIFACT,encoder)
    rows=evaluate(cases,classifier)
    verdict=verdict_v2(rows,independent=False)
    verdict.update(errors=sum(row['decision']=='ERROR' for row in rows),elapsed_seconds=time.perf_counter()-started,
        full_043_acceptance='NOT_ESTABLISHED',route_accuracy=None,line_coverage=None,branch_coverage=None,
        note='Label/component regression only. Policy routes require separate gold; no blind/production claim.')
    if before!={str(p):sha(p) for p in protected}:
        raise RuntimeError('Inputs changed during evaluation')
    verdict['inputs_unchanged']=True
    for name,value in [('results.json',rows),('summary.json',verdict)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    write_workbook(output/'S5_HUYEN_ROUTER_V2.xlsx',verdict,rows,method)
    print(json.dumps(verdict,ensure_ascii=False),flush=True)
    return 1 if verdict['errors'] or verdict['success']<.9 else 0


if __name__=='__main__':
    raise SystemExit(main())
