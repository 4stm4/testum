"""make celery_task_id nullable

Revision ID: 007_make_celery_task_id_nullable
Revises: 006_fix_task_enum_values
Create Date: 2025-11-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_make_celery_task_id_nullable'
down_revision = '006_fix_task_enum_values'
branch_labels = None
depends_on = None


def upgrade():
    """Make celery_task_id nullable in task_runs table."""
    # First, update any existing 'pending' values to NULL to avoid unique constraint issues
    op.execute("UPDATE task_runs SET celery_task_id = NULL WHERE celery_task_id = 'pending'")
    
    # Then alter the column to be nullable
    op.alter_column('task_runs', 'celery_task_id',
                    existing_type=sa.String(length=255),
                    nullable=True)


def downgrade():
    """Make celery_task_id not nullable again (caution: may fail if NULL values exist)."""
    # Set any NULL values to 'pending' before making column non-nullable
    op.execute("UPDATE task_runs SET celery_task_id = 'pending' WHERE celery_task_id IS NULL")
    
    op.alter_column('task_runs', 'celery_task_id',
                    existing_type=sa.String(length=255),
                    nullable=False)
