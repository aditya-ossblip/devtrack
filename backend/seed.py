"""Create the demo account. Nothing else.

    python seed.py                          # create it if missing
    python seed.py --email you@gmail.com    # ...or re-point it at that address
    python seed.py --reset                  # empty every table first

`--email` is how you move the demo account onto a real address. Sign-in is
through Google, and Google matches on the verified email it hands over — so
pointing this account at your Google address means your first Google sign-in
lands *in* it, keeping its admin role and everything it owns, instead of
quietly creating a second account with no projects.

There is deliberately no demo project. Signing in and building a project from
nothing — naming it, picking a key, adding people, shaping the board — is the
flow the app is actually for, and a pre-filled example lets you skip all of it
and never find out whether it works.

The schema comes from migrations, not from here. Run `npm run db:upgrade`
first; this script refuses to guess at tables that do not exist yet.

Idempotent: running it twice does not duplicate anything.
"""

import os
import shutil
import sys

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import (
    Activity,
    Attachment,
    Comment,
    Issue,
    Notification,
    PasswordReset,
    Project,
    ProjectMember,
    Sprint,
    User,
    WorkflowState,
    WorkflowTransition,
)

DEMO_EMAIL = os.getenv('DEMO_EMAIL', 'aditya@devtrack.local')
DEMO_PASSWORD = 'devtrack123'

# Children before parents. Issue is listed after its own dependents but before
# Sprint and WorkflowState, which it points at.
DELETION_ORDER = (
    Attachment,
    Activity,
    Comment,
    Notification,
    PasswordReset,
    Issue,
    Sprint,
    WorkflowTransition,
    WorkflowState,
    ProjectMember,
    Project,
    User,
)


def require_schema() -> None:
    """Fail loudly rather than seeding into a half-built database."""
    tables = set(inspect(db.engine).get_table_names())
    missing = {'users', 'projects', 'issues', 'activities'} - tables
    if missing:
        print('The database has no schema yet.')
        print(f'Missing tables: {", ".join(sorted(missing))}')
        print('Run:  npm run db:upgrade')
        sys.exit(1)


def wipe() -> None:
    """Empty every table without touching the schema.

    Deliberately not `drop_all()` + `create_all()`. Those bypass Alembic
    entirely: the tables would be rebuilt from the models while
    `alembic_version` still claims the last migration was applied, and the two
    would drift apart the moment a migration adds something the models have
    since changed.
    """
    # Self-referential and cross-table pointers first, so the bulk deletes below
    # cannot trip a foreign key on a database that enforces them.
    db.session.query(Issue).update({Issue.epic_id: None, Issue.sprint_id: None})
    db.session.flush()

    for model in DELETION_ORDER:
        db.session.query(model).delete()

    db.session.commit()
    print('Emptied every table.')


def clear_uploads(app) -> None:
    directory = app.config['UPLOAD_DIR']
    if directory.exists():
        shutil.rmtree(directory)
        print(f'Removed uploaded files in {directory}.')


def seed(email: str = DEMO_EMAIL) -> None:
    email = email.strip().lower()

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is not None:
        print(f'{email} already exists — nothing to do.')
        return

    # Re-pointing rather than creating: if the stock demo account is still
    # here, move it to the new address instead of leaving an orphan behind.
    existing = db.session.scalar(db.select(User).filter_by(email=DEMO_EMAIL))
    if existing is not None and email != DEMO_EMAIL:
        taken = db.session.scalar(db.select(User).filter_by(email=email))
        if taken is not None:
            print(f'{email} is already used by another account. Nothing changed.')
            sys.exit(1)
        previous = existing.email
        existing.email = email
        db.session.commit()
        print(f'Moved the demo account from {previous} to {email}.')
        print('Sign in with Google using that address and it will link to this account.')
        return

    user = User(
        name='Aditya Kundu',
        email=email,
        role='admin',
        title='Team Lead & Backend',
    )
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.commit()

    print(f'Created {email}.')
    print(f'Password sign-in (only used while Google is unconfigured): {DEMO_PASSWORD}')
    print('Then create your first project in the app — there is no demo one.')
    print('Everyone else signs up themselves; add them from the Team page.')


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        require_schema()
        if '--reset' in sys.argv:
            wipe()
            clear_uploads(app)

        address = DEMO_EMAIL
        if '--email' in sys.argv:
            index = sys.argv.index('--email') + 1
            if index >= len(sys.argv):
                print('--email needs an address after it.')
                sys.exit(1)
            address = sys.argv[index]
            if '@' not in address:
                print(f'{address} does not look like an email address.')
                sys.exit(1)

        seed(address)
