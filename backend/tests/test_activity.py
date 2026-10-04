"""The activity log, and the report that now depends on it."""

from datetime import datetime, time, timedelta, timezone

from app.extensions import db
from app.models import Activity, today_utc


def verbs(client, world, auth, email='lead@test.local'):
    response = client.get(f"/api/projects/{world['project'].id}/activity", headers=auth(email))
    return [row['verb'] for row in response.get_json()['activity']]


def test_creating_an_issue_is_recorded(client, world, auth):
    client.post('/api/issues', json={'projectId': world['project'].id, 'title': 'Logged'},
                headers=auth('lead@test.local'))
    assert 'issue.created' in verbs(client, world, auth)


def test_a_move_records_both_ends(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['In progress'].id},
                 headers=auth('lead@test.local'))

    entry = db.session.scalar(db.select(Activity).filter_by(verb='issue.moved'))
    assert entry.field == 'status'
    assert entry.from_value == 'To do'
    assert entry.to_value == 'In progress'
    assert entry.subject.startswith('DEV-')

    # Both ends are also kept as ids. Assigning `issue.state_id` rather than
    # `issue.state` once left `issue.state` pointing at the old row, and the
    # log recorded a move from "To do" to "To do".
    assert entry.from_ref == world['states']['To do'].id
    assert entry.to_ref == world['states']['In progress'].id


def test_each_edited_field_is_its_own_row(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'title': 'Renamed', 'priority': 'highest'},
                 headers=auth('lead@test.local'))

    rows = db.session.scalars(db.select(Activity).filter_by(verb='issue.updated')).all()
    assert {row.field for row in rows} == {'title', 'priority'}


def test_an_unchanged_field_records_nothing(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'title': 'Dev own issue'}, headers=auth('lead@test.local'))
    assert db.session.scalar(db.select(db.func.count(Activity.id)).filter_by(verb='issue.updated')) == 0


def test_reassignment_records_who_it_moved_between(client, world, auth):
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'assigneeId': world['other'].id}, headers=auth('manager@test.local'))

    entry = db.session.scalar(db.select(Activity).filter_by(verb='issue.assigned'))
    assert entry.from_value == 'Rohan Bose'
    assert entry.to_value == 'Divya Das'


def test_deleting_an_issue_keeps_its_history(client, world, auth):
    key = world['own'].key
    client.delete(f"/api/issues/{world['own'].id}", headers=auth('lead@test.local'))

    entry = db.session.scalar(db.select(Activity).filter_by(verb='issue.deleted'))
    assert key in entry.subject      # the key survives the row it described


def test_comments_and_members_are_recorded(client, world, auth):
    client.post(f"/api/issues/{world['own'].id}/comments",
                json={'body': 'Looking at it'}, headers=auth('dev@test.local'))
    client.delete(f"/api/projects/{world['project'].id}/members/{world['other'].id}",
                  headers=auth('manager@test.local'))

    recorded = verbs(client, world, auth)
    assert 'comment.added' in recorded
    assert 'member.removed' in recorded


def test_activity_can_be_filtered(client, world, auth):
    headers = auth('lead@test.local')
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)
    client.post(f"/api/issues/{world['own'].id}/comments",
                json={'body': 'done'}, headers=headers)

    moved = client.get(f"/api/projects/{world['project'].id}/activity",
                       query_string={'verb': 'issue.moved'}, headers=headers).get_json()
    assert [row['verb'] for row in moved['activity']] == ['issue.moved']


def test_issue_history_is_scoped_to_that_issue(client, world, auth):
    headers = auth('lead@test.local')
    client.patch(f"/api/issues/{world['own'].id}", json={'title': 'A'}, headers=headers)
    client.patch(f"/api/issues/{world['foreign'].id}", json={'title': 'B'}, headers=headers)

    response = client.get(f"/api/issues/{world['own'].id}/activity", headers=headers)
    rows = response.get_json()['activity']
    assert rows and all(row['issueId'] == world['own'].id for row in rows)


def test_completed_per_day_counts_transitions_not_edits(client, world, auth):
    """The bug this log exists to fix.

    Finishing an issue and then renaming it used to count as two completions,
    because the report read updated_at. It now reads the move itself.
    """
    headers = auth('lead@test.local')
    project_id = world['project'].id

    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'title': 'Renamed after finishing'}, headers=headers)

    report = client.get(f'/api/projects/{project_id}/analytics', headers=headers).get_json()
    # today_utc, not date.today: the rows are stamped UTC and the report now
    # buckets them in UTC. Asking in local time made this fail at 4am IST.
    today = today_utc().isoformat()
    by_day = {row['date']: row['count'] for row in report['completedByDay']}

    assert by_day[today] == 1
    assert sum(by_day.values()) == 1


def test_a_renamed_done_column_still_counts(client, world, auth):
    headers = auth('manager@test.local')
    project_id = world['project'].id

    client.patch(f"/api/projects/{project_id}/states/{world['states']['Done'].id}",
                 json={'name': 'Shipped'}, headers=headers)
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)

    report = client.get(f'/api/projects/{project_id}/analytics', headers=headers).get_json()
    assert sum(row['count'] for row in report['completedByDay']) == 1


def test_renaming_a_column_does_not_erase_past_completions(client, world, auth):
    """The reason the log keeps ids beside the names.

    Finish something in "Done", rename the column to "Shipped", and a report
    that matched on the recorded name would find nothing on the board called
    "Done" and quietly report a week with no work finished in it.
    """
    headers = auth('manager@test.local')
    project_id = world['project'].id

    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)
    client.patch(f"/api/projects/{project_id}/states/{world['states']['Done'].id}",
                 json={'name': 'Shipped'}, headers=headers)

    report = client.get(f'/api/projects/{project_id}/analytics', headers=headers).get_json()
    assert sum(row['count'] for row in report['completedByDay']) == 1


def test_a_completion_is_filed_on_the_day_it_actually_happened(client, world, auth):
    """Buckets and timestamps have to be on the same clock.

    The two tests above only sum, so they pass whichever bar the completion
    lands on. This one pins the bar. It writes the row at a fixed instant
    instead of relying on "now", so it gives the same answer at 4am as at noon
    — which is the whole point, since the bug it guards against was invisible
    for eighteen hours a day.
    """
    headers = auth('lead@test.local')
    project_id = world['project'].id

    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)

    entry = db.session.scalar(db.select(Activity).filter_by(verb='issue.moved'))
    assert entry is not None

    # Midday UTC, three days back: inside the 14-day window, and far enough
    # from midnight that no plausible server clock reads it as another date.
    stamped = datetime.combine(
        today_utc() - timedelta(days=3), time(12, 0), tzinfo=timezone.utc
    )
    entry.created_at = stamped
    db.session.commit()

    report = client.get(f'/api/projects/{project_id}/analytics', headers=headers).get_json()
    by_day = {row['date']: row['count'] for row in report['completedByDay']}

    assert by_day[stamped.date().isoformat()] == 1
    assert by_day[today_utc().isoformat()] == 0
    assert sum(by_day.values()) == 1
