"""Live updates: the socket layer and the activity feed that rides on it."""

from app.extensions import db, socketio
from app.models import Activity


def token_for(client, email, password='password123'):
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['token']


def live(app, client, email):
    """A signed-in socket, the way the browser opens one."""
    sock = socketio.test_client(app, flask_test_client=client,
                                auth={'token': token_for(client, email)})
    assert sock.is_connected()
    sock.get_received()  # drop the 'connected' greeting
    return sock


def names(received):
    return [message['name'] for message in received]


def test_a_member_can_join_their_project_room(app, client, world):
    sock = live(app, client, 'dev@test.local')
    sock.emit('join_project', {'projectId': world['project'].id})
    assert 'joined_project' in names(sock.get_received())


def test_a_non_member_is_refused_the_room(app, client, world, new_user):
    new_user('Out Sider', 'out@test.local')
    sock = live(app, client, 'out@test.local')
    sock.emit('join_project', {'projectId': world['project'].id})
    received = sock.get_received()
    assert 'joined_project' not in names(received)
    assert 'error' in names(received)


def test_a_socket_without_a_token_is_refused(app, client):
    sock = socketio.test_client(app, flask_test_client=client)
    assert not sock.is_connected()


def test_moving_an_issue_sends_the_activity_to_the_room(app, client, world, auth):
    watcher = live(app, client, 'manager@test.local')
    watcher.emit('join_project', {'projectId': world['project'].id})
    watcher.get_received()

    done = world['states']['Done']
    response = client.patch(f"/api/issues/{world['own'].id}", json={'stateId': done.id},
                            headers=auth('dev@test.local'))
    assert response.status_code == 200, response.get_json()

    feed = [m['args'][0]['activity'] for m in watcher.get_received() if m['name'] == 'activity:new']
    assert feed, 'no activity:new arrived'
    moved = [entry for entry in feed if entry['verb'] == 'issue.moved']
    assert moved and moved[0]['issueId'] == world['own'].id
    assert moved[0]['to'] == 'Done'
    assert moved[0]['actorName'] == 'Rohan Bose'
    # The live copy is the stored row: same id, so the panel can de-duplicate.
    assert db.session.get(Activity, moved[0]['id']) is not None


def test_other_projects_hear_nothing(app, client, world, auth, new_user):
    stranger = new_user('Out Sider', 'out@test.local')
    created = client.post('/api/projects', json={'name': 'Elsewhere'},
                          headers=auth('out@test.local'))
    assert created.status_code == 201, created.get_json()
    elsewhere = created.get_json()['project']['id']

    sock = live(app, client, 'out@test.local')
    sock.emit('join_project', {'projectId': elsewhere})
    sock.get_received()

    client.patch(f"/api/issues/{world['own'].id}", json={'stateId': world['states']['Done'].id},
                 headers=auth('dev@test.local'))
    assert 'activity:new' not in names(sock.get_received())
    assert stranger.id  # used


def test_the_history_survives_a_restart(app, client, world, auth):
    """What the panel loads on open is the stored log, not anything in memory."""
    client.patch(f"/api/issues/{world['own'].id}", json={'stateId': world['states']['Done'].id},
                 headers=auth('dev@test.local'))

    # Nothing live is listening at all - as if every browser had been closed.
    history = client.get(f"/api/projects/{world['project'].id}/activity",
                         headers=auth('lead@test.local')).get_json()['activity']
    assert any(entry['verb'] == 'issue.moved' for entry in history)
