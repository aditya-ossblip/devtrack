"""Configuration loading.

These exist because a real bug shipped here: `.env` was loaded *after*
`config.py` had already read the environment, so every setting silently fell
back to its default -- including DATABASE_URL, which would have sent a
MySQL-configured app to SQLite without a word.

Every test here stubs `dotenv.load_dotenv`. Without that the real
`backend/.env` loads on reimport and puts the developer's own settings back
into the environment, so a test asking "what happens with no SECRET_KEY?"
could never actually see that state.
"""

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def restore_config_module():
    """Reimporting app.config swaps the module other imports already hold."""
    original = sys.modules.get('app.config')
    yield
    if original is not None:
        sys.modules['app.config'] = original
    else:
        sys.modules.pop('app.config', None)


def _reload_config(monkeypatch, **env):
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: False)

    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    sys.modules.pop('app.config', None)
    return importlib.import_module('app.config')


def test_dotenv_is_loaded_before_any_setting_is_read(monkeypatch):
    """The regression guard for the ordering bug.

    A stand-in `load_dotenv` injects a value the way the real one would. If it
    runs after the Config class body, as it once did, Config never sees it and
    this fails.
    """
    monkeypatch.delenv('SECRET_KEY', raising=False)

    def fake_load_dotenv(*args, **kwargs):
        monkeypatch.setenv('SECRET_KEY', 'value-that-came-from-dotenv')
        return True

    monkeypatch.setattr('dotenv.load_dotenv', fake_load_dotenv)

    sys.modules.pop('app.config', None)
    config = importlib.import_module('app.config')

    assert config.Config.SECRET_KEY == 'value-that-came-from-dotenv'


def test_settings_come_from_the_environment(monkeypatch):
    config = _reload_config(
        monkeypatch,
        SECRET_KEY='a-real-secret-key-of-sufficient-length',
        DATABASE_URL='mysql+pymysql://user:pw@localhost/devtrack',
        JWT_EXPIRES_SECONDS='3600',
    )
    assert config.Config.SECRET_KEY == 'a-real-secret-key-of-sufficient-length'
    assert config.Config.SQLALCHEMY_DATABASE_URI.startswith('mysql+pymysql://')
    assert config.Config.JWT_EXPIRES_SECONDS == 3600


def test_a_blank_database_url_falls_back_to_sqlite(monkeypatch):
    config = _reload_config(monkeypatch, DATABASE_URL='')
    assert config.Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite:///')


def test_the_fallback_secret_key_is_only_a_fallback(monkeypatch):
    """If this is ever the live key, tokens are forgeable by anyone with the source."""
    config = _reload_config(monkeypatch, SECRET_KEY=None)
    assert config.Config.SECRET_KEY == 'dev-only-not-for-deployment'


def test_the_test_key_is_long_enough_for_hs256(monkeypatch):
    """RFC 7518 wants >= 32 bytes; PyJWT warns below that on every token."""
    config = _reload_config(monkeypatch)
    assert len(config.TestConfig.SECRET_KEY) >= 32


def test_tests_use_a_cheap_password_hash_but_the_app_does_not(monkeypatch):
    """Fixtures hash a lot of passwords; scrypt would make the suite crawl."""
    config = _reload_config(monkeypatch, PASSWORD_HASH_METHOD=None)
    assert config.Config.PASSWORD_HASH_METHOD == 'scrypt'
    assert config.TestConfig.PASSWORD_HASH_METHOD.startswith('pbkdf2:')
