"""core tables

The tables that existed before migrations were introduced: users, projects
and their members, sprints, the workflow, issues, comments and notifications.

They used to be created by db.create_all() and only the changes after that
were migrations, so `db upgrade` on a brand-new database (a fresh clone, a
new laptop) failed partway through. This revision goes underneath the old
first one and builds those tables, so the whole chain runs from nothing.

A database that already has them is at a later revision and never runs this.

Revision ID: 4d1e0b7f2a90
Revises:
Create Date: 2026-10-04 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d1e0b7f2a90'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=190), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('lead_id', sa.Integer(), nullable=False),
    sa.Column('issue_counter', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['lead_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_key'), ['key'], unique=True)

    op.create_table('project_members',
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('project_id', 'user_id')
    )

    op.create_table('sprints',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('goal', sa.String(length=400), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sprints', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sprints_project_id'), ['project_id'], unique=False)

    op.create_table('workflow_states',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('wip_limit', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('workflow_states', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_states_project_id'), ['project_id'], unique=False)

    op.create_table('issues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=24), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('state_id', sa.Integer(), nullable=False),
    sa.Column('assignee_id', sa.Integer(), nullable=True),
    sa.Column('reporter_id', sa.Integer(), nullable=True),
    sa.Column('epic_id', sa.Integer(), nullable=True),
    sa.Column('sprint_id', sa.Integer(), nullable=True),
    sa.Column('story_points', sa.Integer(), nullable=True),
    sa.Column('labels', sa.String(length=400), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['epic_id'], ['issues.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], ),
    sa.ForeignKeyConstraint(['state_id'], ['workflow_states.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_issues_key'), ['key'], unique=True)
        batch_op.create_index(batch_op.f('ix_issues_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_issues_sprint_id'), ['sprint_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_issues_state_id'), ['state_id'], unique=False)

    op.create_table('workflow_transitions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('from_state_id', sa.Integer(), nullable=False),
    sa.Column('to_state_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['from_state_id'], ['workflow_states.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['to_state_id'], ['workflow_states.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('workflow_transitions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_transitions_project_id'), ['project_id'], unique=False)

    op.create_table('comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('issue_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comments_issue_id'), ['issue_id'], unique=False)

    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('issue_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('text', sa.String(length=400), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)


def downgrade():
    op.drop_table('notifications')
    op.drop_table('comments')
    op.drop_table('workflow_transitions')
    op.drop_table('issues')
    op.drop_table('workflow_states')
    op.drop_table('sprints')
    op.drop_table('project_members')
    op.drop_table('projects')
    op.drop_table('users')
