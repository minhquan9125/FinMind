"""Third frozen development pass; preserves raw rankings and prior experiments."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_request_objectives import resolve_objectives
from src.retrieval_orchestration.intent_experiment import transitions
from prepare_s5_intent_scorer import sha,write
from run_s5_intent_consensus import stats

PARENT=ROOT/'outputs/s5_intent_composition_20261112'
OUT=PARENT/'objectives-v3'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    parent=read(PARENT/'results.json')
    labels=sorted(parent['linear']['development']['metrics']['per_label'])
    cases,traces=read(PARENT/'cases.json'),read(PARENT/'traces.json')
    raw=np.asarray(read(PARENT/'raw-probabilities.json'))
    watched=[PARENT/name for name in ['cases.json','traces.json','raw-probabilities.json','results.json']]
    watched += [PARENT/'consensus-v2/results.json',PARENT/'new-check/results.json',PARENT/'new-check/summary.json',
                ROOT/'backend/src/retrieval_orchestration/intent_request_objectives.py',
                ROOT/'backend/src/retrieval_orchestration/intent_request_consensus.py',
                ROOT/'docs/sprint5/intent-labels.v1.json',ROOT/'docs/sprint5/S5-WBS04.1-objective-plan.md',Path(__file__)]
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in watched}
    OUT.mkdir()
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_SCORING',source_hashes=hashes,
          all_sets_previously_seen=True,no_fit=True,no_new_embeddings=True,
          raw_scores_preserved=True,confidence=None,runtime_enabled=False))
    groups={}
    for dataset in sorted({r['evaluation_set'] for r in cases}):
        original={r['id']:r for r in parent['linear'][dataset]['cases']}
        rows=[]
        for i,case in enumerate(cases):
            if case['evaluation_set']!=dataset: continue
            decision=resolve_objectives(raw[i],traces[i]['component_probabilities'],labels,traces[i]['parts'])
            rows.append(dict(id=case['id'],question=case['text'],gold=case['intent_label'],
                 base_label=original[case['id']]['top1'],final_label=decision['intent_label'],
                 resolution=decision,base_ranking=original[case['id']]['ranking'],parts=traces[i]['parts']))
        groups[dataset]=rows
    extra=[]
    for row in read(PARENT/'new-check/results.json'):
        ranking=row['base_ranking']
        base=[next(g['score'] for g in ranking['groups'] if g['intent_label']==label) for label in labels]
        decision=resolve_objectives(base,row['component_probabilities'],labels,row['parts'])
        extra.append(dict(id=row['id'],question=row['question'],gold=row['gold'],base_label=ranking['groups'][0]['intent_label'],
               final_label=decision['intent_label'],resolution=decision,base_ranking=ranking,parts=row['parts']))
    groups['previous_new_check']=extra
    metrics={name:stats(rows,labels) for name,rows in groups.items()}
    changes={}
    against_v2={}
    v2=read(PARENT/'consensus-v2/results.json')
    for dataset,rows in groups.items():
        linear=[dict(id=r['id'],gold=r['gold'],top1=r['base_label']) for r in rows]
        current=[dict(id=r['id'],gold=r['gold'],top1=r['final_label']) for r in rows]
        changes[dataset]=transitions(linear,current)
        earlier=v2[dataset] if dataset in v2 else read(PARENT/'new-check/results.json')
        against_v2[dataset]=transitions([dict(id=r['id'],gold=r['gold'],top1=r['final_label']) for r in earlier],current)
    old=transitions(parent['original']['regression']['cases'],[dict(id=r['id'],gold=r['gold'],top1=r['final_label']) for r in groups['regression']])
    target=next(r for r in groups['regression'] if r['id']=='S5-T-038')
    core=[r for r in groups['controls'] if r['id'].startswith('CONTROL-')]
    passes=(target['final_label']=='MIXED' and all(r['gold']==r['final_label'] for r in core)
            and not old['regressed'] and not any(c['regressed'] for c in changes.values())
            and not any(c['regressed'] for c in against_v2.values()))
    for name,digest in hashes.items():
        if sha(ROOT/name)!=digest: raise ValueError('SOURCE_CHANGED_DURING_SCORING')
    write(OUT/'results.json',groups)
    write(OUT/'summary.json',dict(status='COMPLETED_DEVELOPMENT_NOT_INDEPENDENT_FINAL_TEST',passes_gate=passes,
        metrics=metrics,changes_against_linear=changes,changes_against_v2=against_v2,
        original_regression_changes=old,target_T038=target['resolution'],
        core_controls_correct=sum(r['gold']==r['final_label'] for r in core),core_controls_total=len(core),
        confidence=None,calibrated=False,runtime_unchanged=True))
    print(json.dumps(dict(passes_gate=passes,T038=target['final_label'],correct={k:m['correct'] for k,m in metrics.items()},
           regression_against_linear={k:v['regressed'] for k,v in changes.items()},
           regression_against_v2={k:v['regressed'] for k,v in against_v2.items()},
           original_regressions=old['regressed'],core_controls_correct=sum(r['gold']==r['final_label'] for r in core)),indent=2))


if __name__=='__main__': main()
