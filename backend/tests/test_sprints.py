from datetime import date, timedelta


def _sprint(client, world, auth, **kwargs):
    payload = {'name': 'DEV Sprint 1', **kwargs}
    return client.post(f"/api/projects/{world['project'].id}/sprints",
                       json=payload, headers=auth('lead@test.local')).get_json()['sprint']


def test_a_sprint_needs_issues_before_it_can_start(client, world, auth):
    headers = auth('lead@test.local')
    sprint = _sprint(client, world, auth)

    empty = client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)
    assert empty.status_code == 400
    assert 'Add some issues' in empty.get_json()['error']

    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)
    started = client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)
    assert started.status_code == 200
    assert started.get_json()['sprint']['state'] == 'active'


def test_only_one_sprint_runs_at_a_time(client, world, auth):
    headers = auth('lead@test.local')
    first = _sprint(client, world, auth, name='S1')
    second = _sprint(client, world, auth, name='S2')

    client.post(f"/api/sprints/{first['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)
    client.post(f"/api/sprints/{first['id']}/start", headers=headers)

    client.post(f"/api/sprints/{second['id']}/issues",
                json={'issueIds': [world['foreign'].id]}, headers=headers)
    clash = client.post(f"/api/sprints/{second['id']}/start", headers=headers)

    assert clash.status_code == 409
    assert 'still running' in clash.get_json()['error']


def test_completing_a_sprint_carries_unfinished_work_to_the_backlog(client, world, auth):
    headers = auth('lead@test.local')
    sprint = _sprint(client, world, auth)

    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id, world['foreign'].id]}, headers=headers)
    client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)

    # Finish one of the two.
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)

    completed = client.post(f"/api/sprints/{sprint['id']}/complete", headers=headers)
    body = completed.get_json()

    assert body['sprint']['state'] == 'completed'
    assert body['carriedOver'] == 1

    backlog = client.get('/api/issues',
                         query_string={'projectId': world['project'].id, 'sprintId': 'backlog'},
                         headers=headers).get_json()
    assert [i['title'] for i in backlog['issues']] == ['Someone elses issue']


def test_completing_can_roll_work_into_the_next_sprint(client, world, auth):
    headers = auth('lead@test.local')
    current = _sprint(client, world, auth, name='S1')
    following = _sprint(client, world, auth, name='S2')

    client.post(f"/api/sprints/{current['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)
    client.post(f"/api/sprints/{current['id']}/start", headers=headers)
    client.post(f"/api/sprints/{current['id']}/complete",
                json={'moveUnfinishedTo': following['id']}, headers=headers)

    rolled = client.get('/api/issues',
                        query_string={'projectId': world['project'].id, 'sprintId': following['id']},
                        headers=headers).get_json()
    assert [i['title'] for i in rolled['issues']] == ['Dev own issue']


def test_the_board_can_be_filtered_to_the_active_sprint(client, world, auth):
    headers = auth('lead@test.local')
    sprint = _sprint(client, world, auth)
    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)
    client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)

    board = client.get(f"/api/projects/{world['project'].id}/board",
                       query_string={'sprintId': 'active'}, headers=headers).get_json()
    titles = [i['title'] for col in board['columns'] for i in col['issues']]
    assert titles == ['Dev own issue']


def test_burndown_needs_dates_and_then_reports_points(client, world, auth):
    headers = auth('lead@test.local')
    project_id = world['project'].id

    undated = client.get(f'/api/projects/{project_id}/burndown', headers=headers).get_json()
    assert undated['sprint'] is None

    sprint = _sprint(
        client, world, auth,
        startDate=(date.today() - timedelta(days=2)).isoformat(),
        endDate=(date.today() + timedelta(days=2)).isoformat(),
    )
    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id, world['foreign'].id]}, headers=headers)
    client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)

    burndown = client.get(f'/api/projects/{project_id}/burndown', headers=headers).get_json()
    assert burndown['sprint']['name'] == 'DEV Sprint 1'
    assert len(burndown['points']) == 5                 # inclusive of both ends
    assert burndown['points'][0]['ideal'] == 8.0        # 3 + 5 story points
    assert burndown['points'][-1]['ideal'] == 0.0
    # Days after today have no actual reading yet.
    assert burndown['points'][-1]['remaining'] is None


def test_velocity_lists_completed_sprints_only(client, world, auth):
    headers = auth('lead@test.local')
    project_id = world['project'].id
    sprint = _sprint(client, world, auth)

    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)
    client.post(f"/api/sprints/{sprint['id']}/start", headers=headers)

    assert client.get(f'/api/projects/{project_id}/velocity', headers=headers).get_json()['sprints'] == []

    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)
    client.post(f"/api/sprints/{sprint['id']}/complete", headers=headers)

    velocity = client.get(f'/api/projects/{project_id}/velocity', headers=headers).get_json()
    assert velocity['sprints'] == [{'name': 'DEV Sprint 1', 'committed': 3, 'completed': 3}]
