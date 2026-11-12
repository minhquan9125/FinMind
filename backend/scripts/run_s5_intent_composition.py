"""One frozen composition experiment using an unchanged linear classifier."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_composition import requests,combine_scores
from src.retrieval_orchestration.intent_scoring import classifier_probabilities,rankings
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from src.retrieval_orchestration.intent_experiment import transitions
from run_s5_intent_scorer import report
from prepare_s5_intent_scorer import sha,write,read_rows

SCORER=ROOT/'outputs/s5_intent_scorer_20261112'
DATA=ROOT/'docs/sprint5/intent-composition-v1'
OUT=ROOT/'outputs/s5_intent_composition_20261112'


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    fit=ROOT/json.loads((SCORER/'fit-location.json').read_text())['output']
    previous=json.loads((fit/'summary.json').read_text(encoding='utf-8'))
    if sha(fit/'parameters.npz')!=previous['parameter_sha256']: raise ValueError('HEAD_CHANGED')
    parameters=np.load(fit/'parameters.npz',allow_pickle=False)
    labels=previous['labels']
    old_method=json.loads((SCORER/'method.json').read_text())
    controls_manifest=json.loads((DATA/'manifest.json').read_text())
    if sha(DATA/'controls.jsonl')!=controls_manifest['source_sha256']: raise ValueError('CONTROLS_CHANGED')
    cases=json.loads((SCORER/'evaluation-cases.json').read_text(encoding='utf-8'))
    controls=read_rows(DATA/'controls.jsonl')
    cases += [dict(r,evaluation_set='controls') for r in controls]
    training=read_rows(SCORER/'training.jsonl')
    if {r['text'].casefold() for r in training}&{r['text'].casefold() for r in controls}: raise ValueError('CONTROL_TRAIN_OVERLAP')
    parts=[requests(r['text']) for r in cases]
    lookup={}
    cache=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    lookup.update(zip(json.loads((cache/'embedded-texts.json').read_text(encoding='utf-8')),
                      np.load(cache/'experiment-vectors.npy',allow_pickle=False)))
    lookup.update(zip([r['text'] for r in training],np.load(SCORER/'training-vectors.npy',allow_pickle=False)))
    old_cases=json.loads((SCORER/'evaluation-cases.json').read_text(encoding='utf-8'))
    lookup.update(zip([r['text'] for r in old_cases],np.load(SCORER/'evaluation-vectors.npy',allow_pickle=False)))
    required={r['text'] for r in cases}|{part for pieces in parts for part in pieces}
    missing=sorted(required-set(lookup))
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    watched=[fit/'parameters.npz',fit/'summary.json',fit/'results.json',SCORER/'method.json',
             SCORER/'evaluation-cases.json',SCORER/'evaluation-vectors.npy',SCORER/'training.jsonl',
             SCORER/'training-vectors.npy',cache/'embedded-texts.json',cache/'experiment-vectors.npy',
             DATA/'controls.jsonl',DATA/'manifest.json',ROOT/'docs/sprint5/S5-WBS04.1-composition-plan.md',
             ROOT/'backend/src/retrieval_orchestration/intent_composition.py',
             ROOT/'backend/src/retrieval_orchestration/intent_scoring.py',
             ROOT/'backend/scripts/run_s5_intent_scorer.py',Path(__file__),*original_dir.iterdir()]
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in watched if p.is_file()}
    OUT.mkdir()
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_INFERENCE',model=old_method['model'],
         fixed_head_C=previous['C_selection']['C'],head_parameter_sha256=sha(fit/'parameters.npz'),
         source_hashes=hashes,no_fit=True,score_type='COMPOSITION_SUPPORT_UNCALIBRATED',
         old_threshold_not_applied=True,controls_authored_by_same_agent=True,
         type='ONE_PREDECLARED_HEURISTIC_NO_TUNING_AFTER_SCORES',missing_real_embedding_texts=len(missing)))
    write(OUT/'cases.json',cases)
    write(OUT/'request-parts.json',parts)
    write(OUT/'new-texts.json',missing)
    encoder=get_embedding_service()
    expected=old_method['model']
    if (encoder.model_name,encoder.revision)!=(expected['name'],expected['revision']): raise ValueError('MODEL_MISMATCH')
    print(f'Embedding {len(missing)} missing texts; fixed classifier, no training.',flush=True)
    if missing:
        fresh=np.asarray(encoder.embed_texts(missing),dtype=np.float32)
        if fresh.shape!=(len(missing),1024) or not np.isfinite(fresh).all(): raise ValueError('INVALID_REAL_EMBEDDINGS')
        np.save(OUT/'new-vectors.npy',fresh,allow_pickle=False)
        lookup.update(zip(missing,fresh))
    question=[r['text'] for r in cases]
    raw=classifier_probabilities(np.stack([lookup[q] for q in question]),parameters['coefficients'],parameters['intercepts'])
    effective=raw.copy()
    traces=[]
    for i,pieces in enumerate(parts):
        changed=pieces!=[question[i]]
        component=classifier_probabilities(np.stack([lookup[q] for q in pieces]),parameters['coefficients'],parameters['intercepts']) if changed else []
        if changed and len(pieces)==1:
            effective[i]=component[0]
            traces.append(dict(mode='SUPPORT_REMOVED_SINGLE_REQUEST',parts=pieces,component_probabilities=component.tolist(),support=0.,component_labels=[]))
        elif len(pieces)>=2:
            combined=combine_scores(raw[i],component,labels)
            effective[i]=combined['scores']
            traces.append(dict(mode='MULTI_REQUEST_SUPPORT',parts=pieces,component_probabilities=component.tolist(),support=combined['support'],component_labels=combined['component_labels']))
        else:
            traces.append(dict(mode='UNCHANGED',parts=pieces,component_probabilities=[],support=0.,component_labels=[]))
    candidates=dict(linear=rankings(question,raw,labels,'intent-linear-v1','CLASSIFIER_PROBABILITY_UNCALIBRATED',expected),
       composition=rankings(question,effective,labels,'intent-composition-support-v1','COMPOSITION_SUPPORT_UNCALIBRATED',expected))
    original=load_library(original_dir)
    matcher=IntentMatcher(original,encoder)
    candidates['original']=[matcher._rank(q,lookup[q],7,5) for q in question]
    results={name:{} for name in candidates}
    for name,predictions in candidates.items():
        for set_name in sorted({r['evaluation_set'] for r in cases}):
            indices=[i for i,r in enumerate(cases) if r['evaluation_set']==set_name]
            results[name][set_name]=report([cases[i] for i in indices],[predictions[i] for i in indices],labels)
    for name in ['linear','composition']:
        results[name]['regression_transitions']=transitions(results['original']['regression']['cases'],results[name]['regression']['cases'])
    changes={s:transitions(results['linear'][s]['cases'],results['composition'][s]['cases'])
             for s in ['development','regression','known_diagnostic','previous_check','controls']}
    target=next(r for r in results['composition']['regression']['cases'] if r['id']=='S5-T-038')
    evidence=[r for r in results['composition']['controls']['cases'] if r['id'].startswith('CONTROL-EVIDENCE-')]
    passes=(target['top1']=='MIXED'
        and not results['composition']['regression_transitions']['regressed']
        and not any(changes[s]['regressed'] for s in ['development','regression','known_diagnostic','previous_check'])
        and results['composition']['development']['metrics']['hits']['1']>=results['linear']['development']['metrics']['hits']['1']
        and all(r['top1']=='PERSON_ROLE' for r in evidence))
    for path,digest in hashes.items():
        if sha(ROOT/path)!=digest: raise ValueError('SOURCE_CHANGED_DURING_EXPERIMENT')
    write(OUT/'raw-probabilities.json',raw.tolist())
    write(OUT/'traces.json',traces)
    write(OUT/'results.json',results)
    write(OUT/'summary.json',dict(status='COMPLETED_OFFLINE_NOT_PRODUCTION_APPROVAL',passes_preregistered_gate=passes,
       target_T038=dict(gold=target['gold'],top1=target['top1']),changes_against_linear=changes,
       original_regressions=results['composition']['regression_transitions'],
       metrics={name:{s:r['metrics'] for s,r in sets.items() if s!='regression_transitions'} for name,sets in results.items()},
       runtime_unchanged=True,calibrated=False,legacy_threshold_applied_to_composition=False))
    print(json.dumps(dict(passes_gate=passes,target=target['top1'],changes=changes,
        hits={name:{s:r['metrics']['hits'] for s,r in sets.items() if s!='regression_transitions'} for name,sets in results.items()}),indent=2))


if __name__=='__main__': main()
