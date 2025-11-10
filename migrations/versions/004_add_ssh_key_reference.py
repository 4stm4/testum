"""Add ssh_key_id reference to platforms

Revision ID: 004
Revises: 003
Create Date: 2025-11-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Add ssh_key_id column to platforms table."""
    op.add_column('platforms', sa.Column('ssh_key_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_platforms_ssh_key_id', 'platforms', 'ssh_keys', ['ssh_key_id'], ['id'])


def downgrade():
    """Remove ssh_key_id column from platforms table."""
    op.drop_constraint('fk_platforms_ssh_key_id', 'platforms', type_='foreignkey')
    op.drop_column('platforms', 'ssh_key_id')
