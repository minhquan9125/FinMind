"""Freeze additive candidates using cached real vectors; do not open later-check."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.retrieval_orchestration.intent_additive import append_library,selection_key
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from src.retrieval_orchestration.intent_experiment import transitions
from run_s5_intent_experiment import measure,write,read_rows

DATA=ROOT/'docs/sprint5/intent-experiment-v2'
CACHE=ROOT/'outputs/s5_intent_experiment_20261111/run01'
DEFAULT=ROOT/'outputs/s5_intent_additive_20261112'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    output=parser.parse_args().output
    if output.exists():
        raise FileExistsError(output)
    for path,digest in json.loads((CACHE/'method.json').read_text())['input_hashes'].items():
        if sha(ROOT/path)!=digest:
            raise ValueError('PREVIOUS_EXPERIMENT_SOURCE_CHANGED: '+path)
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    original=load_library(original_dir)
    files=[*original_dir.iterdir(),CACHE/'embedded-texts.json',CACHE/'experiment-vectors.npy',
           DATA/'library-draft.jsonl',DATA/'development.jsonl',DATA/'known-diagnostic.jsonl',
           DATA/'manifest.json',ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl',
           ROOT/'docs/sprint5/S5-WBS04.1-additive-plan.md',Path(__file__),
           ROOT/'backend/src/retrieval_orchestration/intent_additive.py',
           ROOT/'backend/src/retrieval_orchestration/intent_matching.py',
           ROOT/'backend/scripts/run_s5_intent_experiment.py',
           ROOT/'backend/src/retrieval_orchestration/intent_experiment.py']
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in files if p.is_file()}
    texts=json.loads((CACHE/'embedded-texts.json').read_text(encoding='utf-8'))
    values=np.load(CACHE/'experiment-vectors.npy',allow_pickle=False)
    if values.shape!=(len(texts),1024) or not np.isfinite(values).all():
        raise ValueError('INVALID_VECTOR_CACHE')
    lookup=dict(zip(texts,values))
    draft=read_rows(DATA/'library-draft.jsonl')
    components=[['PERSON_ROLE','REPORT_CONTENT'],['NUMERIC','NEWS'],['ENTITY_RELATION','TREND'],['REPORT_CONTENT','NEWS']]
    for row in draft:
        row['component_intents']=components[int(row['family_id'].rsplit('-',1)[1])-1] if row['intent_label']=='MIXED' else []
    focused=[r for r in draft if r['intent_label'] in ['PERSON_ROLE','ENTITY_RELATION','MIXED']]
    variants=dict(original=original,
        add_all=append_library(original,draft,np.stack([lookup[r['text']] for r in draft]),'add-all-draft1'),
        add_focused=append_library(original,focused,np.stack([lookup[r['text']] for r in focused]),'add-focused-draft1'))
    sets=dict(development=read_rows(DATA/'development.jsonl'),
              regression=read_rows(ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl'),
              known_diagnostic=read_rows(DATA/'known-diagnostic.jsonl'))
    if {r['text'].casefold() for r in variants['add_all'].rows}&{r['text'].casefold() for rows in sets.values() for r in rows}:
        raise ValueError('EXACT_TRAIN_EVAL_OVERLAP')
    output.mkdir(parents=True)
    write(output/'method.json',dict(status='FROZEN_BEFORE_SCORING',input_hashes=hashes,
          variants=['original','add_all','add_focused'],cached_real_embeddings=True,
          threshold=.65,gap=.08,payload_groups=3,later_check_scored=False,
          selection_rule='S5-WBS04.1-additive-plan.md'))
    encoder=SimpleNamespace(model_name=original.manifest['model']['name'],revision=original.manifest['model']['revision'])
    results={}
    for name,library in variants.items():
        matcher=IntentMatcher(library,encoder)
        results[name]={set_name:measure(cases,[matcher._rank(r['text'],lookup[r['text']],7,5) for r in cases])
                       for set_name,cases in sets.items()}
        if name!='original':
            dest=output/name
            dest.mkdir()
            (dest/'library.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in library.rows),encoding='utf-8',newline='\n')
            np.save(dest/'vectors.npy',library.vectors,allow_pickle=False)
            write(dest/'manifest.json',dict(library.manifest,
                  files={n:sha(dest/n) for n in ['library.jsonl','vectors.npy']},
                  old_prefix_rows=len(original.rows),row_count=len(library.rows)))
    results_baseline=results['original']
    if results_baseline['regression']['metrics']['hits']!={'1':22,'3':41,'5':46}:
        raise ValueError('BASELINE_NOT_REPRODUCED')
    candidates=[]
    for name in ['add_all','add_focused']:
        result=results[name]
        changes=transitions(results_baseline['regression']['cases'],result['regression']['cases'])
        result['regression_transitions']=changes
        dev=result['development']['metrics']
        reg=result['regression']['metrics']
        eligible=(dev['hits']['1']>results_baseline['development']['metrics']['hits']['1']
                  and not changes['regressed'] and all(result[s]['metrics']['accepted_wrong_route']<=results_baseline[s]['metrics']['accepted_wrong_route']
                                                     for s in ['development','regression']))
        candidates.append(dict(name=name,eligible=eligible,wrong_regression=reg['accepted_wrong_route'],
             wrong_dev=dev['accepted_wrong_route'],regressed=len(changes['regressed']),
             dev_hits=dev['hits']['1'],regression_hits=reg['hits']['1'],rows=len(variants[name].rows)))
    selected=min(candidates,key=selection_key)
    for path,digest in hashes.items():
        if sha(ROOT/path)!=digest:
            raise ValueError('SOURCE_CHANGED_DURING_SCORING')
    write(output/'results.json',results)
    write(output/'selection.json',dict(status='FROZEN_BEFORE_LATER_CHECK',selected=selected,
         candidates=candidates,method_sha256=sha(output/'method.json'),results_sha256=sha(output/'results.json'),
         candidate_manifest_sha256=sha(output/selected['name']/'manifest.json'),
         original_manifest_sha256=sha(original_dir/'manifest.json'),
         later_file_sha256=json.loads((DATA/'manifest.json').read_text())['files']['later-check-UNSCORED.jsonl']['sha256'],
         policy_simulation_not_e2e=True,do_not_promote_without_quality_confirmation=True))
    print(json.dumps(dict(candidates=candidates,selected=selected),indent=2))


if __name__=='__main__':
    main()
