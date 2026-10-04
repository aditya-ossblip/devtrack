"""Every list endpoint answers the same shape."""

from app.extensions import db
from app.models import Issue


def make_issues(client, world, auth, count):
    headers = auth('lead@test.local')
    for n in range(count):
        client.post('/api/issues',
                    json={'projectId': world['project'].id, 'title': f'Bulk issue {n}'},
                    headers=headers)


def test_meta_describes_where_the_page_sits(client, world, auth):
    make_issues(client, world, auth, 8)          # + the 2 from the fixture
    response = client.get('/api/issues',
                          query_string={'projectId': world['project'].id, 'perPage': 4},
                          headers=auth('lead@test.local'))
    body = response.get_json()

    assert len(body['issues']) == 4
    assert body['meta'] == {
        'page': 1, 'perPage': 4, 'total': 10, 'pages': 3, 'hasMore': True,
    }


def test_the_last_page_reports_no_more(client, world, auth):
    make_issues(client, world, auth, 8)
    body = client.get('/api/issues',
                      query_string={'projectId': world['project'].id, 'perPage': 4, 'page': 3},
                      headers=auth('lead@test.local')).get_json()

    assert len(body['issues']) == 2
    assert body['meta']['hasMore'] is False


def test_pages_do_not_overlap_or_skip(client, world, auth):
    make_issues(client, world, auth, 8)
    headers = auth('lead@test.local')

    seen = []
    for page in (1, 2, 3):
        body = client.get('/api/issues',
                          query_string={'projectId': world['project'].id, 'perPage': 4, 'page': page},
                          headers=headers).get_json()
        seen.extend(issue['id'] for issue in body['issues'])

    assert len(seen) == len(set(seen)) == 10


def test_per_page_is_clamped(client, world, auth):
    body = client.get('/api/issues',
                      query_string={'projectId': world['project'].id, 'perPage': 5000},
                      headers=auth('lead@test.local')).get_json()
    assert body['meta']['perPage'] == 100        # MAX_PER_PAGE


def test_rubbish_paging_values_fall_back_to_the_default(client, world, auth):
    body = client.get('/api/issues',
                      query_string={'projectId': world['project'].id, 'page': 'abc', 'perPage': '-4'},
                      headers=auth('lead@test.local')).get_json()
    assert body['meta']['page'] == 1
    assert body['meta']['perPage'] == 1          # clamped to the floor, not negative


def test_users_notifications_and_activity_all_carry_meta(client, world, auth):
    headers = auth('lead@test.local')
    client.patch(f"/api/issues/{world['own'].id}",
                 json={'stateId': world['states']['Done'].id}, headers=headers)

    for path in ('/api/users',
                 '/api/notifications',
                 f"/api/projects/{world['project'].id}/activity"):
        body = client.get(path, headers=auth('dev@test.local')).get_json()
        assert 'meta' in body, path
        # A superset is fine: /api/users adds `exact` to say it is a lookup
        # rather than a page of a list. These five are the contract.
        assert {'page', 'perPage', 'total', 'pages', 'hasMore'} <= set(body['meta']), path


def test_an_empty_result_still_has_sane_meta(client, world, auth):
    body = client.get('/api/users', query_string={'q': 'nobodyatall'},
                      headers=auth('lead@test.local')).get_json()
    assert body['users'] == []
    assert body['meta']['total'] == 0
    assert body['meta']['pages'] == 1
    assert body['meta']['hasMore'] is False
