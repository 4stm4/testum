"""Add encrypted_private_key to ssh_keys

Revision ID: 005
Revises: 004
Create Date: 2025-11-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """Add encrypted_private_key column to ssh_keys table."""
    op.add_column('ssh_keys', sa.Column('encrypted_private_key', sa.LargeBinary(), nullable=True))


def downgrade():
    """Remove encrypted_private_key column from ssh_keys table."""
    op.drop_column('ssh_keys', 'encrypted_private_key')
