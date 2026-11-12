"""Fit two offline ranking methods; choose linear C from grouped library CV only."""
from collections import defaultdict
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_scoring import family_weights,centroid_vectors,classifier_probabilities,normalized,rankings,baseline_policy
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher,summarize_evaluation
from src.retrieval_orchestration.intent_experiment import ROUTES,transitions
from prepare_s5_intent_scorer import OUT,sha,write,read_rows


def report(cases,predictions,labels):
    summary=summarize_evaluation(cases,predictions,labels)
    details=[]
    for case,prediction in zip(cases,predictions):
        ordered=[g['intent_label'] for g in prediction['groups']]
        gold=case['intent_label']
        details.append(dict(id=case['id'],gold=gold,top1=ordered[0],gold_rank=ordered.index(gold)+1 if gold else None,
            question=case['text'],ranking=prediction,company=case.get('company'),family_id=case.get('family_id',case['id'])))
    labeled=[r for r in details if r['gold']]
    control=defaultdict(list)
    for row in details:
        if row['company']: control[row['family_id']].append(row)
    summary.update(hits={str(k):sum(r['gold_rank']<=k for r in labeled) for k in [1,3,5]},
         argmax_route_wrong_without_threshold=[r['id'] for r in labeled if ROUTES[r['top1']]!=ROUTES[r['gold']]],
         single_to_mixed=[r['id'] for r in labeled if r['gold']!='MIXED' and r['top1']=='MIXED'],
         mixed_to_single=[r['id'] for r in labeled if r['gold']=='MIXED' and r['top1']!='MIXED'],
         company_changed_top1=[f for f,rows in control.items() if len({r['top1'] for r in rows})>1],
         company_all_correct=[f for f,rows in control.items() if all(r['gold']==r['top1'] for r in rows)],
         legacy_policy_applied=predictions[0]['ranking_policy']=='cosine-max-per-label-v1')
    if summary['legacy_policy_applied']:
        decisions=[(r,baseline_policy(r['ranking'])) for r in labeled]
        summary['legacy_policy']=dict(accepted=sum(d!='NEED_FALLBACK' for _,d in decisions),
              fallback=sum(d=='NEED_FALLBACK' for _,d in decisions),
              wrong_route_ids=[r['id'] for r,d in decisions if d!='NEED_FALLBACK' and d!=ROUTES[r['gold']]])
    return dict(metrics=summary,cases=details)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT/'fit')
    output=parser.parse_args().output.resolve()
    if output.exists(): raise FileExistsError(output)
    method=json.loads((OUT/'method.json').read_text())
    watched={**method['source_hashes'],**{(OUT/name).relative_to(ROOT).as_posix():d for name,d in method['files'].items()}}
    for name,digest in watched.items():
        if sha(ROOT/name)!=digest: raise ValueError('FROZEN_INPUT_CHANGED: '+name)
    rows=read_rows(OUT/'training.jsonl')
    x=np.load(OUT/'training-vectors.npy',allow_pickle=False).astype(np.float64)
    folds=np.load(OUT/'folds.npy',allow_pickle=False)
    weights=np.load(OUT/'weights.npy',allow_pickle=False)
    y=np.array([r['intent_label'] for r in rows])
    labels=sorted(set(y))
    cases=json.loads((OUT/'evaluation-cases.json').read_text(encoding='utf-8'))
    queries=np.load(OUT/'evaluation-vectors.npy',allow_pickle=False).astype(np.float64)
    output.mkdir()
    write(output/'start.json',dict(status='STARTED_BEFORE_FIT',method_sha256=sha(OUT/'method.json'),
          runner_sha256=sha(Path(__file__)),sklearn=importlib.metadata.version('scikit-learn'),
          numpy=importlib.metadata.version('numpy'),no_runtime_change=True))
    cv=[]
    for c in method['C_grid']:
        oof=np.zeros((len(rows),len(labels)))
        iterations=[]
        for fold in range(method['folds']):
            train=np.flatnonzero(folds!=fold)
            val=np.flatnonzero(folds==fold)
            if set(y[train])!=set(labels) or set(y[val])!=set(labels): raise ValueError('FOLD_MISSING_CLASS')
            if {rows[i]['family_id'] for i in train}&{rows[i]['family_id'] for i in val}: raise ValueError('FAMILY_LEAKAGE')
            model=LogisticRegression(C=c,solver=method['solver'],l1_ratio=method['l1_ratio'],
                                    max_iter=method['max_iter'],tol=method['tol'])
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                model.fit(x[train],y[train],sample_weight=family_weights([rows[i] for i in train]))
            if list(model.classes_)!=labels: raise ValueError('CLASS_ORDER_MISMATCH')
            oof[val]=model.predict_proba(x[val])
            iterations.append(model.n_iter_.tolist())
        predicted=np.array(labels)[np.argmax(oof,axis=1)]
        entry=dict(C=c,macro_f1=float(f1_score(y,predicted,labels=labels,average='macro',sample_weight=weights)),
             accuracy=float(np.average(predicted==y,weights=weights)),iterations=iterations)
        cv.append(entry)
        np.save(output/f'oof-C-{c}.npy',oof,allow_pickle=False)
    chosen=min(cv,key=lambda row:(-row['macro_f1'],-row['accuracy'],row['C']))
    write(output/'cv-selection.json',dict(chosen=chosen,all_candidates=cv,
          chosen_before_evaluation=True,training_rows_only=True))
    model=LogisticRegression(C=chosen['C'],solver=method['solver'],l1_ratio=method['l1_ratio'],
                            max_iter=method['max_iter'],tol=method['tol'])
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        model.fit(x,y,sample_weight=weights)
    probabilities=classifier_probabilities(queries,model.coef_,model.intercept_)
    if not np.allclose(probabilities,model.predict_proba(queries),atol=1e-12,rtol=0): raise ValueError('PROBABILITY_EXPORT_MISMATCH')
    center_labels,centers=centroid_vectors(rows,x)
    if center_labels!=labels: raise ValueError('CENTROID_CLASS_ORDER')
    np.savez(output/'parameters.npz',coefficients=model.coef_,intercepts=model.intercept_,centroids=centers)
    original=load_library(ROOT/'outputs/s5_wbs033_20261110/intent-library-v1')
    from types import SimpleNamespace
    encoder=SimpleNamespace(model_name=method['model']['name'],revision=method['model']['revision'])
    matcher=IntentMatcher(original,encoder)
    question=[r['text'] for r in cases]
    predictions=dict(original=[matcher._rank(q,v,7,5) for q,v in zip(question,queries)],
         centroid=rankings(question,normalized(queries)@centers.T,labels,'cosine-family-centroid-v1',
                           'COSINE_SIMILARITY_NOT_PROBABILITY',method['model']),
         linear=rankings(question,probabilities,labels,'intent-linear-v1',
                         'CLASSIFIER_PROBABILITY_UNCALIBRATED',method['model']))
    results={}
    for name,values in predictions.items():
        results[name]={}
        for set_name in sorted({r['evaluation_set'] for r in cases}):
            indices=[i for i,r in enumerate(cases) if r['evaluation_set']==set_name]
            results[name][set_name]=report([cases[i] for i in indices],[values[i] for i in indices],labels)
    if results['original']['regression']['metrics']['hits']!={'1':22,'3':41,'5':46}: raise ValueError('BASELINE_DRIFT')
    eligible=[]
    for name in ['centroid','linear']:
        change=transitions(results['original']['regression']['cases'],results[name]['regression']['cases'])
        results[name]['regression_transitions']=change
        dev,base=results[name]['development']['metrics'],results['original']['development']['metrics']
        if dev['top1_accuracy']>base['top1_accuracy'] and dev['macro_f1']>base['macro_f1'] and not change['regressed']:
            eligible.append(name)
    for name,digest in watched.items():
        if sha(ROOT/name)!=digest: raise ValueError('SOURCE_CHANGED_DURING_FIT')
    write(output/'results.json',results)
    write(output/'summary.json',dict(status='COMPLETED_OFFLINE_NOT_APPROVED',labels=labels,C_selection=chosen,
          eligible_for_further_check=eligible,
          further_check_and_calibration_required=bool(eligible),legacy_threshold_applied_to_candidates=False,
          no_runtime_change=True,metrics={name:{s:r['metrics'] for s,r in sets.items() if s!='regression_transitions'} for name,sets in results.items()},
          regression_transitions={name:results[name]['regression_transitions'] for name in ['centroid','linear']},
          parameter_sha256=sha(output/'parameters.npz')))
    write(OUT/'fit-location.json',dict(output=output.relative_to(ROOT).as_posix(),summary_sha256=sha(output/'summary.json')))
    print(json.dumps(dict(C_selection=chosen,eligible=eligible,
           hits={name:{s:r['metrics']['hits'] for s,r in sets.items() if s!='regression_transitions'} for name,sets in results.items()}),indent=2))


if __name__=='__main__':
    main()
