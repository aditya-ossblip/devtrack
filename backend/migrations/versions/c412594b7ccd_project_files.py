"""project files

A file now belongs to a project. It may still point at one issue inside that
project, so `issue_id` becomes nullable rather than going away.

Revision ID: c412594b7ccd
Revises: 9f65d32dfa16
Create Date: 2026-09-20 17:49:57.568640

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c412594b7ccd'
down_revision = '9f65d32dfa16'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attachments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=False))
        batch_op.alter_column('issue_id',
                              existing_type=sa.INTEGER(),
                              nullable=True)
        batch_op.create_index(batch_op.f('ix_attachments_project_id'),
                              ['project_id'], unique=False)
        # The name is ours, not Alembic's. SQLite cannot alter a table in
        # place, so batch mode rebuilds it and copies the rows across — and a
        # constraint it has to re-create must have a name to be re-created by.
        batch_op.create_foreign_key('fk_attachments_project_id_projects',
                                    'projects', ['project_id'], ['id'])


def downgrade():
    with op.batch_alter_table('attachments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_attachments_project_id_projects',
                                 type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_attachments_project_id'))
        batch_op.alter_column('issue_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)
        batch_op.drop_column('project_id')
