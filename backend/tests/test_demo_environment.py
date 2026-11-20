import importlib.util
import os
from pathlib import Path


def test_demo_configuration_precedence_and_portable_paths(tmp_path,monkeypatch):
    module_path=Path(__file__).resolve().parents[1]/'scripts/demo_environment.py'
    spec=importlib.util.spec_from_file_location('demo_environment_test',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    backend=tmp_path/'backend';backend.mkdir()
    (tmp_path/'.env').write_text('FINMIND_DATA_ROOT=root-data\nHF_HOME=root-cache\n',encoding='utf-8')
    (backend/'.env').write_text('FINMIND_DATA_ROOT=member-data\nHF_HOME=backend-cache\nADMIN_INGEST_DATABASE_URL=writer-config\n',encoding='utf-8')
    (backend/'.env.operator').write_text('DATABASE_URL=operator-config\n',encoding='utf-8')
    monkeypatch.delenv('FINMIND_DATA_ROOT',raising=False)
    monkeypatch.delenv('ADMIN_INGEST_DATABASE_URL',raising=False)
    monkeypatch.setenv('HF_HOME','shell-cache')
    module.load_demo_environment(backend)
    assert os.environ['FINMIND_DATA_ROOT']=='member-data'
    assert os.environ['HF_HOME']=='shell-cache'
    assert os.environ['ADMIN_INGEST_DATABASE_URL']=='writer-config'
