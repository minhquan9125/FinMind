"""Use the verified project model cache without a second download on web startup."""
import sys
from types import SimpleNamespace

from src.documents import embeddings


def test_project_cache_is_used_offline_when_complete(tmp_path, monkeypatch):
    monkeypatch.delenv('HF_HUB_CACHE', raising=False)
    monkeypatch.setattr(embeddings, 'PROJECT_MODEL_CACHE', tmp_path)
    snapshot = tmp_path / 'models--BAAI--bge-m3' / 'snapshots' / 'test-revision'
    snapshot.mkdir(parents=True)
    (snapshot / 'config.json').write_text('{}')
    (snapshot / 'pytorch_model.bin').write_bytes(b'fixture')
    calls = []
    class FakeModel:
        def __init__(self, *args, **kwargs): calls.append(kwargs)
    monkeypatch.setitem(sys.modules, 'sentence_transformers', SimpleNamespace(SentenceTransformer=FakeModel))
    service = embeddings.EmbeddingService('BAAI/bge-m3', revision='test-revision')
    service._load()
    service._load()
    assert len(calls) == 1
    assert calls[0]['local_files_only'] is True
    assert calls[0]['cache_folder'] == str(tmp_path)


def test_shared_embedding_encoder_serializes_classifier_and_search_threads():
    from concurrent.futures import ThreadPoolExecutor
    import time
    import numpy as np
    class Encoder:
        active=0
        maximum=0
        def encode(self,texts,**kwargs):
            self.active+=1
            self.maximum=max(self.maximum,self.active)
            time.sleep(.015)
            self.active-=1
            return np.ones((len(texts),1024))
    service=embeddings.EmbeddingService('BAAI/bge-m3',revision='test')
    service._model=Encoder()
    with ThreadPoolExecutor(max_workers=4) as pool:
        vectors=list(pool.map(service.embed_query,['one','two','three','four']))
    assert service._model.maximum==1
    assert all(len(vector)==1024 for vector in vectors)


def test_identical_classifier_and_retrieval_queries_reuse_vectors_without_mutable_aliasing():
    import numpy as np
    class Encoder:
        calls=0
        def encode(self,texts,**kwargs):
            self.calls+=1
            return np.ones((len(texts),1024))
    service=embeddings.EmbeddingService('BAAI/bge-m3',revision='fixed-test-revision')
    service._model=Encoder()
    first=service.embed_texts(['same question'])
    first[0][0]=999
    second=service.embed_query('same question')
    assert service._model.calls==1
    assert second[0]==1.0
    for i in range(260):service.embed_query(str(i))
    assert len(service._query_vectors)==256
