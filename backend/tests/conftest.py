import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Issue, Project, ProjectMember, Sprint, User  # noqa: E402


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(name, email, role, password='password123'):
    user = User(name=name, email=email, role=role, title='')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture()
def new_user(app):
    """Make an extra account mid-test.

    A fixture rather than a bare import, because `make_user` touches the
    session and only works inside the app context `app` sets up.
    """

    def _make(name, email, role='developer'):
        user = make_user(name, email, role)
        db.session.commit()
        return user

    return _make


@pytest.fixture()
def join(app):
    """Add someone to a project with a given project role."""

    def _join(project, user, role='developer'):
        db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))
        db.session.commit()

    return _join


@pytest.fixture()
def world(app):
    """A lead, a manager, two developers, one project, two issues."""
    lead = make_user('Aditya Kundu', 'lead@test.local', 'developer')
    manager = make_user('Arjun Bhatt', 'manager@test.local', 'manager')
    dev = make_user('Rohan Bose', 'dev@test.local', 'developer')
    other = make_user('Divya Das', 'other@test.local', 'developer')

    project = Project(key='DEV', name='DevTrack v1.0', description='', lead_id=lead.id)
    db.session.add(project)
    db.session.flush()
    project.install_default_workflow()
    db.session.flush()

    for user, role in ((lead, 'admin'), (manager, 'manager'), (dev, 'developer'), (other, 'developer')):
        db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))

    states = {state.name: state for state in project.states}

    own = Issue(
        key=project.next_issue_key(), project_id=project.id, title='Dev own issue',
        type='task', priority='medium', state_id=states['To do'].id,
        assignee_id=dev.id, reporter_id=lead.id, position=1, story_points=3,
    )
    foreign = Issue(
        key=project.next_issue_key(), project_id=project.id, title='Someone elses issue',
        type='bug', priority='high', state_id=states['To do'].id,
        assignee_id=other.id, reporter_id=lead.id, position=2, story_points=5,
    )
    db.session.add_all([own, foreign])
    db.session.commit()

    return {
        'lead': lead, 'manager': manager, 'dev': dev, 'other': other,
        'project': project, 'states': states, 'own': own, 'foreign': foreign,
    }


@pytest.fixture()
def auth(client):
    """auth(email) -> {'Authorization': 'Bearer ...'}"""

    def _headers(email, password='password123'):
        response = client.post('/api/auth/login', json={'email': email, 'password': password})
        assert response.status_code == 200, response.get_json()
        return {'Authorization': f"Bearer {response.get_json()['token']}"}

    return _headers
