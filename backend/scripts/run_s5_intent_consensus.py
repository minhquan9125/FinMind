"""Frozen second development pass: decision evidence, not invented ranking scores."""
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_request_consensus import resolve
from src.retrieval_orchestration.intent_experiment import transitions
from prepare_s5_intent_scorer import sha,write

PARENT=ROOT/'outputs/s5_intent_composition_20261112'
OUT=PARENT/'consensus-v2'


def stats(rows,labels):
    labeled=[r for r in rows if r['gold']]
    confusion=Counter((r['gold'],r['final_label']) for r in labeled)
    f1=[]
    for label in labels:
        tp=confusion[label,label]
        fp=sum(n for (gold,pred),n in confusion.items() if pred==label and gold!=label)
        fn=sum(n for (gold,pred),n in confusion.items() if gold==label and pred!=label)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    correct=sum(r['gold']==r['final_label'] for r in labeled)
    return dict(correct=correct,labeled=len(labeled),accuracy=correct/len(labeled),macro_f1=sum(f1)/len(f1),
                wrong_ids=[r['id'] for r in labeled if r['gold']!=r['final_label']],
                confusion_matrix={a:{b:confusion[a,b] for b in labels} for a in labels},
                confidence_available=False,legacy_threshold_not_applied=True)


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    def read(p): return json.loads(p.read_text(encoding='utf-8'))
    for name,digest in read(PARENT/'method.json')['source_hashes'].items():
        if sha(ROOT/name)!=digest: raise ValueError('PARENT_SOURCE_CHANGED')
    cases,traces=read(PARENT/'cases.json'),read(PARENT/'traces.json')
    raw=np.asarray(read(PARENT/'raw-probabilities.json'))
    parent=read(PARENT/'results.json')
    labels=sorted(parent['linear']['development']['metrics']['per_label'])
    watched=[PARENT/name for name in ['method.json','cases.json','traces.json','raw-probabilities.json','results.json','summary.json']]
    watched += [ROOT/'backend/src/retrieval_orchestration/intent_request_consensus.py',Path(__file__),ROOT/'docs/sprint5/S5-WBS04.1-consensus-plan.md']
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in watched}
    OUT.mkdir()
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_SCORING',type='DEVELOPMENT_REANALYSIS_NOT_INDEPENDENT_TEST',
          source_hashes=hashes,no_fit=True,no_new_embeddings=True,raw_classifier_scores_unchanged=True,
          confidence=None,legacy_threshold_not_applied=True))
    resolutions=[resolve(raw[i],trace['component_probabilities'],labels) for i,trace in enumerate(traces)]
    results={}
    metrics={}
    changes={}
    for dataset in sorted({r['evaluation_set'] for r in cases}):
        indices=[i for i,r in enumerate(cases) if r['evaluation_set']==dataset]
        original=parent['linear'][dataset]['cases']
        by_id={r['id']:r for r in original}
        rows=[]
        for i in indices:
            case=cases[i]
            rows.append(dict(id=case['id'],question=case['text'],gold=case['intent_label'],
                 base_label=by_id[case['id']]['top1'],final_label=resolutions[i]['intent_label'],
                 resolution=resolutions[i],base_ranking=by_id[case['id']]['ranking'],parts=traces[i]['parts']))
        results[dataset]=rows
        metrics[dataset]=stats(rows,labels)
        changes[dataset]=transitions(original,[dict(id=r['id'],gold=r['gold'],top1=r['final_label']) for r in rows])
    old_changes=transitions(parent['original']['regression']['cases'],
         [dict(id=r['id'],gold=r['gold'],top1=r['final_label']) for r in results['regression']])
    target=next(r for r in results['regression'] if r['id']=='S5-T-038')
    evidence=[r for r in results['controls'] if r['id'].startswith('CONTROL-EVIDENCE-')]
    passes=(target['final_label']=='MIXED' and not old_changes['regressed']
            and not any(c['regressed'] for c in changes.values())
            and metrics['development']['correct']>=parent['linear']['development']['metrics']['hits']['1']
            and all(r['final_label']=='PERSON_ROLE' for r in evidence))
    for name,digest in hashes.items():
        if sha(ROOT/name)!=digest: raise ValueError('SOURCE_CHANGED_DURING_SCORING')
    write(OUT/'results.json',results)
    write(OUT/'summary.json',dict(status='COMPLETED_DECISION_EXPERIMENT_NOT_PRODUCTION_APPROVAL',passes_gate=passes,
          labels=labels,metrics=metrics,changes_against_linear=changes,changes_against_original_regression=old_changes,
          target_T038=target['resolution'],confidence=None,no_score_reassignment=True,
          top3_and_top5_remain_raw_classifier_metrics=True,runtime_unchanged=True))
    print(json.dumps(dict(passes_gate=passes,T038=target['final_label'],
          correct={name:m['correct'] for name,m in metrics.items()},changes=changes,
          changes_against_original=old_changes),indent=2))


if __name__=='__main__': main()
