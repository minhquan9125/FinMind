"""Real-model regression and CPU profiling using an injected, loaded encoder."""
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from src.retrieval_orchestration.intent_v2_dataset import read_rows
from src.retrieval_orchestration.intent_matching import summarize_evaluation
from build_s5_intent_v2 import CACHE, OUT, sha, write
from evaluate_s5_intent_v2 import FrozenEncoder


def regression(encoder, output=CACHE.parent / 'legacy-regression'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'docs/sprint5/intent-dataset-v1/test.jsonl'
    # Only the 47 pre-existing labeled rows. Unknown rows keep their original status.
    rows = [dict(r) for r in read_rows(source) if r['intent_label'] is not None]
    for row in rows:
        if row['intent_label'] == 'TREND':
            row['intent_label'] = 'ANALYSIS'
        elif row['intent_label'] == 'NUMERIC' and row['source_types'] == ['PRICE']:
            row['intent_label'] = 'PRICE'
        row['component_intents'] = ['ANALYSIS' if c == 'TREND' else c for c in row['component_intents']]
    write(output / 'method.json', dict(status='FROZEN_BEFORE_MEASUREMENT',
        runner_sha256=sha(__file__), source_sha256=sha(source),
        label_mapping='TREND->ANALYSIS; NUMERIC with sole PRICE source->PRICE',
        labeled_cases=len(rows), unlabeled_cases_excluded=9, historical_seen_not_blind=True,
        original_gold_file_unchanged=True))
    values = encoder.embed_texts([r['text'] for r in rows])
    np.save(output / 'query-vectors.npy', np.asarray(values, dtype=np.float32), allow_pickle=False)
    model = json.loads((OUT / 'library/manifest.json').read_text(encoding='utf-8'))['model']
    classifier = IntentClassifier.load(OUT, FrozenEncoder(rows, values, model))
    results = [dict(id=r['id'], gold=r['intent_label'], gold_components=r['component_intents'],
                    **classifier.classify(r['text'])) for r in rows]
    predictions = [dict(groups=[dict(intent_label=r['resolution']['intent_label'])]) for r in results]
    summary = summarize_evaluation(rows, predictions, classifier.manifest['labels'])
    write(output / 'cases.json', rows)
    write(output / 'results.json', results)
    write(output / 'summary.json', summary)
    print('REGRESSION', summary['top1_accuracy'], summary['wrong_case_ids'], flush=True)


def profile_cpu(encoder, output=CACHE.parent / 'cpu-profile'):
    import torch
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = read_rows(CACHE / 'development.jsonl')
    sample = [r for i, r in enumerate(rows) if i % 10 in [0, 5]]
    original = torch.get_num_threads()
    write(output / 'method.json', dict(status='FROZEN_BEFORE_MEASUREMENT',
        sample_ids=[r['id'] for r in sample], threads=[1, 2, 4], original_threads=original,
        device=str(encoder.device), cuda_available=torch.cuda.is_available(),
        runner_sha256=sha(__file__), target_p95_ms=500, exploratory_not_acceptance=True))
    results = []
    try:
        for threads in [1, 2, 4]:
            torch.set_num_threads(threads)
            encoder.embed_query('FinMind')
            times = []
            for row in sample:
                started = time.perf_counter()
                encoder.embed_query(row['text'])
                times.append(1000 * (time.perf_counter() - started))
            item = dict(threads=threads, p50_ms=float(np.percentile(times, 50)),
                        p95_ms=float(np.percentile(times, 95)), embedding_only_ms=times)
            results.append(item)
            print('CPU_PROFILE', threads, item['p50_ms'], item['p95_ms'], flush=True)
    finally:
        torch.set_num_threads(original)
    write(output / 'results.json', results)
    return results
