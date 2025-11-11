"""Fix task enum values to use lowercase

Revision ID: 006
Revises: 005
Create Date: 2025-11-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """
    This migration doesn't need to do anything at the database level.
    The enum types in PostgreSQL remain the same (lowercase values).
    We only changed the SQLAlchemy model definition to use values_callable,
    which forces SQLAlchemy to use enum values instead of attribute names.
    
    This is a no-op migration to track the model change.
    """
    pass


def downgrade():
    """
    This migration doesn't need to do anything at the database level.
    """
    pass
