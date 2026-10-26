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
