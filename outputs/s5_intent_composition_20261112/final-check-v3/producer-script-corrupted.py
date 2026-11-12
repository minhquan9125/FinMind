"""Freeze and run one new check of the fixed resolution; no fitting/calibration."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_composition import requests
from src.retrieval_orchestration.intent_request_objectives import resolve_objectives
from src.retrieval_orchestration.intent_scoring import classifier_probabilities,rankings
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from prepare_s5_intent_scorer import sha,write,read_rows
from run_s5_intent_consensus import stats

PARENT=ROOT/'outputs/s5_intent_composition_20261112'
OUT=PARENT/'final-check-v3'
TEMPLATES={'NUMERIC': ['T? l? n? tr?n v?n ch? s? h?u {c} cu?i n?m 2019 l? bao nhi?u?',
             'Cho bi?t l?i nhu?n gi? l?i c?a {c} t?i 31/12/2019.'],
 'REPORT_CONTENT': ['BCTN {c} n?m 2019 m? t? ch?nh s?ch ph?t tri?n nh?n l?c ra sao?',
                    'Gi?i th?ch chi?n l??c m? r?ng th? tr??ng tr?nh b?y trong b?o c?o th??ng ni?n {c} '
                    'n?m 2019.'],
 'NEWS': ['T?m c?c b?i tin v? {c} c?ng b? chia c? t?c trong th?ng 06/2019.',
          'H?y t?m t?t b?i b?o {c} kh?nh th?nh c? s? s?n xu?t ??ng ng?y 15/07/2019.'],
 'PERSON_ROLE': ['Ai gi? ch?c Gi?m ??c t?i ch?nh {c} t?i cu?i n?m 2019?',
                 'Theo BCTN {c} 2019, ai l? Ch? t?ch H?QT? Tr?ch c?u l?m b?ng ch?ng cho c?u tr? l?i.'],
 'ENTITY_RELATION': ['C?ng ty m? c?a {c} t?i 31/12/2019 l? ??n v? n?o?',
                     'Li?t k? doanh nghi?p h?p t?c v?i {c} trong d? ?n tri?n khai n?m 2019.'],
 'TREND': ['??nh gi? chi?u h??ng kh? n?ng sinh l?i {c} qua giai ?o?n 2016?2019.',
           'Nh?n ??nh ?? t?ng gi? c? phi?u {c} trong qu? II/2019 c? b?n v?ng kh?ng?'],
 'MIXED': ['Ai gi? ch?c Gi?m ??c t?i ch?nh {c} cu?i n?m 2019? BCTN {c} m? t? ch?nh s?ch ph?t tri?n nh?n '
           'l?c ra sao?',
           'Cho bi?t l?i nhu?n gi? l?i {c} cu?i n?m 2019 r?i t?m c?c b?i tin chia c? t?c {c} th?ng '
           '06/2019.']}


def main():
    if OUT.exists(): raise FileExistsError('NEW_CHECK_ALREADY_ATTEMPTED')
    scorer=ROOT/'outputs/s5_intent_scorer_20261112'
    fit=ROOT/json.loads((scorer/'fit-location.json').read_text())['output']
    parent_summary=json.loads((PARENT/'objectives-v3/summary.json').read_text())
    if not parent_summary['passes_gate']: raise ValueError('DEVELOPMENT_GATE_NOT_PASSED')
    metadata=json.loads((scorer/'method.json').read_text())
    labels=json.loads((fit/'summary.json').read_text())['labels']
    parameters=np.load(fit/'parameters.npz',allow_pickle=False)
    cases=[dict(id=f'FINAL-{label}-{i}-{company}',text=text.format(c=company),intent_label=label,
             family_id=f'FINAL-{label}-{i}',company=company,split='FINAL_CHECK_ONLY')
           for label,phrases in TEMPLATES.items() for i,text in enumerate(phrases,1) for company in ['DPM','VRE']]
    training=read_rows(scorer/'training.jsonl')
    if {r['text'].casefold() for r in cases}&{r['text'].casefold() for r in training}: raise ValueError('TEST_TRAIN_OVERLAP')
    parts=[requests(r['text']) for r in cases]
    texts=sorted({r['text'] for r in cases}|{q for spans in parts for q in spans})
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    watched=[fit/'parameters.npz',PARENT/'objectives-v3/method.json',PARENT/'objectives-v3/summary.json',
             ROOT/'backend/src/retrieval_orchestration/intent_request_consensus.py',
             ROOT/'backend/src/retrieval_orchestration/intent_request_objectives.py',
             ROOT/'backend/src/retrieval_orchestration/intent_composition.py',
             ROOT/'backend/src/retrieval_orchestration/intent_scoring.py',Path(__file__),*original_dir.iterdir()]
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in watched if p.is_file()}
    OUT.mkdir()
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_CHECK',source_hashes=hashes,rows=28,
           authored_by_same_agent=True,blind_test=False,no_fit=True,no_calibration=True,
           model=metadata['model'],confidence=None,one_check_after_frozen_development=True))
    write(OUT/'cases.json',cases); write(OUT/'request-parts.json',parts); write(OUT/'texts.json',texts)
    encoder=get_embedding_service()
    expected=metadata['model']
    if (encoder.model_name,encoder.revision)!=(expected['name'],expected['revision']): raise ValueError('MODEL_MISMATCH')
    print(f'Encoding {len(texts)} texts for 28 frozen final cases; no fitting.',flush=True)
    vectors=np.asarray(encoder.embed_texts(texts),dtype=np.float32)
    if vectors.shape!=(len(texts),1024) or not np.isfinite(vectors).all(): raise ValueError('INVALID_VECTORS')
    np.save(OUT/'vectors.npy',vectors,allow_pickle=False)
    lookup=dict(zip(texts,vectors))
    raw=classifier_probabilities(np.stack([lookup[r['text']] for r in cases]),parameters['coefficients'],parameters['intercepts'])
    original=IntentMatcher(load_library(original_dir),encoder)
    baseline=[original._rank(r['text'],lookup[r['text']],7,5) for r in cases]
    raw_ranking=rankings([r['text'] for r in cases],raw,labels,'intent-linear-v1','CLASSIFIER_PROBABILITY_UNCALIBRATED',expected)
    results=[]
    for i,(case,spans) in enumerate(zip(cases,parts)):
        component=classifier_probabilities(np.stack([lookup[q] for q in spans]),parameters['coefficients'],parameters['intercepts']) if spans!=[case['text']] else []
        decision=resolve_objectives(raw[i],component,labels,spans)
        results.append(dict(id=case['id'],question=case['text'],gold=case['intent_label'],
               final_label=decision['intent_label'],resolution=decision,base_ranking=raw_ranking[i],
               original_ranking=baseline[i],parts=spans,
               component_probabilities=np.asarray(component).tolist()))
    metrics={name:stats([dict(r,final_label=(r['original_ranking']['groups'][0]['intent_label'] if name=='original'
                         else r['base_ranking']['groups'][0]['intent_label'] if name=='linear' else r['final_label'])) for r in results],labels)
             for name in ['original','linear','consensus']}
    old_correct_to_wrong=[r['id'] for r in results if r['base_ranking']['groups'][0]['intent_label']==r['gold']!=r['final_label']]
    for name,digest in hashes.items():
        if sha(ROOT/name)!=digest: raise ValueError('SOURCE_CHANGED_DURING_CHECK')
    write(OUT/'results.json',results)
    write(OUT/'summary.json',dict(status='COMPLETED_ONE_FINAL_CHECK_NOT_E2E_APPROVAL',metrics=metrics,
         linear_correct_to_wrong=old_correct_to_wrong,confidence=None,
         calibrated=False,runtime_unchanged=True,no_legacy_threshold_applied=True))
    print(json.dumps(dict(correct={name:m['correct'] for name,m in metrics.items()},linear_correct_to_wrong=old_correct_to_wrong),indent=2))


if __name__=='__main__': main()
