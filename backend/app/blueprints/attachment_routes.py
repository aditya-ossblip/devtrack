"""Files.

A file belongs to a **project**. It may also point at one issue inside that
project, which is what "attach to this task" means — but the project is the
owner either way, so the Files page can list everything a team has uploaded
without caring how it got there.

Three rules do most of the safety work here: the stored filename is generated
rather than taken from the upload, the extension must be on an allowlist, and
the size is measured from what was actually written rather than from the
header the client sent.
"""

import os
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from ..auth import can_manage, current_user, require_project, token_required
from ..errors import ApiError
from ..events import broadcast
from ..extensions import db
from ..history import paginate, record
from ..models import Attachment, Issue

bp = Blueprint('attachments', __name__, url_prefix='/api')


def _upload_dir() -> Path:
    directory = Path(current_app.config['UPLOAD_DIR'])
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _extension(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _load_issue(issue_id: int) -> Issue:
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        raise ApiError('That issue does not exist.', 404)
    require_project(issue.project_id)
    return issue


def _store(upload, *, project_id, issue=None, actor):
    """Write one uploaded file to disk and record it. Shared by both routes."""
    original = os.path.basename(upload.filename)[:255]
    extension = _extension(original)
    allowed = current_app.config['ALLOWED_UPLOAD_EXTENSIONS']
    if extension not in allowed:
        raise ApiError(
            f'.{extension or "?"} files are not allowed. '
            f'Accepted: {", ".join(sorted(allowed))}.'
        )

    # The name on disk is ours, never theirs: "../../etc/passwd" and
    # "report.pdf" both end up as a random token with a checked extension.
    stored_name = f'{secrets.token_hex(16)}.{extension}'
    destination = _upload_dir() / stored_name
    upload.save(destination)

    size = destination.stat().st_size
    limit = current_app.config['MAX_UPLOAD_BYTES']
    if size > limit:
        # Measured after writing, because Content-Length is whatever the
        # client felt like claiming.
        destination.unlink(missing_ok=True)
        raise ApiError(f'That file is larger than the {limit // (1024 * 1024)}MB limit.', 413)
    if size == 0:
        destination.unlink(missing_ok=True)
        raise ApiError('That file is empty.')

    attachment = Attachment(
        project_id=project_id,
        issue_id=issue.id if issue is not None else None,
        uploader_id=actor.id,
        filename=original,
        stored_name=stored_name,
        content_type=upload.mimetype or 'application/octet-stream',
        size=size,
    )
    db.session.add(attachment)
    record('attachment.added', project_id=project_id, actor=actor, issue=issue,
           field='attachment', after=original,
           subject=None if issue is not None else original)
    db.session.commit()

    broadcast('attachment:added',
              {'projectId': project_id, 'issueId': attachment.issue_id,
               'attachment': attachment.to_dict()},
              project_id)
    return attachment


# --------------------------------------------------------------------------
# Project files — everything the team has uploaded, in one place
# --------------------------------------------------------------------------

@bp.get('/projects/<int:project_id>/files')
@token_required
def list_project_files(project_id: int):
    """Every file in the project, newest first.

    Includes files attached to issues, because the point of this list is that
    you do not have to remember which task somebody put the report on.
    `?scope=project` narrows it to files that belong to no issue.
    """
    project = require_project(project_id)

    query = db.select(Attachment).filter(Attachment.project_id == project.id)
    if request.args.get('scope') == 'project':
        query = query.filter(Attachment.issue_id.is_(None))
    query = query.order_by(Attachment.created_at.desc(), Attachment.id.desc())

    files, meta = paginate(query)
    return jsonify(files=files, meta=meta)


@bp.post('/projects/<int:project_id>/files')
@token_required
def upload_project_file(project_id: int):
    """Upload a file that belongs to the project rather than to a task.

    The final report, the slide deck, the source archive — the things a team
    would otherwise put in a Drive folder and paste a link to.
    """
    project = require_project(project_id)
    upload = request.files.get('file')
    if upload is None or not upload.filename:
        raise ApiError('Choose a file to upload.')

    attachment = _store(upload, project_id=project.id, actor=current_user())
    return jsonify(file=attachment.to_dict()), 201


# --------------------------------------------------------------------------
# Issue attachments — the same rows, with an issue attached
# --------------------------------------------------------------------------

@bp.get('/issues/<int:issue_id>/attachments')
@token_required
def list_attachments(issue_id: int):
    issue = _load_issue(issue_id)
    return jsonify(attachments=[a.to_dict() for a in issue.attachments])


@bp.post('/issues/<int:issue_id>/attachments')
@token_required
def upload_attachment(issue_id: int):
    issue = _load_issue(issue_id)
    upload = request.files.get('file')
    if upload is None or not upload.filename:
        raise ApiError('Choose a file to attach.')

    attachment = _store(upload, project_id=issue.project_id, issue=issue, actor=current_user())
    return jsonify(attachment=attachment.to_dict()), 201


# --------------------------------------------------------------------------
# Download and delete — the same for both kinds
# --------------------------------------------------------------------------

@bp.get('/attachments/<int:attachment_id>')
@token_required
def download_attachment(attachment_id: int):
    attachment = db.session.get(Attachment, attachment_id)
    if attachment is None:
        raise ApiError('That file does not exist.', 404)
    require_project(attachment.project_id)

    path = _upload_dir() / attachment.stored_name
    if not path.exists():
        raise ApiError('That file is missing from storage.', 410)

    # as_attachment so a stored .svg or .html is downloaded rather than
    # rendered in the origin — an uploaded page must never run as us.
    return send_file(
        path,
        mimetype=attachment.content_type,
        as_attachment=True,
        download_name=attachment.filename,
    )


@bp.delete('/attachments/<int:attachment_id>')
@token_required
def delete_attachment(attachment_id: int):
    user = current_user()
    attachment = db.session.get(Attachment, attachment_id)
    if attachment is None:
        raise ApiError('That file does not exist.', 404)

    project = require_project(attachment.project_id)
    if attachment.uploader_id != user.id and not can_manage(user, project):
        raise ApiError('You can only remove files you uploaded.', 403)

    (_upload_dir() / attachment.stored_name).unlink(missing_ok=True)
    record('attachment.deleted', project_id=project.id, actor=user,
           issue=attachment.issue, field='attachment', before=attachment.filename,
           subject=None if attachment.issue is not None else attachment.filename)
    issue_id = attachment.issue_id
    db.session.delete(attachment)
    db.session.commit()

    broadcast('attachment:deleted',
              {'projectId': project.id, 'issueId': issue_id, 'attachmentId': attachment_id},
              project.id)
    return '', 204
