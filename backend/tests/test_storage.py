"""Where files go, and how much room a project gets.

The S3 tests use a small in-memory stand-in for the bucket, so they run
without a network, an account or boto3's own test tools.
"""

import io

import pytest

from app.extensions import db
from app.models import Attachment
from app.storage import LocalStorage, S3Storage, build_storage, set_storage


class FakeS3:
    """Just enough of boto3's S3 client for the app: put, get, delete."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[(Bucket, Key)] = (bytes(Body), ContentType)

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            error = Exception('NoSuchKey')
            error.response = {'Error': {'Code': 'NoSuchKey'}}
            raise error
        return {'Body': io.BytesIO(self.objects[(Bucket, Key)][0])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def upload(client, project_id, headers, name='notes.txt', body=b'hello'):
    return client.post(
        f'/api/projects/{project_id}/files',
        data={'file': (io.BytesIO(body), name)},
        content_type='multipart/form-data',
        headers=headers,
    )


# ------------------------------------------------------------------- quota

def test_a_project_cannot_go_past_its_file_space(client, world, auth, app):
    """160 KB per project in tests, 64 KB per file: two fit, the third does not."""
    headers = auth('dev@test.local')
    project_id = world['project'].id
    chunk = b'x' * (60 * 1024)

    assert upload(client, project_id, headers, 'a.txt', chunk).status_code == 201
    assert upload(client, project_id, headers, 'b.txt', chunk).status_code == 201

    third = upload(client, project_id, headers, 'c.txt', chunk)
    assert third.status_code == 413
    assert 'file space' in third.get_json()['error']
    assert db.session.scalar(db.select(db.func.count(Attachment.id))) == 2

    # Deleting a file makes room again.
    first = db.session.scalar(db.select(Attachment).filter_by(filename='a.txt'))
    assert client.delete(f'/api/attachments/{first.id}', headers=headers).status_code == 204
    assert upload(client, project_id, headers, 'c.txt', chunk).status_code == 201


def test_the_files_list_reports_space_used(client, world, auth, app):
    headers = auth('dev@test.local')
    project_id = world['project'].id
    upload(client, project_id, headers, body=b'12345')

    usage = client.get(f'/api/projects/{project_id}/files', headers=headers).get_json()['usage']
    assert usage == {
        'used': 5,
        'limit': app.config['PROJECT_STORAGE_BYTES'],
        'maxFileSize': app.config['MAX_UPLOAD_BYTES'],
    }


# ---------------------------------------------------------------- S3 bucket

@pytest.fixture()
def bucket(app):
    fake = FakeS3()
    set_storage(app, S3Storage('devtrack-files', fake))
    return fake


def test_uploads_go_to_the_bucket_and_come_back(client, world, auth, bucket):
    headers = auth('dev@test.local')
    created = upload(client, world['project'].id, headers, 'deck.pdf', b'%PDF-1.7').get_json()['file']

    stored = db.session.get(Attachment, created['id']).stored_name
    assert ('devtrack-files', f'uploads/{stored}') in bucket.objects

    response = client.get(created['url'], headers=headers)
    assert response.status_code == 200
    assert response.data == b'%PDF-1.7'
    assert 'attachment' in response.headers['Content-Disposition']


def test_deleting_removes_it_from_the_bucket(client, world, auth, bucket):
    headers = auth('dev@test.local')
    created = upload(client, world['project'].id, headers).get_json()['file']

    assert client.delete(created['url'], headers=headers).status_code == 204
    assert bucket.objects == {}


def test_a_file_missing_from_the_bucket_is_a_clear_410(client, world, auth, bucket):
    headers = auth('dev@test.local')
    created = upload(client, world['project'].id, headers).get_json()['file']
    bucket.objects.clear()

    assert client.get(created['url'], headers=headers).status_code == 410


def test_strangers_still_cannot_download_from_the_bucket(client, world, auth, bucket, new_user):
    created = upload(client, world['project'].id, auth('dev@test.local')).get_json()['file']
    new_user('Stranger', 'stranger@test.local')

    assert client.get(created['url'], headers=auth('stranger@test.local')).status_code == 404


# ----------------------------------------------------------------- settings

def test_s3_without_keys_is_refused_at_startup():
    with pytest.raises(RuntimeError) as caught:
        build_storage({'STORAGE_BACKEND': 's3', 'S3_BUCKET': 'x'})
    assert 'S3_ACCESS_KEY_ID' in str(caught.value)


def test_an_unknown_backend_is_refused():
    with pytest.raises(RuntimeError):
        build_storage({'STORAGE_BACKEND': 'ftp'})


@pytest.mark.parametrize('key', ['../escape.txt', 'a/b.txt', 'a\\b.txt'])
def test_storage_refuses_keys_that_could_leave_its_folder(tmp_path, key):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).save(key, b'x', 'text/plain')
    with pytest.raises(ValueError):
        S3Storage('b', FakeS3()).save(key, b'x', 'text/plain')
