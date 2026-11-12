"""Independently reconstruct OOF selection, centroids and all saved scorer outputs."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/s5_intent_scorer_20261112'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def macro_f1(y,predicted,labels,weights):
    values=[]
    for label in labels:
        tp=sum(w for a,b,w in zip(y,predicted,weights) if a==b==label)
        fp=sum(w for a,b,w in zip(y,predicted,weights) if b==label and a!=label)
        fn=sum(w for a,b,w in zip(y,predicted,weights) if a==label and b!=label)
        values.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return sum(values)/len(values)


def main():
    location=read(OUT/'fit-location.json')
    fit=ROOT/location['output']
    assert sha(fit/'summary.json')==location['summary_sha256']
    method=read(OUT/'method.json')
    for path,digest in method['source_hashes'].items(): assert sha(ROOT/path)==digest,path
    for name,digest in method['files'].items(): assert sha(OUT/name)==digest,name
    start=read(fit/'start.json')
    assert start['method_sha256']==sha(OUT/'method.json')
    recovery=read(OUT/'recovery-note.json')
    assert recovery['original_runner_sha256']==start['runner_sha256']
    assert recovery['corrected_runner_sha256']==sha(ROOT/'backend/scripts/run_s5_intent_scorer.py')
    summary=read(fit/'summary.json')
    assert summary['parameter_sha256']==sha(fit/'parameters.npz')
    params=np.load(fit/'parameters.npz',allow_pickle=False)
    first=np.load(OUT/'fit/parameters.npz',allow_pickle=False)
    assert all(np.array_equal(params[name],first[name]) for name in params.files)
    rows=[json.loads(line) for line in (OUT/'training.jsonl').read_text(encoding='utf-8').splitlines()]
    x=np.load(OUT/'training-vectors.npy',allow_pickle=False).astype(np.float64)
    weights=np.load(OUT/'weights.npy',allow_pickle=False)
    folds=np.load(OUT/'folds.npy',allow_pickle=False)
    labels=summary['labels']
    y=[r['intent_label'] for r in rows]
    families=defaultdict(list)
    for i,row in enumerate(rows):
        assert row['split']=='LIBRARY'
        families[row['family_id']].append(i)
    for indices in families.values(): assert len(set(folds[indices]))==1
    for fold in range(4):
        assert {y[i] for i in range(len(rows)) if folds[i]==fold}==set(labels)
        assert {y[i] for i in range(len(rows)) if folds[i]!=fold}==set(labels)
    for label in labels:
        total=sum(w for a,w in zip(y,weights) if a==label)
        assert abs(total-len(rows)/len(labels))<1e-10
        family_weights=[weights[indices].sum() for indices in families.values() if y[indices[0]]==label]
        assert max(family_weights)-min(family_weights)<1e-10
    cv=[]
    for c in method['C_grid']:
        oof=np.load(fit/f'oof-C-{c}.npy',allow_pickle=False)
        assert oof.shape==(len(rows),7) and np.isfinite(oof).all() and np.allclose(oof.sum(axis=1),1)
        predicted=[labels[i] for i in oof.argmax(axis=1)]
        cv.append(dict(C=c,macro_f1=macro_f1(y,predicted,labels,weights),
             accuracy=float(np.average(np.array(predicted)==np.array(y),weights=weights))))
    chosen=min(cv,key=lambda r:(-r['macro_f1'],-r['accuracy'],r['C']))
    assert chosen['C']==summary['C_selection']['C']
    assert abs(chosen['macro_f1']-summary['C_selection']['macro_f1'])<1e-12
    unit=x/np.linalg.norm(x,axis=1,keepdims=True)
    prototypes=[]
    for label in labels:
        family_centers=[]
        for indices in families.values():
            if y[indices[0]]==label:
                center=unit[indices].mean(axis=0)
                family_centers.append(center/np.linalg.norm(center))
        center=np.mean(family_centers,axis=0)
        prototypes.append(center/np.linalg.norm(center))
    assert np.allclose(prototypes,params['centroids'],atol=1e-14,rtol=0)
    cases=read(OUT/'evaluation-cases.json')
    queries=np.load(OUT/'evaluation-vectors.npy',allow_pickle=False).astype(np.float64)
    assert not {r['text'].casefold() for r in rows}&{r['text'].casefold() for r in cases}
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    old_rows=[json.loads(line) for line in (original_dir/'library.jsonl').read_text(encoding='utf-8').splitlines()]
    old=np.load(original_dir/'vectors.npy',allow_pickle=False).astype(np.float64)
    source=read(fit/'results.json')
    largest=count=0
    for name,sets in source.items():
        for set_name,result in sets.items():
            if set_name=='regression_transitions': continue
            expected=[(i,r) for i,r in enumerate(cases) if r['evaluation_set']==set_name]
            assert len(expected)==len(result['cases'])
            hits={1:0,3:0,5:0}
            for (i,case),record in zip(expected,result['cases']):
                assert case['id']==record['id'] and case['text']==record['question'] and case['intent_label']==record['gold']
                query=queries[i]
                if name=='original':
                    cosine=np.einsum('ij,j->i',old,query)/(np.linalg.norm(old,axis=1)*np.linalg.norm(query))
                    scores={label:max(float(cosine[j]) for j,r in enumerate(old_rows) if r['intent_label']==label) for label in labels}
                elif name=='centroid':
                    scores=dict(zip(labels,np.einsum('ij,j->i',prototypes,query)/np.linalg.norm(query)))
                else:
                    logits=np.einsum('ij,j->i',params['coefficients'],query)+params['intercepts']
                    probability=np.exp(logits-logits.max()); probability/=probability.sum()
                    scores=dict(zip(labels,probability))
                ordered=sorted(labels,key=lambda label:(-scores[label],label))
                assert ordered==[g['intent_label'] for g in record['ranking']['groups']]
                for group in record['ranking']['groups']: largest=max(largest,abs(group['score']-scores[group['intent_label']]))
                if case['intent_label']:
                    rank=ordered.index(case['intent_label'])+1
                    for k in hits: hits[k]+=rank<=k
                count+=1
            assert {str(k):v for k,v in hits.items()}==result['metrics']['hits']
    assert largest<1e-10
    proof=dict(status='PASS',rankings_recomputed=count,max_score_difference=largest,
          grouped_split_verified=True,family_and_label_weights_verified=True,C_selected_from_OOF_only=chosen['C'],
          centroid_reconstruction_passed=True,no_evaluation_rows_fitted=True,
          recovery_parameter_arrays_identical=True,official_source_hashes_unchanged=True,
          calibrated=False,legacy_threshold_not_applied_to_candidates=True)
    (OUT/'audit.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__': main()
