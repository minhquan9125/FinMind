import asyncio
import copy
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

from src.retrieval_orchestration.chat_logic import new_document
from tests.test_postgres_chat_store import Repository

spec = importlib.util.spec_from_file_location('chat_migration', Path(__file__).parents[1]/'scripts/migrate_chat_history.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_import_keeps_owner_identity_and_is_idempotent(tmp_path):
    owner, unknown = str(uuid4()), str(uuid4())
    doc = new_document(owner, str(uuid4()))
    doc['metadata']['execution_mode'] = 'LIVE'
    root = tmp_path/'web'
    folder = root/owner
    folder.mkdir(parents=True)
    target = folder/(doc['session_id']+'.json')
    original = json.dumps(doc, ensure_ascii=False).encode('utf8')
    target.write_bytes(original)
    other = root/unknown
    other.mkdir()
    (other/(str(uuid4())+'.json')).write_text('{}', encoding='utf8')
    docs, counts = migration.legacy_documents(root, {owner})
    assert counts == {'valid': 1, 'unknown_owner': 1, 'invalid': 0}
    async def run():
        repo = Repository()
        assert (await migration.import_documents(repo, docs))['imported'] == 1
        assert (await migration.import_documents(repo, docs))['already_present'] == 1
        newer = copy.deepcopy(repo.docs[(owner, doc['session_id'])])
        newer['revision'] = 1
        repo.docs[(owner, doc['session_id'])] = newer
        assert (await migration.import_documents(repo, docs))['kept_existing'] == 1
        assert repo.docs[(owner, doc['session_id'])]['revision'] == 1
    asyncio.run(run())
    assert target.read_bytes() == original


def test_import_rejects_forged_owner_and_noncanonical_session(tmp_path):
    owner = str(uuid4())
    folder = tmp_path/owner
    folder.mkdir()
    doc = new_document(str(uuid4()), str(uuid4()))
    (folder/(doc['session_id']+'.json')).write_text(json.dumps(doc), encoding='utf8')
    docs, counts = migration.legacy_documents(tmp_path, {owner})
    assert docs == [] and counts['invalid'] == 1
