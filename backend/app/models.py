"""DevTrack domain model, following Jira's vocabulary.

The shape here is deliberately close to Jira's: a project owns a workflow, a
workflow is an ordered list of states, and an issue sits in exactly one state.
Everything the board renders is derived from those three things, so adding a
column is a row in `workflow_states` rather than a code change.
"""

from datetime import date, datetime, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

ROLES = ('admin', 'manager', 'developer')

# A state's *category* is what the UI colours and what reports count. Teams can
# rename and reorder states freely; the category keeps "done" meaningful.
STATE_CATEGORIES = ('todo', 'in_progress', 'done')

ISSUE_TYPES = ('epic', 'story', 'task', 'bug', 'subtask')
PRIORITIES = ('highest', 'high', 'medium', 'low', 'lowest')
PRIORITY_ORDER = {name: index for index, name in enumerate(PRIORITIES)}

SPRINT_STATES = ('future', 'active', 'completed')

# What an activity row can record. Kept small and closed: a free-text verb
# column turns the log into prose nobody can query.
ACTIVITY_VERBS = (
    'issue.created', 'issue.moved', 'issue.updated', 'issue.deleted',
    'issue.assigned', 'comment.added', 'comment.deleted',
    'member.added', 'member.removed', 'member.role_changed',
    'sprint.started', 'sprint.completed',
    'attachment.added', 'attachment.deleted',
)
NOTIFICATION_TYPES = ('assigned', 'mentioned', 'done', 'deadline', 'member', 'comment')

# Created for every new project. Teams edit them afterwards in project settings.
DEFAULT_WORKFLOW = (
    ('To do', 'todo'),
    ('In progress', 'in_progress'),
    ('In review', 'in_progress'),
    ('Done', 'done'),
)


def utcnow():
    return datetime.now(timezone.utc)


def today_utc() -> date:
    """Today, on the same clock every stored timestamp already uses.

    `date.today()` is the *server's* local date, and for several hours out of
    every 24 that is a different day from UTC — while every instant in this
    database is stamped UTC by `utcnow()` above. Mixing the two files a
    completion under the wrong day on the report and flips `overdue` at the
    wrong hour. This shipped as a bug: the analytics test passed all afternoon
    and failed at 4am IST, when the local date had rolled over and the UTC one
    had not.

    The genuinely correct answer is the *viewer's* date, which needs their UTC
    offset sent with the request. Until that exists UTC is the honest default:
    it is at least the same for every viewer, which the server's own timezone
    is not.
    """
    return utcnow().date()


def initials_of(name: str) -> str:
    """"Aditya Kundu" -> "AK". Single names give their first two letters."""
    parts = [part for part in (name or '').split() if part]
    if not parts:
        return '??'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def relative_time(moment: datetime) -> str:
    """A short "10 mins ago" string. The frontend prints this as-is."""
    if moment is None:
        return ''
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = int((utcnow() - moment).total_seconds())

    if seconds < 60:
        return 'Just now'
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days == 1:
        return 'Yesterday'
    if days < 7:
        return f'{days} days ago'
    weeks = days // 7
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False, unique=True, index=True)
    # Nullable: an account created through Google has never had a password,
    # and storing an unusable placeholder hash would make "has a password" a
    # question you answer by string-matching.
    password_hash = db.Column(db.String(255), nullable=True)
    # Google's stable user id. Matched on before email, because an address can
    # change hands and this cannot.
    google_sub = db.Column(db.String(40), nullable=True, unique=True, index=True)
    role = db.Column(db.String(20), nullable=False, default='developer')
    title = db.Column(db.String(120), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def set_password(self, raw: str) -> None:
        method = current_app.config.get('PASSWORD_HASH_METHOD', 'scrypt')
        self.password_hash = generate_password_hash(raw, method=method)

    def check_password(self, raw: str) -> bool:
        # A Google-only account has no hash to check against, and must not be
        # reachable with an empty password.
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw)

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def initials(self) -> str:
        return initials_of(self.name)

    def to_dict(self) -> dict:
        # No email here: the member list does not need it, and the fewer places
        # an address travels the better.
        return {
            'id': self.id,
            'name': self.name,
            'initials': self.initials,
            'role': self.role.capitalize(),
            'title': self.title,
        }

    def to_private_dict(self) -> dict:
        """The signed-in user's own record — includes their email."""
        return {
            **self.to_dict(),
            'email': self.email,
            # So the profile editor can offer "set a password" rather than
            # "change password" to someone who has never had one.
            'hasPassword': self.has_password,
            'googleLinked': bool(self.google_sub),
        }


class ProjectMember(db.Model):
    __tablename__ = 'project_members'

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role = db.Column(db.String(20), nullable=False, default='developer')
    joined_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship('Project', back_populates='memberships')
    user = db.relationship('User')

    def to_dict(self) -> dict:
        return {**self.user.to_dict(), 'projectRole': self.role.capitalize()}


# --------------------------------------------------------------------------
# Projects and their workflow
# --------------------------------------------------------------------------

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(10), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    lead_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issue_counter = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    lead = db.relationship('User', foreign_keys=[lead_id])
    issues = db.relationship('Issue', back_populates='project', cascade='all, delete-orphan')
    memberships = db.relationship('ProjectMember', back_populates='project', cascade='all, delete-orphan')
    states = db.relationship(
        'WorkflowState',
        back_populates='project',
        cascade='all, delete-orphan',
        order_by='WorkflowState.position',
    )
    sprints = db.relationship('Sprint', back_populates='project', cascade='all, delete-orphan')
    transitions = db.relationship(
        'WorkflowTransition',
        cascade='all, delete-orphan',
        foreign_keys='WorkflowTransition.project_id',
    )

    def next_issue_key(self) -> str:
        """DEV-1, DEV-2, ... Counter lives on the project so keys never reuse."""
        self.issue_counter += 1
        return f'{self.key}-{self.issue_counter}'

    def install_default_workflow(self) -> None:
        for position, (name, category) in enumerate(DEFAULT_WORKFLOW):
            db.session.add(
                WorkflowState(project=self, name=name, category=category, position=position)
            )

    def to_dict(self, counts: bool = True) -> dict:
        data = {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'leadId': self.lead_id,
            'leadName': self.lead.name if self.lead else None,
            'memberCount': len(self.memberships),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }
        if counts:
            tally = {category: 0 for category in STATE_CATEGORIES}
            for issue in self.issues:
                if issue.state and issue.state.category in tally:
                    tally[issue.state.category] += 1
            data['issueCounts'] = tally
            data['issueTotal'] = len(self.issues)
        return data


class WorkflowState(db.Model):
    """One column on the board. Editable per project — that is the workflow."""

    __tablename__ = 'workflow_states'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    category = db.Column(db.String(20), nullable=False, default='todo')
    position = db.Column(db.Integer, nullable=False, default=0)
    wip_limit = db.Column(db.Integer, nullable=True)

    project = db.relationship('Project', back_populates='states')
    issues = db.relationship('Issue', back_populates='state')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'position': self.position,
            'wipLimit': self.wip_limit,
        }


class WorkflowTransition(db.Model):
    """An allowed move between two states.

    If a project has no transition rows, every move is allowed — which is what
    most teams want and keeps the default simple. Add rows to lock a workflow
    down; `Project.allows_transition` falls back to permissive when empty.
    """

    __tablename__ = 'workflow_transitions'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    from_state_id = db.Column(db.Integer, db.ForeignKey('workflow_states.id'), nullable=False)
    to_state_id = db.Column(db.Integer, db.ForeignKey('workflow_states.id'), nullable=False)

    from_state = db.relationship('WorkflowState', foreign_keys=[from_state_id])
    to_state = db.relationship('WorkflowState', foreign_keys=[to_state_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'fromStateId': self.from_state_id,
            'toStateId': self.to_state_id,
        }


class Sprint(db.Model):
    __tablename__ = 'sprints'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    goal = db.Column(db.String(400), nullable=False, default='')
    state = db.Column(db.String(20), nullable=False, default='future')
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship('Project', back_populates='sprints')
    issues = db.relationship('Issue', back_populates='sprint')

    def to_dict(self) -> dict:
        points = sum(issue.story_points or 0 for issue in self.issues)
        done = sum(
            issue.story_points or 0
            for issue in self.issues
            if issue.state and issue.state.category == 'done'
        )
        return {
            'id': self.id,
            'name': self.name,
            'goal': self.goal,
            'state': self.state,
            'startDate': self.start_date.isoformat() if self.start_date else None,
            'endDate': self.end_date.isoformat() if self.end_date else None,
            'issueCount': len(self.issues),
            'points': points,
            'pointsDone': done,
        }


# --------------------------------------------------------------------------
# Issues
# --------------------------------------------------------------------------

class Issue(db.Model):
    __tablename__ = 'issues'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(24), nullable=False, unique=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    type = db.Column(db.String(20), nullable=False, default='task')
    priority = db.Column(db.String(20), nullable=False, default='medium')

    state_id = db.Column(db.Integer, db.ForeignKey('workflow_states.id'), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # An epic is just an issue of type 'epic'; children point back at it.
    epic_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=True, index=True)

    story_points = db.Column(db.Integer, nullable=True)
    # Comma-separated rather than a join table: labels are free text the UI
    # filters on, and a table here would buy nothing but joins.
    labels = db.Column(db.String(400), nullable=False, default='')

    due_date = db.Column(db.Date, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    project = db.relationship('Project', back_populates='issues')
    state = db.relationship('WorkflowState', back_populates='issues')
    sprint = db.relationship('Sprint', back_populates='issues')
    assignee = db.relationship('User', foreign_keys=[assignee_id])
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    epic = db.relationship('Issue', remote_side=[id], foreign_keys=[epic_id])
    comments = db.relationship(
        'Comment',
        back_populates='issue',
        cascade='all, delete-orphan',
        order_by='Comment.created_at',
    )
    # No delete cascade, deliberately. A file belongs to the project, so
    # deleting the task it happened to be attached to must not destroy it —
    # SQLAlchemy nulls `issue_id` instead and the file stays in Files, where
    # the team can still find it. Deleting a task used to delete the report
    # somebody had attached to it.
    attachments = db.relationship(
        'Attachment',
        back_populates='issue',
        cascade='save-update, merge',
        order_by='Attachment.created_at',
    )

    @property
    def is_overdue(self) -> bool:
        """Never stored — always derived, so it cannot go stale in the table."""
        if self.due_date is None:
            return False
        if self.state and self.state.category == 'done':
            return False
        return self.due_date < today_utc()

    @property
    def label_list(self) -> list:
        return [label for label in (self.labels or '').split(',') if label]

    def set_labels(self, labels) -> None:
        cleaned = []
        for label in labels or []:
            slug = str(label).strip().replace(',', '')
            if slug and slug not in cleaned:
                cleaned.append(slug)
        self.labels = ','.join(cleaned)

    def to_dict(self, with_comments: bool = False) -> dict:
        data = {
            'id': self.id,
            'key': self.key,
            'projectId': self.project_id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'priority': self.priority,
            'stateId': self.state_id,
            'stateName': self.state.name if self.state else None,
            'stateCategory': self.state.category if self.state else None,
            'assignee': self.assignee.initials if self.assignee else None,
            'assigneeId': self.assignee_id,
            'assigneeName': self.assignee.name if self.assignee else None,
            'reporterId': self.reporter_id,
            'reporterName': self.reporter.name if self.reporter else None,
            'epicId': self.epic_id,
            'epicKey': self.epic.key if self.epic else None,
            'epicTitle': self.epic.title if self.epic else None,
            'sprintId': self.sprint_id,
            'storyPoints': self.story_points,
            'labels': self.label_list,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'overdue': self.is_overdue,
            'position': self.position,
            'commentCount': len(self.comments),
            'attachmentCount': len(self.attachments),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
        if with_comments:
            data['comments'] = [comment.to_dict() for comment in self.comments]
            data['attachments'] = [a.to_dict() for a in self.attachments]
        return data


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    issue = db.relationship('Issue', back_populates='comments')
    author = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'issueId': self.issue_id,
            'body': self.body,
            'authorId': self.author_id,
            'authorName': self.author.name if self.author else None,
            'authorInitials': self.author.initials if self.author else '??',
            'time': relative_time(self.created_at),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'edited': bool(self.updated_at and self.created_at and self.updated_at > self.created_at),
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=True)
    type = db.Column(db.String(20), nullable=False, default='member')
    text = db.Column(db.String(400), nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': self.type,
            'text': self.text,
            'projectId': self.project_id,
            'issueId': self.issue_id,
            'time': relative_time(self.created_at),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'read': self.read_at is not None,
        }


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------

class Activity(db.Model):
    """Who changed what, when.

    Written by the routes that mutate things, never inferred afterwards. This
    is what makes the completed-per-day report exact: before it existed the
    report guessed from `Issue.updated_at`, which moves for any edit at all,
    so renaming a finished issue counted as finishing it again.
    """

    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    verb = db.Column(db.String(32), nullable=False, index=True)
    field = db.Column(db.String(40), nullable=True)
    from_value = db.Column(db.String(200), nullable=True)
    to_value = db.Column(db.String(200), nullable=True)
    # Names are what a person reads; ids are what a report counts. Rename a
    # column from "Done" to "Shipped" and every completion recorded before the
    # rename would drop out of the analytics, because the name written into
    # history no longer matches any column on the board. These two carry the
    # workflow state ids for moves, and are deliberately not foreign keys - the
    # history has to outlive the column it refers to.
    from_ref = db.Column(db.Integer, nullable=True)
    to_ref = db.Column(db.Integer, nullable=True)
    # The issue key is copied in rather than joined, so the history survives
    # the issue being deleted.
    subject = db.Column(db.String(240), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    actor = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'projectId': self.project_id,
            'issueId': self.issue_id,
            'verb': self.verb,
            'field': self.field,
            'from': self.from_value,
            'to': self.to_value,
            'subject': self.subject,
            'actorId': self.actor_id,
            'actorName': self.actor.name if self.actor else 'Someone',
            'actorInitials': self.actor.initials if self.actor else '??',
            'time': relative_time(self.created_at),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }


class Attachment(db.Model):
    """A file, belonging to a project and optionally to one issue inside it.

    The project is the owner, not the issue. That is what lets the Files page
    list everything in one place, and what lets a file exist that is simply
    "the project's" — the final report, the presentation — with no task it
    naturally hangs off. A file attached to an issue is the same row with
    `issue_id` filled in, so nothing has to be moved or copied when one is
    promoted to the other.
    """

    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    # Nullable: a project file is not attached to any task.
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=True, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # What the user called it, and what it is called on disk. They are never
    # the same: the stored name is generated, so a crafted filename cannot
    # escape the upload directory or collide with someone else's file.
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(80), nullable=False, unique=True)
    content_type = db.Column(db.String(120), nullable=False, default='application/octet-stream')
    size = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship('Project')
    issue = db.relationship('Issue', back_populates='attachments')
    uploader = db.relationship('User')

    @property
    def human_size(self) -> str:
        size = float(self.size or 0)
        for unit in ('B', 'KB', 'MB'):
            if size < 1024 or unit == 'MB':
                return f'{size:.0f} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} MB'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'projectId': self.project_id,
            'issueId': self.issue_id,
            # The issue's key and title travel with the file so the Files page
            # can say what a file is *for* without a second request per row.
            'issueKey': self.issue.key if self.issue else None,
            'issueTitle': self.issue.title if self.issue else None,
            'filename': self.filename,
            'contentType': self.content_type,
            'size': self.size,
            'humanSize': self.human_size,
            'uploaderId': self.uploader_id,
            'uploaderName': self.uploader.name if self.uploader else None,
            'time': relative_time(self.created_at),
            'url': f'/api/attachments/{self.id}',
        }


class PasswordReset(db.Model):
    """A single-use, time-limited token for setting a forgotten password.

    Only the hash is stored. If the table leaks, the rows in it cannot be
    used to take an account - the same reason passwords are not stored either.
    """

    __tablename__ = 'password_resets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship('User')

    @property
    def is_usable(self) -> bool:
        if self.used_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > utcnow()


# --------------------------------------------------------------------------
# Board assembly
# --------------------------------------------------------------------------

def build_board(project, issues=None) -> list:
    """Group a project's issues into its workflow states, in workflow order.

    Every state is returned even when empty — the board keys its "Drop an issue
    here" placeholder off an empty list, and a missing column simply would not
    render.
    """
    issues = project.issues if issues is None else issues

    grouped = {state.id: [] for state in project.states}
    for issue in sorted(issues, key=lambda i: (i.position, i.id)):
        if issue.state_id in grouped:
            grouped[issue.state_id].append(issue)

    return [
        {
            'id': state.id,
            'name': state.name,
            'category': state.category,
            'wipLimit': state.wip_limit,
            'issues': [issue.to_dict() for issue in grouped.get(state.id, [])],
        }
        for state in sorted(project.states, key=lambda s: s.position)
    ]


def allowed_transitions(project, from_state_id) -> list:
    """State ids an issue may move to from `from_state_id`.

    A project with no transition rows allows every move — the permissive
    default most teams want. Adding rows locks the workflow down.
    """
    if not project.transitions:
        return [state.id for state in project.states]

    allowed = [t.to_state_id for t in project.transitions if t.from_state_id == from_state_id]
    # Staying put is always legal, so an unchanged status is never rejected.
    if from_state_id not in allowed:
        allowed.append(from_state_id)
    return allowed
