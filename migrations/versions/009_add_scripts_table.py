# SPDX-License-Identifier: MIT
"""create scripts table

Revision ID: 009_add_scripts_table
Revises: 008_add_platform_system_info
Create Date: 2024-05-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '009_add_scripts_table'
down_revision = '008_add_platform_system_info'
branch_labels = None
depends_on = None


def upgrade():
    """Create scripts table for reusable automation snippets."""
    op.create_table(
        'scripts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_scripts_name', 'scripts', ['name'], unique=True)


def downgrade():
    """Drop scripts table."""
    op.drop_index('ix_scripts_name', table_name='scripts')
    op.drop_table('scripts')
