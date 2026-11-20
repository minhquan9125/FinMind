"""Freeze and encode v2 data with the shared BGE service; no fitting or routing."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.retrieval_orchestration.intent_v2_dataset import read_rows, validate_dataset

DATA = ROOT / 'docs/sprint5/intent-v2'
SCHEMA = ROOT / 'docs/sprint5/intent-labels.v2.json'
OUT = ROOT / 'outputs/s5_intent_v2_20261113/vector-cache'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def encode(encoder, output=OUT):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Use a new attempt path: ' + str(output))
    summary = validate_dataset(DATA, SCHEMA)
    if encoder.model_name != 'BAAI/bge-m3' or encoder.revision != '5617a9f61b028005a4858fdac845db406aefb181':
        raise ValueError('MODEL_OR_REVISION_MISMATCH')
    paths = [SCHEMA, DATA / 'manifest.json', DATA / 'library.jsonl', DATA / 'development.jsonl',
             ROOT / 'backend/src/documents/embeddings.py', Path(__file__)]
    snapshots = {p: p.read_bytes() for p in paths}
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(raw).hexdigest() for p, raw in snapshots.items()}
    output.mkdir(parents=True)
    write(output / 'method.json', dict(status='FROZEN_BEFORE_ENCODING', input_hashes=hashes,
          model=dict(name=encoder.model_name, revision=encoder.revision, dimension=1024),
          created_at=datetime.now(timezone.utc).isoformat(), data_summary=summary,
          packages={p: importlib.metadata.version(p) for p in ['numpy', 'torch', 'sentence-transformers']},
          blind_acceptance_available=False, no_fit=True))
    elapsed, files = {}, {}
    for split in ['library', 'development']:
        rows = read_rows(DATA / (split + '.jsonl'))
        (output / (split + '.jsonl')).write_bytes(snapshots[DATA / (split + '.jsonl')])
        blocks, started = [], time.perf_counter()
        for start in range(0, len(rows), 64):
            block = np.asarray(encoder.embed_texts([r['text'] for r in rows[start:start + 64]]), dtype=np.float32)
            if block.shape != (len(rows[start:start + 64]), 1024) or not np.isfinite(block).all():
                raise ValueError('INVALID_ENCODER_OUTPUT')
            blocks.append(block)
            print(f'BGE v2 {split}: {min(start + 64, len(rows))}/{len(rows)}', flush=True)
        values = np.concatenate(blocks)
        if not np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-4, rtol=0):
            raise ValueError('VECTORS_NOT_NORMALIZED')
        np.save(output / (split + '-vectors.npy'), values, allow_pickle=False)
        elapsed[split] = time.perf_counter() - started
        for name in [split + '.jsonl', split + '-vectors.npy']:
            files[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    if any(p.read_bytes() != raw for p, raw in snapshots.items()):
        raise ValueError('SOURCE_CHANGED_DURING_ENCODING')
    write(output / 'completed.json', dict(status='PASS', files=files, seconds=elapsed,
          input_hashes=hashes, no_fit=True, development_vectors_not_library_members=True))
    print('BGE v2 cache completed', elapsed, flush=True)
    return output


if __name__ == '__main__':
    from src.documents.embeddings import get_embedding_service
    encode(get_embedding_service())
