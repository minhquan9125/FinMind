"""Reconstruct composition evidence from saved vectors, without refit/model loading."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_composition import requests

OUT=ROOT/'outputs/s5_intent_composition_20261112'
SCORER=ROOT/'outputs/s5_intent_scorer_20261112'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def probabilities(values,parameters):
    logits=np.einsum('ij,kj->ik',np.asarray(values,dtype=np.float64),parameters['coefficients'])+parameters['intercepts']
    exponential=np.exp(logits-logits.max(axis=1,keepdims=True))
    return exponential/exponential.sum(axis=1,keepdims=True)


def main():
    method=read(OUT/'method.json')
    for name,digest in method['source_hashes'].items(): assert sha(ROOT/name)==digest,name
    fit=ROOT/read(SCORER/'fit-location.json')['output']
    assert sha(fit/'parameters.npz')==method['head_parameter_sha256']
    parameters=np.load(fit/'parameters.npz',allow_pickle=False)
    labels=read(fit/'summary.json')['labels']
    cases,parts,traces=read(OUT/'cases.json'),read(OUT/'request-parts.json'),read(OUT/'traces.json')
    assert len(cases)==len(parts)==len(traces)==208
    cache=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    lookup=dict(zip(read(cache/'embedded-texts.json'),np.load(cache/'experiment-vectors.npy',allow_pickle=False)))
    training=[json.loads(line) for line in (SCORER/'training.jsonl').read_text(encoding='utf-8').splitlines()]
    lookup.update(zip([r['text'] for r in training],np.load(SCORER/'training-vectors.npy',allow_pickle=False)))
    lookup.update(zip([r['text'] for r in read(SCORER/'evaluation-cases.json')],np.load(SCORER/'evaluation-vectors.npy',allow_pickle=False)))
    fresh=np.load(OUT/'new-vectors.npy',allow_pickle=False)
    assert fresh.shape==(len(read(OUT/'new-texts.json')),1024) and np.isfinite(fresh).all()
    assert np.allclose(np.linalg.norm(fresh,axis=1),1,atol=1e-4,rtol=0)
    lookup.update(zip(read(OUT/'new-texts.json'),fresh))
    raw=probabilities(np.stack([lookup[r['text']] for r in cases]),parameters)
    assert np.allclose(raw,read(OUT/'raw-probabilities.json'),atol=1e-12,rtol=0)
    effective=raw.copy()
    for i,(case,spans,trace) in enumerate(zip(cases,parts,traces)):
        assert spans==requests(case['text'])==trace['parts']
        if spans==[case['text']]:
            assert trace['mode']=='UNCHANGED'
            continue
        component=probabilities(np.stack([lookup[q] for q in spans]),parameters)
        assert np.allclose(component,trace['component_probabilities'],atol=1e-12,rtol=0)
        if len(spans)==1:
            assert trace['mode']=='SUPPORT_REMOVED_SINGLE_REQUEST'
            effective[i]=component[0]
        else:
            assert trace['mode']=='MULTI_REQUEST_SUPPORT'
            top=[sorted(range(7),key=lambda j:(-p[j],labels[j]))[0] for p in component]
            scores=[min(component[a,top[a]],component[b,top[b]]) for a in range(len(top)) for b in range(a+1,len(top))
                    if top[a]!=top[b] and labels[top[a]]!='MIXED' and labels[top[b]]!='MIXED']
            support=max(scores,default=0)
            assert abs(support-trace['support'])<1e-12
            effective[i,labels.index('MIXED')]=max(raw[i,labels.index('MIXED')],support)
    original=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    old_rows=[json.loads(line) for line in (original/'library.jsonl').read_text(encoding='utf-8').splitlines()]
    old_vectors=np.load(original/'vectors.npy',allow_pickle=False).astype(np.float64)
    results=read(OUT/'results.json')
    largest=count=0
    for name,sets in results.items():
        for subset,result in sets.items():
            if subset=='regression_transitions': continue
            expected=[(i,r) for i,r in enumerate(cases) if r['evaluation_set']==subset]
            hits={1:0,3:0,5:0}
            for (i,case),record in zip(expected,result['cases']):
                assert case['id']==record['id'] and case['intent_label']==record['gold']
                if name=='original':
                    q=lookup[case['text']].astype(np.float64)
                    cosine=np.einsum('ij,j->i',old_vectors,q)/(np.linalg.norm(old_vectors,axis=1)*np.linalg.norm(q))
                    values=np.array([max(cosine[j] for j,r in enumerate(old_rows) if r['intent_label']==label) for label in labels])
                else: values=raw[i] if name=='linear' else effective[i]
                order=sorted(range(7),key=lambda j:(-values[j],labels[j]))
                assert [labels[j] for j in order]==[g['intent_label'] for g in record['ranking']['groups']]
                largest=max(largest,max(abs(values[labels.index(g['intent_label'])]-g['score']) for g in record['ranking']['groups']))
                if case['intent_label']:
                    rank=[labels[j] for j in order].index(case['intent_label'])+1
                    for k in hits: hits[k]+=rank<=k
                count+=1
            assert {str(k):v for k,v in hits.items()}==result['metrics']['hits']
    assert largest<1e-10
    proof=dict(status='PASS',rankings_recomputed=count,max_score_difference=largest,
        frozen_classifier_unchanged=True,component_probabilities_reconstructed=True,
        mixed_support_independently_recomputed=True,original_source_hashes_unchanged=True,
        no_training=True,no_legacy_threshold_applied=True,calibrated=False)
    (OUT/'audit.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof,indent=2))


if __name__=='__main__': main()
