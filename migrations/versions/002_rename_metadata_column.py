"""Rename metadata to task_metadata in task_runs table

Revision ID: 002
Revises: 001
Create Date: 2025-11-09

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Rename metadata column to task_metadata to avoid SQLAlchemy reserved name conflict
    op.alter_column('task_runs', 'metadata', new_column_name='task_metadata')


def downgrade():
    # Rename back for rollback
    op.alter_column('task_runs', 'task_metadata', new_column_name='metadata')
