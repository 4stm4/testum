"""add system_info to platforms

Revision ID: 008_add_platform_system_info
Revises: 007_make_celery_task_id_nullable
Create Date: 2024-05-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_platform_system_info'
down_revision = '007_make_celery_task_id_nullable'
branch_labels = None
depends_on = None


def upgrade():
    """Add system_info JSON column to platforms."""
    op.add_column('platforms', sa.Column('system_info', sa.JSON(), nullable=True))


def downgrade():
    """Remove system_info JSON column from platforms."""
    op.drop_column('platforms', 'system_info')
