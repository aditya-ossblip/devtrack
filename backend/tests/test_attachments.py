"""Attachments: the upload path is where a file server usually gets it wrong."""

import io

from app.extensions import db
from app.models import Attachment


def upload(client, issue_id, headers, name='notes.txt', body=b'hello', field='file'):
    return client.post(
        f'/api/issues/{issue_id}/attachments',
        data={field: (io.BytesIO(body), name)},
        content_type='multipart/form-data',
        headers=headers,
    )


def upload_to_project(client, project_id, headers, name='report.pdf', body=b'hello'):
    return client.post(
        f'/api/projects/{project_id}/files',
        data={'file': (io.BytesIO(body), name)},
        content_type='multipart/form-data',
        headers=headers,
    )


def test_uploading_and_listing(client, world, auth):
    headers = auth('dev@test.local')
    response = upload(client, world['own'].id, headers)
    body = response.get_json()['attachment']

    assert response.status_code == 201
    assert body['filename'] == 'notes.txt'
    assert body['size'] == 5
    assert body['url'] == f"/api/attachments/{body['id']}"

    listed = client.get(f"/api/issues/{world['own'].id}/attachments", headers=headers)
    assert len(listed.get_json()['attachments']) == 1


def test_the_stored_name_is_never_the_uploaded_name(client, world, auth):
    """A crafted filename must not decide where the file lands."""
    upload(client, world['own'].id, auth('dev@test.local'), name='../../../etc/passwd.txt')

    stored = db.session.scalar(db.select(Attachment))
    assert stored.filename == 'passwd.txt'          # path stripped for display
    assert '/' not in stored.stored_name
    assert '..' not in stored.stored_name
    assert stored.stored_name.endswith('.txt')
    assert len(stored.stored_name) == 32 + 4        # 16 random bytes, hex, + ext


def test_an_extension_off_the_allowlist_is_refused(client, world, auth):
    response = upload(client, world['own'].id, auth('dev@test.local'),
                      name='payload.exe', body=b'MZ')
    assert response.status_code == 400
    assert 'not allowed' in response.get_json()['error']
    assert db.session.scalar(db.select(db.func.count(Attachment.id))) == 0


def test_a_file_over_the_limit_is_refused_and_not_kept(client, world, auth):
    from flask import current_app
    oversize = b'x' * (current_app.config['MAX_UPLOAD_BYTES'] + 1)

    response = upload(client, world['own'].id, auth('dev@test.local'),
                      name='big.log', body=oversize)
    assert response.status_code == 413
    assert db.session.scalar(db.select(db.func.count(Attachment.id))) == 0


def test_an_empty_file_is_refused(client, world, auth):
    response = upload(client, world['own'].id, auth('dev@test.local'), body=b'')
    assert response.status_code == 400


def test_missing_file_field_is_a_clear_error(client, world, auth):
    response = client.post(f"/api/issues/{world['own'].id}/attachments",
                           data={}, content_type='multipart/form-data',
                           headers=auth('dev@test.local'))
    assert response.status_code == 400
    assert 'Choose a file' in response.get_json()['error']


def test_download_returns_the_bytes_as_a_download(client, world, auth):
    headers = auth('dev@test.local')
    created = upload(client, world['own'].id, headers, name='page.svg',
                     body=b'<svg onload="alert(1)"></svg>').get_json()['attachment']

    response = client.get(created['url'], headers=headers)
    assert response.status_code == 200
    assert b'<svg' in response.data
    # as_attachment, so an uploaded SVG or HTML can never execute in our origin
    assert 'attachment' in response.headers['Content-Disposition']


def test_only_the_uploader_or_a_manager_can_delete(client, world, auth):
    created = upload(client, world['own'].id, auth('dev@test.local')).get_json()['attachment']

    assert client.delete(created['url'], headers=auth('other@test.local')).status_code == 403
    assert client.delete(created['url'], headers=auth('manager@test.local')).status_code == 204
    assert db.session.scalar(db.select(db.func.count(Attachment.id))) == 0


def test_a_non_member_cannot_reach_an_attachment(client, world, auth):
    created = upload(client, world['own'].id, auth('dev@test.local')).get_json()['attachment']
    client.post('/api/auth/register', json={
        'name': 'Out Sider', 'email': 'out@test.local', 'password': 'password123'})

    assert client.get(created['url'], headers=auth('out@test.local')).status_code == 404


def test_attachments_appear_on_the_issue_and_are_counted(client, world, auth):
    headers = auth('dev@test.local')
    upload(client, world['own'].id, headers)

    detail = client.get(f"/api/issues/{world['own'].id}", headers=headers).get_json()
    assert detail['issue']['attachmentCount'] == 1
    assert len(detail['issue']['attachments']) == 1



# --------------------------------------------------------------------------
# Project files.
#
# A file belongs to the project. Attaching it to an issue is optional, and the
# Files page is the one place everything shows up — which is the whole reason
# a team would stop passing documents around in a group chat.
# --------------------------------------------------------------------------

def test_a_file_can_belong_to_the_project_rather_than_a_task(client, world, auth):
    headers = auth('dev@test.local')
    project_id = world['project'].id

    created = upload_to_project(client, project_id, headers)
    assert created.status_code == 201

    body = created.get_json()['file']
    assert body['filename'] == 'report.pdf'
    assert body['issueId'] is None
    assert body['issueKey'] is None
    assert body['projectId'] == project_id


def test_the_files_list_includes_task_attachments_too(client, world, auth):
    """The point of the page: you do not have to remember where a file went."""
    headers = auth('dev@test.local')
    project_id = world['project'].id

    upload_to_project(client, project_id, headers, name='deck.pptx')
    upload(client, world['own'].id, headers, name='screenshot.png')

    listed = client.get(f'/api/projects/{project_id}/files', headers=headers).get_json()
    names = {f['filename'] for f in listed['files']}
    assert names == {'deck.pptx', 'screenshot.png'}

    # ...and each one says what it is for.
    by_name = {f['filename']: f for f in listed['files']}
    assert by_name['deck.pptx']['issueKey'] is None
    assert by_name['screenshot.png']['issueKey'] == world['own'].key


def test_the_scope_filter_narrows_to_files_on_no_task(client, world, auth):
    headers = auth('dev@test.local')
    project_id = world['project'].id
    upload_to_project(client, project_id, headers, name='deck.pptx')
    upload(client, world['own'].id, headers, name='screenshot.png')

    only = client.get(f'/api/projects/{project_id}/files',
                      query_string={'scope': 'project'}, headers=headers).get_json()
    assert [f['filename'] for f in only['files']] == ['deck.pptx']


def test_deleting_a_task_keeps_its_files(client, world, auth):
    """A file outlives the task it happened to hang off.

    Deleting an issue used to delete its attachments with it, which is fine
    for a screenshot and wrong for the report somebody attached to the wrong
    ticket. The file stays, and turns into a project file.
    """
    project_id = world['project'].id
    upload(client, world['own'].id, auth('dev@test.local'), name='report.pdf')

    deleted = client.delete(f"/api/issues/{world['own'].id}", headers=auth('lead@test.local'))
    assert deleted.status_code == 204

    listed = client.get(f'/api/projects/{project_id}/files',
                        headers=auth('dev@test.local')).get_json()
    assert [f['filename'] for f in listed['files']] == ['report.pdf']
    assert listed['files'][0]['issueId'] is None


def test_a_stranger_cannot_see_or_upload_project_files(client, world, auth, new_user):
    """Files inherit the project's isolation, not a looser rule of their own."""
    project_id = world['project'].id
    upload_to_project(client, project_id, auth('dev@test.local'))

    new_user('Stranger', 'stranger@test.local')
    headers = auth('stranger@test.local')

    assert client.get(f'/api/projects/{project_id}/files', headers=headers).status_code == 404
    assert upload_to_project(client, project_id, headers).status_code == 404


def test_only_the_uploader_or_a_manager_may_delete_a_file(client, world, auth):
    project_id = world['project'].id
    created = upload_to_project(client, project_id, auth('dev@test.local')).get_json()['file']

    # Another developer on the project did not put it there.
    assert client.delete(f"/api/attachments/{created['id']}",
                         headers=auth('other@test.local')).status_code == 403
    assert client.delete(f"/api/attachments/{created['id']}",
                         headers=auth('manager@test.local')).status_code == 204
