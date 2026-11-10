"""Independent real-model audit: no changes to the frozen run or ranking policy."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher

run = root / 'outputs/s5_wbs041_20261110/run01'
destination = root / 'outputs/s5_wbs041_review_20261111'
destination.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
before = {name: sha(run / name) for name in ('method.json', 'test-input.jsonl', 'results.jsonl', 'summary.json')}
method = json.loads((run / 'method.json').read_text(encoding='utf-8'))
cases = [json.loads(line) for line in (run / 'test-input.jsonl').read_text(encoding='utf-8').splitlines()]
stored = [json.loads(line) for line in (run / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
assert len(cases) == len(stored) == 56
assert before['test-input.jsonl'] == method['test_sha256']
for case, record in zip(cases, stored):
    assert case['id'] == record['id'] and case['text'] == record['ranking']['question']
encoder = get_embedding_service()
directory = root / 'outputs/s5_wbs033_20261110/intent-library-v1'
library = load_library(directory, expected_model=encoder.model_name, expected_revision=encoder.revision)
assert sha(directory / 'manifest.json') == method['library_manifest_sha256']
print('Independent audit: re-encoding 56 queries; frozen library and run01 are read-only.', flush=True)
started = time.perf_counter()
query_vectors = np.asarray(encoder.embed_texts([r['text'] for r in cases]), dtype=np.float64)
assert query_vectors.shape == (56, 1024) and np.isfinite(query_vectors).all()
values = library.vectors.astype(np.float64)
norms = np.linalg.norm(values, axis=1)
labels = list(summary['per_label'])
indices = {label: [i for i, row in enumerate(library.rows) if row['intent_label'] == label] for label in labels}
independent, confusion, largest_difference = [], Counter(), 0.0
hits = top3 = total = 0
for case, query, record in zip(cases, query_vectors, stored):
    # Independent expression: raw dot products divided by both norms.
    cosines = np.einsum('ij,j->i', values, query) / (norms * np.linalg.norm(query))
    best = {label: max(float(cosines[i]) for i in members) for label, members in indices.items()}
    ordered = sorted(labels, key=lambda label: (-best[label], label))
    for group in record['ranking']['groups']:
        difference = abs(group['score'] - best[group['intent_label']])
        largest_difference = max(largest_difference, difference)
        assert difference < 1e-5, (case['id'], difference)
    assert ordered == [g['intent_label'] for g in record['ranking']['groups']], case['id']
    if case['intent_label'] is not None:
        total += 1
        hits += ordered[0] == case['intent_label']
        top3 += case['intent_label'] in ordered[:3]
        confusion[case['intent_label'], ordered[0]] += 1
    independent.append(dict(id=case['id'], groups=[dict(intent_label=label, score=best[label]) for label in ordered]))
f1s = []
for label in labels:
    tp = confusion[label, label]
    fp = sum(n for (gold, pred), n in confusion.items() if pred == label and gold != label)
    fn = sum(n for (gold, pred), n in confusion.items() if gold == label and pred != label)
    f1s.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
assert (hits, top3, total) == (22, 41, 47)
assert abs(sum(f1s)/len(labels) - summary['macro_f1']) < 1e-12
single_checks = []
for index in (0, 27, 55):
    vector = np.asarray(encoder.embed_query(cases[index]['text']), dtype=np.float64)
    difference = float(np.abs(vector - query_vectors[index]).max())
    assert np.allclose(vector, query_vectors[index], atol=1e-5, rtol=1e-5)
    single_checks.append(dict(id=cases[index]['id'], max_absolute_difference=difference))
live_result = IntentMatcher(library, encoder).match(cases[0]['text'], top_groups=7)
assert [g['intent_label'] for g in live_result['groups']] == [g['intent_label'] for g in stored[0]['ranking']['groups']]
assert all(abs(a['score'] - b['score']) < 1e-5 for a, b in zip(live_result['groups'], stored[0]['ranking']['groups']))
assert before == {name: sha(run / name) for name in before}
load_library(directory, expected_model=encoder.model_name, expected_revision=encoder.revision)
assert sha(directory / 'manifest.json') == method['library_manifest_sha256']
report = dict(status='PASS', audit_date='2026-11-11', real_model_questions=56,
              model_name=encoder.model_name, revision=encoder.revision,
              cosine_recomputed_independently=True, all_group_rankings_reproduced=True,
              max_group_score_difference=largest_difference,
              batch_vs_single_real_encoder=single_checks,
              single_match_api_verified=True, top1_correct=hits, top3_correct=top3,
              labeled_cases=total, null_cases=9, macro_f1=sum(f1s)/len(labels),
              library_and_run01_unchanged=True, elapsed_seconds=time.perf_counter()-started,
              run01_file_hashes=before)
(destination / 'real-model-audit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
(destination / 'independent-rankings.json').write_text(json.dumps(independent, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(report, indent=2))
