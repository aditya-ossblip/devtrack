def test_login_returns_token_and_user(client, world):
    response = client.post('/api/auth/login',
                           json={'email': 'lead@test.local', 'password': 'password123'})
    body = response.get_json()

    assert response.status_code == 200
    assert body['token']
    assert body['user']['name'] == 'Aditya Kundu'
    assert body['user']['initials'] == 'AK'
    assert 'password_hash' not in body['user']


def test_login_is_case_insensitive_on_email(client, world):
    response = client.post('/api/auth/login',
                           json={'email': 'LEAD@test.local', 'password': 'password123'})
    assert response.status_code == 200


def test_wrong_password_gives_the_same_message_as_unknown_email(client, world):
    wrong = client.post('/api/auth/login',
                        json={'email': 'lead@test.local', 'password': 'nope'})
    unknown = client.post('/api/auth/login',
                          json={'email': 'ghost@test.local', 'password': 'password123'})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()['error'] == unknown.get_json()['error'] == 'Invalid email or password.'


def test_protected_route_rejects_missing_and_malformed_tokens(client, world):
    assert client.get('/api/auth/me').status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer nonsense'}).status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': 'Token abc'}).status_code == 401


def test_register_signs_you_straight_in(client, world):
    response = client.post('/api/auth/register', json={
        'name': 'New Person', 'email': 'new@test.local', 'password': 'password123',
        'title': 'Frontend',
    })
    body = response.get_json()

    assert response.status_code == 201
    assert body['token']
    assert body['user']['initials'] == 'NP'
    # Not the first account in this world, so no automatic admin.
    assert body['user']['role'] == 'Developer'

    me = client.get('/api/auth/me', headers={'Authorization': f"Bearer {body['token']}"})
    assert me.get_json()['user']['email'] == 'new@test.local'


def test_everyone_registers_the_same(client, app):
    """There is no first-user-is-admin rule, deliberately.

    It meant something while a global admin could reach every project. Now
    that project access comes only from being a project's lead or one of its
    members, an "admin" account grants nothing extra — so handing it out by
    accident of signup order was misleading at best.
    """
    first = client.post('/api/auth/register', json={
        'name': 'First Person', 'email': 'first@test.local', 'password': 'password123',
    })
    assert first.get_json()['user']['role'] == 'Developer'

    second = client.post('/api/auth/register', json={
        'name': 'Second Person', 'email': 'second@test.local', 'password': 'password123',
    })
    assert second.get_json()['user']['role'] == 'Developer'


def test_registering_cannot_grant_yourself_a_role(client, app):
    """`role` in the request body used to be honoured, so anyone could ask."""
    response = client.post('/api/auth/register', json={
        'name': 'Opportunist', 'email': 'op@test.local',
        'password': 'password123', 'role': 'admin',
    })
    assert response.get_json()['user']['role'] == 'Developer'


def test_register_rejects_duplicates_short_passwords_and_bad_emails(client, world):
    assert client.post('/api/auth/register', json={
        'name': 'X Y', 'email': 'x@test.local', 'password': 'short'}).status_code == 400
    assert client.post('/api/auth/register', json={
        'name': 'X Y', 'email': 'not-an-email', 'password': 'password123'}).status_code == 400
    assert client.post('/api/auth/register', json={
        'name': 'A B', 'email': 'lead@test.local', 'password': 'password123'}).status_code == 409


def test_errors_are_always_json(client):
    response = client.get('/api/does-not-exist')
    assert response.status_code == 404
    assert response.is_json
    assert 'error' in response.get_json()


def test_health_needs_no_token(client):
    assert client.get('/api/health').get_json() == {'status': 'ok'}
