import os
from unittest.mock import Mock, patch

from backend.src.graph import graph_store


def test_backend_configuration_overrides_root_and_keeps_password_literal(tmp_path):
    root = tmp_path / '.env'
    root.write_text('NEO4J_URI=bolt://root:7687\nNEO4J_USER=root\nNEO4J_PASSWORD=root\n')
    backend = tmp_path / 'backend'; backend.mkdir()
    (backend / '.env').write_text('NEO4J_URI=bolt://backend:17687\nNEO4J_USER=reader\nNEO4J_PASSWORD=literal${SECRET}\n')
    driver = Mock()
    with patch.dict(os.environ, {}, clear=True), patch.object(graph_store, 'ENV_FILE', root), patch('neo4j.GraphDatabase.driver', return_value=driver) as connect:
        store = graph_store.GraphStore.from_environment()
        assert connect.call_args.args == ('bolt://backend:17687',)
        assert connect.call_args.kwargs['auth'] == ('reader', 'literal${SECRET}')
        driver.verify_connectivity.assert_called_once()
        store.close()


def test_process_configuration_still_has_priority(tmp_path):
    root = tmp_path / '.env'
    root.write_text('NEO4J_URI=bolt://root:7687\nNEO4J_USER=root\nNEO4J_PASSWORD=root\n')
    env = {'NEO4J_URI': 'bolt://process:7687', 'NEO4J_USER': 'process', 'NEO4J_PASSWORD': 'process'}
    with patch.dict(os.environ, env, clear=True), patch.object(graph_store, 'ENV_FILE', root), patch('neo4j.GraphDatabase.driver', return_value=Mock()) as connect:
        graph_store.GraphStore.from_environment().close()
        assert connect.call_args.args == ('bolt://process:7687',)
        assert connect.call_args.kwargs['auth'] == ('process', 'process')
