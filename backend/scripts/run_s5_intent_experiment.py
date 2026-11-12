"""Offline 2x2 experiment; never imports production policy or scores later-check."""
from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_library import IntentLibrary, load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from src.retrieval_orchestration.intent_experiment import mask_tickers, policy_observation, transitions, ROUTES

DATA = ROOT / 'docs/sprint5/intent-experiment-v2'
OUT = ROOT / 'outputs/s5_intent_experiment_20261111/run01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def measure(cases, rankings):
    details = []
    for case, ranking in zip(cases, rankings):
        groups, gold = ranking['groups'], case['intent_label']
        labels = [g['intent_label'] for g in groups]
        score, gap = groups[0]['score'], groups[0]['score'] - groups[1]['score']
        decision = policy_observation(labels[0], score, gap)
        details.append(dict(id=case['id'], gold=gold, top1=labels[0],
                            gold_rank=labels.index(gold)+1 if gold else None,
                            expected_route=ROUTES[gold] if gold else None,
                            decision=decision, score=score, gap=gap, ranking=ranking))
    labeled = [r for r in details if r['gold']]
    accepted = [r for r in labeled if r['decision'] != 'NEED_FALLBACK']
    wrong = [r['id'] for r in accepted if r['decision'] != r['expected_route']]
    groups = defaultdict(list)
    for case, row in zip(cases, details):
        if case.get('company'):
            groups[case['family_id']].append(row)
    metrics = dict(total=len(details), labeled=len(labeled),
        hits={str(k): sum(r['gold_rank']<=k for r in labeled) for k in [1,3,5]},
        per_label={label: dict(total=sum(r['gold']==label for r in labeled),
            hits={str(k): sum(r['gold']==label and r['gold_rank']<=k for r in labeled) for k in [1,3,5]}) for label in ROUTES},
        accepted=len(accepted), fallback=len(labeled)-len(accepted),
        accepted_correct_route=len(accepted)-len(wrong), accepted_wrong_route=len(wrong),
        accepted_wrong_route_ids=wrong, accepted_coverage=len(accepted)/len(labeled),
        wrong_route_rate_among_accepted=len(wrong)/len(accepted) if accepted else None,
        single_misread_as_mixed=[r['id'] for r in labeled if r['gold']!='MIXED' and r['top1']=='MIXED'],
        mixed_misread_as_single=[r['id'] for r in labeled if r['gold']=='MIXED' and r['top1']!='MIXED'],
        company_control_families=len(groups),
        company_changed_top1=[f for f, rows in groups.items() if len({r['top1'] for r in rows})>1],
        company_all_correct=[f for f, rows in groups.items() if all(r['gold']==r['top1'] for r in rows)],
        null_policy_observations=[dict(id=r['id'], decision=r['decision']) for r in details if not r['gold']])
    return dict(metrics=metrics, cases=details)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(output)
    manifest_path = DATA/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    # Intentionally never read later-check file contents in this runner.
    consumed = ['library-draft.jsonl', 'development.jsonl']
    for name in consumed:
        if sha(DATA/name) != manifest['files'][name]['sha256']:
            raise ValueError('EXPERIMENT_INPUT_CHANGED')
    library = load_library(ROOT/'outputs/s5_wbs033_20261110/intent-library-v1')
    original_dir = ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    old_run = ROOT/'outputs/s5_wbs041_20261110/run01'
    watched = [*original_dir.iterdir(), *old_run.iterdir(), manifest_path,
               *(DATA/name for name in consumed), ROOT/'docs/sprint5/S5-WBS04.1-improvement-plan.md',
               ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl', DATA/'known-diagnostic.jsonl']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in watched if p.is_file()}
    draft = read_rows(DATA/'library-draft.jsonl')
    mixed_components = [['PERSON_ROLE','REPORT_CONTENT'],['NUMERIC','NEWS'],
                        ['ENTITY_RELATION','TREND'],['REPORT_CONTENT','NEWS']]
    for row in draft:
        row['component_intents'] = (mixed_components[int(row['family_id'].rsplit('-',1)[1])-1]
                                    if row['intent_label']=='MIXED' else [])
    sets = dict(development=read_rows(DATA/'development.jsonl'),
                regression=read_rows(ROOT/'docs/sprint5/intent-dataset-v1/test.jsonl'),
                known_diagnostic=read_rows(DATA/'known-diagnostic.jsonl'))
    assert len(draft)==112 and len(sets['development'])==84
    train_text = {r['text'].casefold() for r in draft}
    if any(r['text'].casefold() in train_text for cases in sets.values() for r in cases):
        raise ValueError('EXACT_TRAIN_EVALUATION_OVERLAP')
    output.mkdir(parents=True)
    write(output/'method.json', dict(status='FROZEN_BEFORE_INFERENCE', plan='docs/sprint5/S5-WBS04.1-improvement-plan.md',
        input_hashes=hashes, threshold=.65, gap=.08, payload_groups=3,
        reported_groups=7, variants=['original','original_masked','balanced','balanced_masked'],
        later_check_scored=False, policy_simulation_not_actual_wbs042=True))
    encoder = get_embedding_service()
    if (encoder.model_name, encoder.revision)!=(library.manifest['model']['name'],library.manifest['model']['revision']):
        raise ValueError('MODEL_MISMATCH')
    variants = [('original',library.rows,False),('original_masked',library.rows,True),
                ('balanced',draft,False),('balanced_masked',draft,True)]
    texts = set()
    for name, rows, masked in variants:
        transform = mask_tickers if masked else lambda s:s
        if name!='original':
            texts.update(transform(r['text']) for r in rows)
        texts.update(transform(r['text']) for cases in sets.values() for r in cases)
    texts = sorted(texts)
    write(output/'embedded-texts.json', texts)
    print(f'Embedding {len(texts)} unique texts; later-check is not loaded.',flush=True)
    started = time.perf_counter()
    vectors = np.asarray(encoder.embed_texts(texts), dtype=np.float32)
    if vectors.shape!=(len(texts),1024) or not np.isfinite(vectors).all():
        raise ValueError('INVALID_REAL_VECTORS')
    np.save(output/'experiment-vectors.npy',vectors,allow_pickle=False)
    lookup = dict(zip(texts,vectors))
    results = {}
    for name, rows, masked in variants:
        transform = mask_tickers if masked else lambda s:s
        rows = tuple(dict(r,text=transform(r['text'])) for r in rows)
        if name=='original':
            active = library
        else:
            metadata = dict(library.manifest, library_version='EXPERIMENT-'+name)
            active = IntentLibrary(rows,np.stack([lookup[r['text']] for r in rows]),metadata)
        matcher = IntentMatcher(active,encoder)
        results[name] = {}
        for set_name, cases in sets.items():
            rankings = [matcher._rank(transform(r['text']),lookup[transform(r['text'])],7,5) for r in cases]
            results[name][set_name] = measure(cases,rankings)
        print(name, json.dumps({s:r['metrics']['hits'] for s,r in results[name].items()}),flush=True)
    for name in results:
        results[name]['regression_transitions'] = transitions(results['original']['regression']['cases'],
                                                            results[name]['regression']['cases'])
    baseline = results['original']
    candidates = [name for name, result in results.items() if name!='original'
                  and result['development']['metrics']['hits']['1']>baseline['development']['metrics']['hits']['1']
                  and all(result[s]['metrics']['accepted_wrong_route']<=baseline[s]['metrics']['accepted_wrong_route']
                          for s in ['development','regression'])]
    for path, checksum in hashes.items():
        if sha(ROOT/path)!=checksum:
            raise ValueError('SOURCE_CHANGED_DURING_EXPERIMENT')
    write(output/'results.json',results)
    write(output/'summary.json',dict(status='COMPLETED_EXPERIMENT_NOT_APPROVED',elapsed_seconds=time.perf_counter()-started,
          candidates_for_review=candidates, later_check_scored=False, baseline_unchanged=True,
          metrics={name:{s:result[s]['metrics'] for s in sets} for name,result in results.items()},
          regression_transitions={name:result['regression_transitions'] for name,result in results.items()}))


if __name__=='__main__':
    main()
