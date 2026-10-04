"""The pure helpers, tested without a database."""

from datetime import timedelta
from types import SimpleNamespace

from app.models import build_board, initials_of, relative_time, utcnow


def test_initials():
    assert initials_of('Aditya Kundu') == 'AK'
    assert initials_of('Rohan Bose') == 'RB'
    assert initials_of('mary jane watson') == 'MW'   # first + last, not middle
    assert initials_of('Prince') == 'PR'
    assert initials_of('  ') == '??'
    assert initials_of(None) == '??'


def test_relative_time_reads_like_the_notifications_panel():
    now = utcnow()
    assert relative_time(now) == 'Just now'
    assert relative_time(now - timedelta(minutes=10)) == '10 mins ago'
    assert relative_time(now - timedelta(minutes=1)) == '1 min ago'
    assert relative_time(now - timedelta(hours=1)) == '1 hour ago'
    assert relative_time(now - timedelta(hours=5)) == '5 hours ago'
    assert relative_time(now - timedelta(days=1)) == 'Yesterday'
    assert relative_time(now - timedelta(days=3)) == '3 days ago'
    assert relative_time(now - timedelta(days=14)) == '2 weeks ago'
    assert relative_time(None) == ''


def _state(state_id, name, category, position):
    return SimpleNamespace(id=state_id, name=name, category=category, position=position, wip_limit=None)


def _issue(issue_id, state_id, position):
    stub = SimpleNamespace(id=issue_id, state_id=state_id, position=position)
    stub.to_dict = lambda: {'id': issue_id, 'stateId': state_id, 'position': position}
    return stub


def _project(states):
    return SimpleNamespace(states=states, issues=[])


def test_build_board_returns_every_state_in_workflow_order():
    project = _project([
        _state(3, 'Done', 'done', 2),
        _state(1, 'To do', 'todo', 0),
        _state(2, 'In progress', 'in_progress', 1),
    ])
    board = build_board(project, [])

    assert [col['name'] for col in board] == ['To do', 'In progress', 'Done']
    assert all(col['issues'] == [] for col in board)


def test_build_board_groups_and_orders_by_position():
    project = _project([_state(1, 'To do', 'todo', 0), _state(2, 'Done', 'done', 1)])
    board = build_board(project, [
        _issue(30, 2, 1),
        _issue(10, 1, 2),
        _issue(20, 1, 1),
    ])
    columns = {col['name']: col for col in board}

    assert [i['id'] for i in columns['To do']['issues']] == [20, 10]
    assert [i['id'] for i in columns['Done']['issues']] == [30]


def test_build_board_ignores_an_issue_from_another_board():
    project = _project([_state(1, 'To do', 'todo', 0)])
    board = build_board(project, [_issue(99, 42, 1)])
    assert sum(len(col['issues']) for col in board) == 0
