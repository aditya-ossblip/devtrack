"""Settings that matter once DevTrack is on the internet.

Google-only sign-in, the production safety checks, Postgres URLs, and the
friendly "too long" message that replaces a database error on Postgres.
"""

import importlib
import sys

import pytest

from app import create_app
from app.config import TestConfig, engine_options, normalise_database_url


# --------------------------------------------------------------- Google only

@pytest.fixture()
def google_only(app):
    app.config['PASSWORD_SIGN_IN'] = False
    return app


def test_config_endpoint_says_whether_passwords_are_allowed(client, app):
    assert client.get('/api/auth/config').get_json()['passwordSignIn'] is True
    app.config['PASSWORD_SIGN_IN'] = False
    assert client.get('/api/auth/config').get_json()['passwordSignIn'] is False


@pytest.mark.parametrize('path, body', [
    ('/api/auth/login', {'email': 'lead@test.local', 'password': 'password123'}),
    ('/api/auth/register', {'name': 'New', 'email': 'new@test.local', 'password': 'password123'}),
    ('/api/auth/forgot', {'email': 'lead@test.local'}),
    ('/api/auth/reset', {'token': 'anything', 'password': 'password123'}),
])
def test_password_routes_are_closed_when_google_only(client, world, google_only, path, body):
    """Refused on the server, not just hidden in the page."""
    response = client.post(path, json=body)
    assert response.status_code == 403
    assert 'Google' in response.get_json()['error']


def test_setting_a_password_is_refused_when_google_only(client, world, auth, app):
    headers = auth('lead@test.local')
    app.config['PASSWORD_SIGN_IN'] = False
    response = client.patch('/api/auth/me', json={
        'currentPassword': 'password123', 'password': 'a-new-password',
    }, headers=headers)
    assert response.status_code == 403


def test_existing_sessions_keep_working_when_google_only(client, world, auth, app):
    headers = auth('lead@test.local')
    app.config['PASSWORD_SIGN_IN'] = False
    assert client.get('/api/auth/me', headers=headers).status_code == 200


# ------------------------------------------------------------ production mode

def _reload_config(monkeypatch, **env):
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    sys.modules.pop('app.config', None)
    return importlib.import_module('app.config')


@pytest.fixture()
def restore_config_module():
    original = sys.modules.get('app.config')
    yield
    if original is not None:
        sys.modules['app.config'] = original


def test_production_turns_passwords_and_reset_links_off(monkeypatch, restore_config_module):
    config = _reload_config(monkeypatch, DEVTRACK_ENV='production',
                            PASSWORD_SIGN_IN=None, RESET_RETURN_TOKEN='1')
    assert config.Config.PASSWORD_SIGN_IN is False
    # Even with RESET_RETURN_TOKEN=1 left over in .env: handing reset links to
    # whoever asks would let anyone take over any account.
    assert config.Config.RESET_RETURN_TOKEN is False


def test_development_keeps_passwords_for_the_demo_account(monkeypatch, restore_config_module):
    config = _reload_config(monkeypatch, DEVTRACK_ENV=None, PASSWORD_SIGN_IN=None)
    assert config.Config.PASSWORD_SIGN_IN is True


class _Production(TestConfig):
    IS_PRODUCTION = True
    SECRET_KEY = 'dev-only-not-for-deployment'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    GOOGLE_CLIENT_ID = ''
    PASSWORD_SIGN_IN = False


def test_production_refuses_to_start_on_development_settings():
    with pytest.raises(RuntimeError) as caught:
        create_app(_Production)
    message = str(caught.value)
    assert 'SECRET_KEY' in message
    assert 'Postgres' in message
    assert 'GOOGLE_CLIENT_ID' in message


# --------------------------------------------------------------- Postgres URLs

@pytest.mark.parametrize('given, expected', [
    ('postgres://u:p@host:5432/db', 'postgresql+psycopg://u:p@host:5432/db'),
    ('postgresql://u:p@host/db?sslmode=require', 'postgresql+psycopg://u:p@host/db?sslmode=require'),
    ('postgresql+psycopg://u:p@host/db', 'postgresql+psycopg://u:p@host/db'),
    ('mysql+pymysql://u:p@host/db', 'mysql+pymysql://u:p@host/db'),
])
def test_host_database_urls_can_be_pasted_as_they_are(given, expected):
    assert normalise_database_url(given) == expected


def test_postgres_sessions_are_pinned_to_utc():
    """A server installed in India defaults to Asia/Kolkata and shifted every
    stored timestamp by 5h30. All times here are UTC, so the session must be."""
    options = engine_options('postgresql+psycopg://u:p@localhost/db')
    assert options['connect_args'] == {'options': '-c timezone=UTC'}
    assert 'connect_args' not in engine_options('sqlite:///x.db')


# ---------------------------------------------------------- too-long values

def test_a_too_long_title_is_a_clear_400_not_a_crash(client, world, auth):
    headers = auth('lead@test.local')
    response = client.post('/api/issues', json={
        'projectId': world['project'].id,
        'title': 'x' * 201,
    }, headers=headers)
    assert response.status_code == 400
    assert 'Title is too long' in response.get_json()['error']

    # Nothing half-written was left behind for the next request to trip over.
    ok = client.post('/api/issues', json={
        'projectId': world['project'].id,
        'title': 'A normal title',
    }, headers=headers)
    assert ok.status_code == 201, ok.get_json()
