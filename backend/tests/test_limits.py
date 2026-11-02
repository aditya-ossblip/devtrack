"""Limits that keep one account or one script from hurting everyone else."""

from app.models import Project
from app.extensions import db
from app.ratelimit import RateLimiter


def test_sign_in_attempts_are_limited_per_address(client, world, app):
    app.config['AUTH_RATE_LIMIT_COUNT'] = 3
    body = {'email': 'lead@test.local', 'password': 'wrong-password'}

    for _ in range(3):
        assert client.post('/api/auth/login', json=body).status_code == 401
    blocked = client.post('/api/auth/login', json=body)
    assert blocked.status_code == 429
    assert 'Too many attempts' in blocked.get_json()['error']

    # Even the right password waits: the limit is on attempts, not failures.
    right = {'email': 'lead@test.local', 'password': 'password123'}
    assert client.post('/api/auth/login', json=right).status_code == 429


def test_each_route_has_its_own_count(client, world, app):
    app.config['AUTH_RATE_LIMIT_COUNT'] = 1
    client.post('/api/auth/login', json={'email': 'x@test.local', 'password': 'nope-nope'})
    # Registering is a different bucket, so it is not blocked by the login above.
    response = client.post('/api/auth/register', json={
        'name': 'New', 'email': 'new@test.local', 'password': 'password123'})
    assert response.status_code == 201


def test_the_window_slides():
    limiter = RateLimiter()
    assert limiter.hit('k', 2, 60, now=0) == 0
    assert limiter.hit('k', 2, 60, now=10) == 0
    assert limiter.hit('k', 2, 60, now=20) > 0       # third inside the minute
    assert limiter.hit('k', 2, 60, now=61) == 0      # the first has expired


def test_one_account_can_lead_only_so_many_projects(client, world, auth, app):
    app.config['MAX_PROJECTS_PER_USER'] = 2
    headers = auth('dev@test.local')

    assert client.post('/api/projects', json={'name': 'One'}, headers=headers).status_code == 201
    assert client.post('/api/projects', json={'name': 'Two'}, headers=headers).status_code == 201
    third = client.post('/api/projects', json={'name': 'Three'}, headers=headers)
    assert third.status_code == 403
    assert 'most one account can' in third.get_json()['error']
    assert db.session.scalar(db.select(db.func.count(Project.id))) == 3   # world's + 2


def test_projects_you_were_added_to_do_not_count(client, world, auth, app):
    """dev is a member of world's project but leads none, so the cap of 1 still allows one."""
    app.config['MAX_PROJECTS_PER_USER'] = 1
    response = client.post('/api/projects', json={'name': 'Mine'}, headers=auth('dev@test.local'))
    assert response.status_code == 201


def test_every_response_carries_the_security_headers(client):
    response = client.get('/api/health')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
