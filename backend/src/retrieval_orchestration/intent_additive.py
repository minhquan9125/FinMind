"""Offline additive experiments; official artifacts and routing are untouched."""
import numpy as np
from .intent_library import IntentLibrary


def append_library(original, extra_rows, extra_vectors, version):
    rows=tuple(original.rows)+tuple(extra_rows)
    ids=[r['id'] for r in rows]
    texts=[r['text'].strip().casefold() for r in rows]
    if len(set(ids))!=len(ids) or len(set(texts))!=len(texts):
        raise ValueError('DUPLICATE_LIBRARY_ROW')
    values=np.asarray(extra_vectors,dtype=np.float32)
    if (values.shape!=(len(extra_rows),original.vectors.shape[1])
            or not np.isfinite(values).all()
            or not np.allclose(np.linalg.norm(values,axis=1),1,atol=1e-4,rtol=0)):
        raise ValueError('INVALID_EXTRA_VECTORS')
    manifest=dict(status='EXPERIMENTAL_DRAFT',model=dict(original.manifest['model']),
                  library_version=version,dataset_version='intent-additive-draft1',
                  label_schema_version=original.manifest['label_schema_version'],
                  original_library_version=original.manifest['library_version'])
    return IntentLibrary(rows,np.concatenate([original.vectors,values]),manifest)


def selection_key(candidate):
    return (not candidate['eligible'],candidate['wrong_regression'],candidate['wrong_dev'],
            candidate['regressed'],-candidate['dev_hits'],-candidate['regression_hits'],
            candidate['rows'],candidate['name'])
