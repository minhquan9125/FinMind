"""Call the public API with the already-loaded BGE service; no embedding cache."""
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_classifier import classify_intent
from src.retrieval_orchestration.intent_v2_dataset import read_rows
from build_s5_intent_v2 import CACHE, OUT, sha, write


def benchmark(encoder, output=CACHE.parent / 'warm-latency'):
    """The caller supplies get_embedding_service(); this never loads a model."""
    import torch
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    rows = read_rows(CACHE / 'development.jsonl')
    sources = [ROOT / 'backend/src/retrieval_orchestration' / n for n in
               ['intent_v2_classifier.py', 'intent_v2_rules.py', 'intent_matching.py', 'intent_scoring.py']]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), *sources]}
    write(output / 'method.json', dict(status='FROZEN_BEFORE_MEASUREMENT',
        source_hashes=hashes, artifact_manifest_sha256=sha(OUT / 'manifest.json'),
        model_loaded_before_measurement=True, one_request_at_a_time=True,
        library_cached_not_query_vectors=True, sample='development110', blind_acceptance=False,
        python=platform.python_version(), platform=platform.platform(), processor=platform.processor(),
        torch=importlib.metadata.version('torch'), device=str(encoder.device), batch_size=encoder.batch_size,
        torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
        target_p95_ms=500))
    started = time.perf_counter()
    classify_intent('FinMind', embedder=encoder, artifact_path=OUT)
    warmup_ms = 1000 * (time.perf_counter() - started)
    measured = []
    for i, row in enumerate(rows):
        started = time.perf_counter()
        result = classify_intent(row['text'], embedder=encoder, artifact_path=OUT)
        elapsed = 1000 * (time.perf_counter() - started)
        measured.append(dict(id=row['id'], gold=row['intent_label'], elapsed_ms=elapsed, result=result))
        if (i + 1) % 22 == 0:
            print('BGE_V2_BENCH', i + 1, '/', len(rows), flush=True)
    for name, digest in hashes.items():
        if sha(ROOT / name) != digest:
            raise ValueError('SOURCE_CHANGED_DURING_BENCHMARK')
    latencies = [r['elapsed_ms'] for r in measured]
    summary = dict(status='MEASURED_DEVELOPMENT_NOT_BLIND', requests=len(measured),
        warmup_ms=warmup_ms, p50_ms=float(np.percentile(latencies, 50)),
        p95_ms=float(np.percentile(latencies, 95)), max_ms=max(latencies),
        correct=sum(r['gold'] == r['result']['resolution']['intent_label'] for r in measured),
        encoder_object_id=id(encoder), api_module=str(classify_intent.__module__),
        query_vectors_recomputed=True, model_cold_load_excluded=True, network_or_database_used=False)
    summary['p95_target_met'] = summary['p95_ms'] <= 500
    write(output / 'requests.json', measured)
    write(output / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary
