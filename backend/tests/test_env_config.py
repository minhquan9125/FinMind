from src.core.config import ENV_FILES, ENV_PATH, Settings


def test_root_env_used_when_backend_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    root = tmp_path / '.env'
    root.write_text('DATABASE_URL=postgresql://example.invalid/root\n', encoding='utf-8')
    backend = tmp_path / 'backend.env'
    settings = Settings(_env_file=(root, backend))
    assert settings.database_url == 'postgresql://example.invalid/root'
    assert Settings.model_config['env_file'] == ENV_FILES
    assert ENV_FILES == (ENV_PATH.parent.parent / '.env', ENV_PATH)


def test_backend_env_overrides_root_and_environment_overrides_both(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    root, backend = tmp_path / 'root.env', tmp_path / 'backend.env'
    root.write_text('DATABASE_URL=postgresql://example.invalid/root\n', encoding='utf-8')
    backend.write_text('DATABASE_URL=postgresql://example.invalid/backend\n', encoding='utf-8')
    assert Settings(_env_file=(root, backend)).database_url.endswith('/backend')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example.invalid/environment')
    assert Settings(_env_file=(root, backend)).database_url.endswith('/environment')
