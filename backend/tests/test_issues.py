from datetime import timedelta

from app.extensions import db
from app.models import Issue, today_utc


def test_board_returns_the_projects_workflow_in_order(client, world, auth):
    response = client.get(f"/api/projects/{world['project'].id}/board",
                          headers=auth('dev@test.local'))
    columns = response.get_json()['columns']

    assert [col['name'] for col in columns] == ['To do', 'In progress', 'In review', 'Done']
    assert [col['category'] for col in columns] == ['todo', 'in_progress', 'in_progress', 'done']
    # Empty columns are still present — the board renders a placeholder off them.
    assert columns[1]['issues'] == []


def test_issue_shape_matches_what_the_card_renders(client, world, auth):
    response = client.get(f"/api/projects/{world['project'].id}/board",
                          headers=auth('dev@test.local'))
    issue = response.get_json()['columns'][0]['issues'][0]

    for key in ('key', 'title', 'type', 'priority', 'stateId', 'stateName', 'stateCategory',
                'assignee', 'labels', 'overdue', 'storyPoints', 'commentCount'):
        assert key in issue, f'missing {key}'
    assert issue['key'] == 'DEV-1'
    assert issue['assignee'] == 'RB'


def test_issue_keys_increment_per_project_and_never_reuse(client, world, auth):
    headers = auth('lead@test.local')
    first = client.post('/api/issues', json={
        'projectId': world['project'].id, 'title': 'Third'}, headers=headers).get_json()
    assert first['issue']['key'] == 'DEV-3'

    client.delete(f"/api/issues/{first['issue']['id']}", headers=headers)

    second = client.post('/api/issues', json={
        'projectId': world['project'].id, 'title': 'Fourth'}, headers=headers).get_json()
    assert second['issue']['key'] == 'DEV-4'


def test_overdue_is_derived_and_clears_when_done(client, world, auth):
    issue = db.session.get(Issue, world['own'].id)
    # today_utc, not date.today: `is_overdue` compares against UTC, and for
    # several hours a day the server's local date is the one after it.
    issue.due_date = today_utc() - timedelta(days=1)
    db.session.commit()

    headers = auth('lead@test.local')
    fetched = client.get(f'/api/issues/{issue.id}', headers=headers).get_json()
    assert fetched['issue']['overdue'] is True

    client.patch(f'/api/issues/{issue.id}',
                 json={'stateId': world['states']['Done'].id}, headers=headers)
    after = client.get(f'/api/issues/{issue.id}', headers=headers).get_json()
    assert after['issue']['overdue'] is False   # due date untouched, flag recomputed


def test_a_move_appends_to_the_target_column(client, world, auth):
    headers = auth('lead@test.local')
    done_id = world['states']['Done'].id

    client.patch(f"/api/issues/{world['own'].id}", json={'stateId': done_id}, headers=headers)
    client.patch(f"/api/issues/{world['foreign'].id}", json={'stateId': done_id}, headers=headers)

    columns = client.get(f"/api/projects/{world['project'].id}/board",
                         headers=headers).get_json()['columns']
    by_name = {col['name']: col for col in columns}

    assert by_name['To do']['issues'] == []
    assert [i['title'] for i in by_name['Done']['issues']] == ['Dev own issue', 'Someone elses issue']


def test_labels_round_trip_and_deduplicate(client, world, auth):
    headers = auth('lead@test.local')
    response = client.patch(f"/api/issues/{world['own'].id}",
                            json={'labels': ['auth', 'backend', 'auth', ' ']}, headers=headers)
    assert response.get_json()['issue']['labels'] == ['auth', 'backend']


def test_comments_can_be_added_and_counted(client, world, auth):
    headers = auth('dev@test.local')
    issue_id = world['own'].id

    created = client.post(f'/api/issues/{issue_id}/comments',
                          json={'body': 'Picking this up now.'}, headers=headers)
    assert created.status_code == 201
    assert created.get_json()['comment']['authorInitials'] == 'RB'

    assert client.post(f'/api/issues/{issue_id}/comments',
                       json={'body': '   '}, headers=headers).status_code == 400

    detail = client.get(f'/api/issues/{issue_id}', headers=headers).get_json()
    assert detail['issue']['commentCount'] == 1
    assert len(detail['issue']['comments']) == 1


def test_my_tasks_returns_only_your_issues(client, world, auth):
    response = client.get('/api/issues', query_string={'assigneeId': 'me'},
                          headers=auth('dev@test.local'))
    titles = [issue['title'] for issue in response.get_json()['issues']]
    assert titles == ['Dev own issue']


def test_backlog_filter_excludes_issues_in_a_sprint(client, world, auth):
    headers = auth('lead@test.local')
    sprint = client.post(f"/api/projects/{world['project'].id}/sprints",
                         json={'name': 'S1'}, headers=headers).get_json()['sprint']
    client.post(f"/api/sprints/{sprint['id']}/issues",
                json={'issueIds': [world['own'].id]}, headers=headers)

    backlog = client.get('/api/issues',
                         query_string={'projectId': world['project'].id, 'sprintId': 'backlog'},
                         headers=headers).get_json()
    assert [i['title'] for i in backlog['issues']] == ['Someone elses issue']


def test_finishing_an_issue_notifies_the_rest_of_the_project(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=auth('lead@test.local'))

    mine = client.get('/api/notifications', headers=auth('lead@test.local')).get_json()
    theirs = client.get('/api/notifications', headers=auth('dev@test.local')).get_json()

    assert mine['notifications'] == []   # not told about my own action
    assert theirs['notifications'][0]['type'] == 'done'
    assert 'Dev own issue' in theirs['notifications'][0]['text']
    assert theirs['unread'] == 1


def test_assigning_someone_notifies_them(client, world, auth):
    client.patch(f"/api/issues/{world['foreign'].id}",
                 json={'assigneeId': world['dev'].id}, headers=auth('manager@test.local'))

    notifications = client.get('/api/notifications', headers=auth('dev@test.local')).get_json()
    assert notifications['notifications'][0]['type'] == 'assigned'


def test_mark_all_read_clears_the_badge(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=auth('lead@test.local'))
    headers = auth('dev@test.local')

    assert client.get('/api/notifications', headers=headers).get_json()['unread'] == 1
    client.post('/api/notifications/read-all', headers=headers)
    assert client.get('/api/notifications', headers=headers).get_json()['unread'] == 0


def test_bad_type_priority_and_state_are_rejected(client, world, auth):
    headers = auth('lead@test.local')
    issue_id = world['own'].id

    assert client.patch(f'/api/issues/{issue_id}', json={'type': 'saga'}, headers=headers).status_code == 400
    assert client.patch(f'/api/issues/{issue_id}', json={'priority': 'urgent'}, headers=headers).status_code == 400
    assert client.patch(f'/api/issues/{issue_id}', json={'stateId': 9999}, headers=headers).status_code == 404
    assert client.patch(f'/api/issues/{issue_id}', json={'dueDate': '20th'}, headers=headers).status_code == 400
