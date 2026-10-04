"""The permission table, asserted row by row.

Project role decides everything. There is no site-wide role that reaches into
a project — see `auth.project_role`. Every rule is enforced server-side, not
just hidden in the UI.
"""

import pytest


def test_developer_may_move_their_own_issue(client, world, auth):
    response = client.patch(f"/api/issues/{world['own'].id}",
                            json={'stateId': world['states']['In progress'].id},
                            headers=auth('dev@test.local'))
    assert response.status_code == 200


def test_developer_may_not_move_someone_elses_issue(client, world, auth):
    response = client.patch(f"/api/issues/{world['foreign'].id}",
                            json={'stateId': world['states']['Done'].id},
                            headers=auth('dev@test.local'))
    assert response.status_code == 403
    assert response.get_json()['error'] == 'You can only change issues assigned to you.'


@pytest.mark.parametrize('email', ['lead@test.local', 'manager@test.local'])
def test_lead_and_manager_may_move_any_issue(client, world, auth, email):
    response = client.patch(f"/api/issues/{world['foreign'].id}",
                            json={'stateId': world['states']['Done'].id}, headers=auth(email))
    assert response.status_code == 200


def test_the_reporter_may_edit_an_issue_they_raised(client, world, auth):
    """The lead reported both issues in the fixture, so this is the lead's path."""
    response = client.patch(f"/api/issues/{world['foreign'].id}",
                            json={'title': 'Renamed by reporter'}, headers=auth('lead@test.local'))
    assert response.status_code == 200


def test_developer_may_create_an_issue(client, world, auth):
    response = client.post('/api/issues',
                           json={'projectId': world['project'].id, 'title': 'New', 'type': 'bug'},
                           headers=auth('dev@test.local'))
    assert response.status_code == 201
    assert response.get_json()['issue']['reporterName'] == 'Rohan Bose'


def test_developer_may_not_delete_an_issue(client, world, auth):
    response = client.delete(f"/api/issues/{world['own'].id}", headers=auth('dev@test.local'))
    assert response.status_code == 403


def test_developer_may_not_reassign_even_their_own_issue(client, world, auth):
    response = client.patch(f"/api/issues/{world['own'].id}",
                            json={'assigneeId': world['other'].id}, headers=auth('dev@test.local'))
    assert response.status_code == 403


def test_developer_may_not_change_the_workflow(client, world, auth):
    project_id = world['project'].id
    headers = auth('dev@test.local')

    assert client.post(f'/api/projects/{project_id}/states',
                       json={'name': 'Blocked'}, headers=headers).status_code == 403
    assert client.put(f'/api/projects/{project_id}/transitions',
                      json={'transitions': []}, headers=headers).status_code == 403
    assert client.patch(f'/api/projects/{project_id}',
                        json={'name': 'Renamed'}, headers=headers).status_code == 403


def test_developer_may_not_add_or_remove_members(client, world, auth):
    project_id = world['project'].id
    headers = auth('dev@test.local')

    assert client.post(f'/api/projects/{project_id}/members',
                       json={'userId': world['other'].id}, headers=headers).status_code == 403
    assert client.delete(f"/api/projects/{project_id}/members/{world['other'].id}",
                         headers=headers).status_code == 403


def test_only_a_project_admin_may_delete_a_project(client, world, auth):
    project_id = world['project'].id
    assert client.delete(f'/api/projects/{project_id}',
                         headers=auth('manager@test.local')).status_code == 403
    assert client.delete(f'/api/projects/{project_id}',
                         headers=auth('lead@test.local')).status_code == 204


def test_comments_can_only_be_deleted_by_their_author_or_a_manager(client, world, auth):
    issue_id = world['own'].id
    comment = client.post(f'/api/issues/{issue_id}/comments',
                          json={'body': 'Mine'}, headers=auth('dev@test.local')).get_json()['comment']

    assert client.delete(f"/api/issues/{issue_id}/comments/{comment['id']}",
                         headers=auth('other@test.local')).status_code == 403
    assert client.delete(f"/api/issues/{issue_id}/comments/{comment['id']}",
                         headers=auth('manager@test.local')).status_code == 204


def test_a_non_member_cannot_tell_the_project_exists(client, world, auth):
    client.post('/api/auth/register', json={
        'name': 'Out Sider', 'email': 'out@test.local', 'password': 'password123'})

    response = client.get(f"/api/projects/{world['project'].id}/board",
                          headers=auth('out@test.local'))
    assert response.status_code == 404  # not 403 — no existence leak


def test_every_write_route_needs_a_token(client, world):
    issue_id = world['own'].id
    project_id = world['project'].id

    assert client.patch(f'/api/issues/{issue_id}', json={'title': 'x'}).status_code == 401
    assert client.delete(f'/api/issues/{issue_id}').status_code == 401
    assert client.post('/api/issues', json={'title': 'x'}).status_code == 401
    assert client.post('/api/projects', json={'name': 'x'}).status_code == 401
    assert client.post(f'/api/projects/{project_id}/states', json={'name': 'x'}).status_code == 401
    assert client.get('/api/users').status_code == 401
    assert client.get('/api/notifications').status_code == 401
    assert client.get(f'/api/projects/{project_id}/analytics').status_code == 401


# --------------------------------------------------------------------------
# Isolation between unrelated people.
#
# DevTrack is meant to be signed up for by strangers whose projects share one
# database. These pin the property that makes that safe: no account on this
# server can reach a project it was not added to. Every one of them would have
# failed while a global admin role still granted project access.
# --------------------------------------------------------------------------

def test_a_stranger_sees_none_of_your_projects(client, world, auth, new_user):
    new_user('Stranger', 'stranger@test.local')
    listed = client.get('/api/projects', headers=auth('stranger@test.local')).get_json()
    assert listed['projects'] == []


def test_a_stranger_cannot_open_your_project(client, world, auth, new_user):
    project_id = world['project'].id
    new_user('Stranger', 'stranger@test.local')
    headers = auth('stranger@test.local')

    # 404, not 403: whether a project exists is itself information.
    assert client.get(f'/api/projects/{project_id}', headers=headers).status_code == 404
    assert client.get(f'/api/projects/{project_id}/board', headers=headers).status_code == 404
    assert client.patch(f'/api/projects/{project_id}',
                        json={'name': 'Mine now'}, headers=headers).status_code == 404
    assert client.delete(f'/api/projects/{project_id}', headers=headers).status_code == 404


def test_a_site_admin_is_not_an_admin_of_your_project(client, world, auth, new_user):
    """The whole point of the change.

    Somebody holds role='admin' on any real install. That must buy them
    nothing on a project belonging to someone they have never met.
    """
    project_id = world['project'].id
    new_user('Site Owner', 'owner@test.local', 'admin')
    headers = auth('owner@test.local')

    assert client.get('/api/projects', headers=headers).get_json()['projects'] == []
    assert client.get(f'/api/projects/{project_id}', headers=headers).status_code == 404
    assert client.delete(f'/api/projects/{project_id}', headers=headers).status_code == 404


def test_a_global_role_does_not_outrank_your_project_role(client, world, auth, new_user, join):
    """A site 'manager' added as a developer stays a developer."""
    outsider = new_user('Visiting Manager', 'visitor@test.local', 'manager')
    join(world['project'], outsider, 'developer')
    headers = auth('visitor@test.local')

    assert client.get(f"/api/projects/{world['project'].id}", headers=headers).status_code == 200
    assert client.patch(f"/api/projects/{world['project'].id}",
                        json={'name': 'Renamed'}, headers=headers).status_code == 403


def test_a_project_admin_who_is_not_the_lead_has_full_control(client, world, auth, new_user, join):
    """Sharing control is the point: the lead must not be the only one who can act."""
    member = new_user('Co-admin', 'coadmin@test.local')
    join(world['project'], member, 'admin')
    headers = auth('coadmin@test.local')
    project_id = world['project'].id

    assert client.patch(f'/api/projects/{project_id}',
                        json={'name': 'Renamed by a co-admin'}, headers=headers).status_code == 200
    assert client.delete(f'/api/projects/{project_id}', headers=headers).status_code == 204


def test_looking_someone_up_needs_their_whole_address(client, world, auth):
    """No browsing the directory, and no confirming a guess."""
    headers = auth('lead@test.local')

    def found(term):
        return client.get('/api/users', query_string={'q': term},
                          headers=headers).get_json()['users']

    assert found('dev@test.local') != []          # you know the address: fine
    assert found('DEV@TEST.LOCAL') != []          # case does not matter
    assert found('dev') == []                     # a fragment finds nothing
    assert found('@test.local') == []             # nor does a whole domain
    assert found('') == []                        # nor does an empty search
    assert found('nobody@test.local') == []       # and a miss looks identical
