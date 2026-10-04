"""Forgotten passwords."""

from datetime import timedelta

from app.extensions import db
from app.models import PasswordReset, utcnow


def request_reset(client, email='dev@test.local'):
    return client.post('/api/auth/forgot', json={'email': email})


def test_the_response_is_identical_for_unknown_addresses(client, world):
    """Otherwise this endpoint tells you who has an account here."""
    known = request_reset(client, 'dev@test.local')
    unknown = request_reset(client, 'nobody@test.local')

    assert known.status_code == unknown.status_code == 200
    assert known.get_json()['sent'] is unknown.get_json()['sent'] is True
    assert 'token' not in unknown.get_json()      # nothing issued for an unknown address


def test_a_token_resets_the_password_and_signs_you_in(client, world):
    token = request_reset(client).get_json()['token']

    response = client.post('/api/auth/reset', json={'token': token, 'password': 'brand-new-pass'})
    body = response.get_json()

    assert response.status_code == 200
    assert body['token']                           # signed in straight away
    assert body['user']['email'] == 'dev@test.local'

    assert client.post('/api/auth/login',
                       json={'email': 'dev@test.local', 'password': 'brand-new-pass'}
                       ).status_code == 200
    assert client.post('/api/auth/login',
                       json={'email': 'dev@test.local', 'password': 'password123'}
                       ).status_code == 401


def test_a_token_works_once(client, world):
    token = request_reset(client).get_json()['token']
    assert client.post('/api/auth/reset', json={'token': token, 'password': 'first-change'}).status_code == 200

    again = client.post('/api/auth/reset', json={'token': token, 'password': 'second-change'})
    assert again.status_code == 400
    assert 'expired or already been used' in again.get_json()['error']


def test_requesting_again_invalidates_the_earlier_link(client, world):
    first = request_reset(client).get_json()['token']
    second = request_reset(client).get_json()['token']

    assert client.post('/api/auth/reset', json={'token': first, 'password': 'password999'}).status_code == 400
    assert client.post('/api/auth/reset', json={'token': second, 'password': 'password999'}).status_code == 200


def test_an_expired_token_is_refused(client, world):
    token = request_reset(client).get_json()['token']

    entry = db.session.scalar(db.select(PasswordReset))
    entry.expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()

    assert client.post('/api/auth/reset', json={'token': token, 'password': 'password999'}).status_code == 400


def test_only_the_hash_is_stored(client, world):
    token = request_reset(client).get_json()['token']
    entry = db.session.scalar(db.select(PasswordReset))

    assert entry.token_hash != token
    assert len(entry.token_hash) == 64             # sha256 hex


def test_the_new_password_still_has_to_be_long_enough(client, world):
    token = request_reset(client).get_json()['token']
    response = client.post('/api/auth/reset', json={'token': token, 'password': 'short'})

    assert response.status_code == 400
    assert 'at least 8' in response.get_json()['error']


def test_a_nonsense_token_is_refused(client, world):
    assert client.post('/api/auth/reset',
                       json={'token': 'not-a-real-token', 'password': 'password999'}
                       ).status_code == 400
