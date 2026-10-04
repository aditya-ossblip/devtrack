def test_creating_a_project_makes_it_immediately_usable(client, world, auth):
    """One request should leave a project you can actually open."""
    response = client.post('/api/projects', json={
        'name': 'Payments Revamp',
        'description': 'Rework checkout.',
        'memberIds': [world['dev'].id, world['other'].id],
    }, headers=auth('lead@test.local'))

    body = response.get_json()
    assert response.status_code == 201
    assert body['project']['key'] == 'PR'          # derived from the name
    assert body['project']['memberCount'] == 3     # creator + two invited

    project_id = body['project']['id']
    detail = client.get(f'/api/projects/{project_id}', headers=auth('lead@test.local')).get_json()
    assert [state['name'] for state in detail['states']] == [
        'To do', 'In progress', 'In review', 'Done'
    ]
    assert detail['role'] == 'admin'               # the creator leads it

    board = client.get(f'/api/projects/{project_id}/board', headers=auth('lead@test.local'))
    assert len(board.get_json()['columns']) == 4


def test_a_taken_key_is_suffixed_when_derived_but_refused_when_asked_for(client, world, auth):
    headers = auth('lead@test.local')
    # 'DEV' already exists in the fixture.
    derived = client.post('/api/projects', json={'name': 'Developer Experience'}, headers=headers)
    assert derived.status_code == 201
    assert derived.get_json()['project']['key'] != 'DEV'

    explicit = client.post('/api/projects', json={'name': 'Anything', 'key': 'DEV'}, headers=headers)
    assert explicit.status_code == 409


def test_invited_members_are_notified(client, world, auth):
    client.post('/api/projects', json={
        'name': 'Notify Me', 'memberIds': [world['dev'].id],
    }, headers=auth('lead@test.local'))

    notifications = client.get('/api/notifications', headers=auth('dev@test.local')).get_json()
    assert notifications['unread'] >= 1
    assert 'added you to Notify Me' in notifications['notifications'][0]['text']


def test_you_only_see_projects_you_are_on(client, world, auth):
    outsider = client.post('/api/auth/register', json={
        'name': 'Out Sider', 'email': 'out@test.local', 'password': 'password123',
    }).get_json()
    headers = {'Authorization': f"Bearer {outsider['token']}"}

    assert client.get('/api/projects', headers=headers).get_json()['projects'] == []
    # Not 403 — that would confirm the project exists.
    assert client.get(f"/api/projects/{world['project'].id}", headers=headers).status_code == 404


def test_member_lookup_is_by_whole_address_only(client, world, auth):
    """Finding someone to add is a lookup, not a search of the directory.

    Matching a fragment of a name or an address let anyone signed in page
    through every account, or check whether a particular person had one. You
    can add someone whose address you already know; you cannot go looking.
    """
    headers = auth('dev@test.local')

    def found(term=None):
        params = {'q': term} if term is not None else {}
        body = client.get('/api/users', query_string=params, headers=headers).get_json()
        return [u['name'] for u in body['users']]

    assert found('manager@test.local') == ['Arjun Bhatt']
    assert found('OTHER@TEST.LOCAL') == ['Divya Das']      # case does not matter

    assert found('arjun') == []            # a name fragment
    assert found('other@') == []            # a partial address
    assert found('@test.local') == []       # a whole domain
    assert found() == []                    # and no listing at all


def test_adding_and_removing_members(client, world, auth):
    project_id = world['project'].id
    new = client.post('/api/auth/register', json={
        'name': 'Late Joiner', 'email': 'late@test.local', 'password': 'password123',
    }).get_json()['user']

    headers = auth('manager@test.local')
    added = client.post(f'/api/projects/{project_id}/members',
                        json={'userId': new['id'], 'role': 'developer'}, headers=headers)
    assert added.status_code == 201

    members = client.get(f'/api/projects/{project_id}/members', headers=headers).get_json()
    assert any(m['id'] == new['id'] for m in members['members'])

    removed = client.delete(f"/api/projects/{project_id}/members/{new['id']}", headers=headers)
    assert removed.status_code == 204


def test_the_project_lead_cannot_be_removed_or_demoted(client, world, auth):
    project_id = world['project'].id
    lead_id = world['lead'].id
    headers = auth('manager@test.local')

    assert client.delete(f'/api/projects/{project_id}/members/{lead_id}', headers=headers).status_code == 400
    assert client.patch(f'/api/projects/{project_id}/members/{lead_id}',
                        json={'role': 'developer'}, headers=headers).status_code == 400


def test_adding_an_unregistered_email_says_so(client, world, auth):
    response = client.post(f"/api/projects/{world['project'].id}/members",
                           json={'email': 'nobody@test.local'}, headers=auth('lead@test.local'))
    assert response.status_code == 404
    assert 'sign up' in response.get_json()['error']
