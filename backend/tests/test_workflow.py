"""Custom workflow states, WIP limits and transition rules."""


def test_columns_can_be_added_renamed_and_deleted(client, world, auth):
    project_id = world['project'].id
    headers = auth('manager@test.local')

    added = client.post(f'/api/projects/{project_id}/states',
                        json={'name': 'Blocked', 'category': 'in_progress'}, headers=headers)
    assert added.status_code == 201
    state_id = added.get_json()['state']['id']

    renamed = client.patch(f'/api/projects/{project_id}/states/{state_id}',
                           json={'name': 'On hold'}, headers=headers)
    assert renamed.get_json()['state']['name'] == 'On hold'

    board = client.get(f'/api/projects/{project_id}/board', headers=headers).get_json()
    assert 'On hold' in [col['name'] for col in board['columns']]

    assert client.delete(f'/api/projects/{project_id}/states/{state_id}',
                         headers=headers).status_code == 204


def test_a_column_holding_issues_cannot_be_deleted(client, world, auth):
    response = client.delete(
        f"/api/projects/{world['project'].id}/states/{world['states']['To do'].id}",
        headers=auth('manager@test.local'),
    )
    assert response.status_code == 400
    assert 'Move them first' in response.get_json()['error']


def test_renaming_a_column_does_not_change_what_counts_as_done(client, world, auth):
    """The category, not the name, is what reports mean by 'done'."""
    project_id = world['project'].id
    headers = auth('manager@test.local')

    client.patch(f"/api/projects/{project_id}/states/{world['states']['Done'].id}",
                 json={'name': 'Shipped'}, headers=headers)
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)

    analytics = client.get(f'/api/projects/{project_id}/analytics', headers=headers).get_json()
    assert analytics['totals']['done'] == 1
    assert 'Shipped' in [row['name'] for row in analytics['byState']]


def test_a_wip_limit_blocks_the_move_that_would_exceed_it(client, world, auth):
    project_id = world['project'].id
    headers = auth('lead@test.local')
    progress_id = world['states']['In progress'].id

    client.patch(f'/api/projects/{project_id}/states/{progress_id}',
                 json={'wipLimit': 1}, headers=headers)

    first = client.patch(f"/api/issues/{world['own'].id}",
                         json={'stateId': progress_id}, headers=headers)
    second = client.patch(f"/api/issues/{world['foreign'].id}",
                          json={'stateId': progress_id}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 422
    assert 'limit of 1' in second.get_json()['error']


def test_no_transition_rules_means_every_move_is_allowed(client, world, auth):
    headers = auth('lead@test.local')
    response = client.patch(f"/api/issues/{world['own'].id}",
                            json={'stateId': world['states']['Done'].id}, headers=headers)
    assert response.status_code == 200


def test_transition_rules_block_a_skipped_step(client, world, auth):
    project_id = world['project'].id
    headers = auth('manager@test.local')
    states = world['states']

    # Only allow To do -> In progress.
    client.put(f'/api/projects/{project_id}/transitions', json={'transitions': [
        {'fromStateId': states['To do'].id, 'toStateId': states['In progress'].id},
    ]}, headers=headers)

    blocked = client.patch(f"/api/issues/{world['own'].id}",
                           json={'stateId': states['Done'].id}, headers=headers)
    assert blocked.status_code == 422
    assert 'does not allow' in blocked.get_json()['error']

    allowed = client.patch(f"/api/issues/{world['own'].id}",
                           json={'stateId': states['In progress'].id}, headers=headers)
    assert allowed.status_code == 200


def test_the_issue_detail_reports_which_moves_are_legal(client, world, auth):
    project_id = world['project'].id
    headers = auth('manager@test.local')
    states = world['states']

    client.put(f'/api/projects/{project_id}/transitions', json={'transitions': [
        {'fromStateId': states['To do'].id, 'toStateId': states['In progress'].id},
    ]}, headers=headers)

    detail = client.get(f"/api/issues/{world['own'].id}", headers=headers).get_json()
    assert states['In progress'].id in detail['allowedStateIds']
    assert states['Done'].id not in detail['allowedStateIds']
    assert states['To do'].id in detail['allowedStateIds']   # staying put is always legal


def test_clearing_the_rules_restores_free_movement(client, world, auth):
    project_id = world['project'].id
    headers = auth('manager@test.local')
    states = world['states']

    client.put(f'/api/projects/{project_id}/transitions', json={'transitions': [
        {'fromStateId': states['To do'].id, 'toStateId': states['In progress'].id},
    ]}, headers=headers)
    client.put(f'/api/projects/{project_id}/transitions', json={'transitions': []}, headers=headers)

    response = client.patch(f"/api/issues/{world['own'].id}",
                            json={'stateId': states['Done'].id}, headers=headers)
    assert response.status_code == 200
