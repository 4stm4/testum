"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-11-09 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ssh_keys table
    op.create_table(
        'ssh_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Create platforms table
    op.create_table(
        'platforms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('auth_method', sa.Enum('password', 'private_key', name='authmethodenum'), nullable=False),
        sa.Column('encrypted_password', sa.LargeBinary(), nullable=True),
        sa.Column('encrypted_private_key', sa.LargeBinary(), nullable=True),
        sa.Column('known_host_fingerprint', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Create task_runs table
    op.create_table(
        'task_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('celery_task_id', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('type', sa.Enum('deploy', 'run_command', name='tasktypeenum'), nullable=False, index=True),
        sa.Column('platform_id', UUID(as_uuid=True), sa.ForeignKey('platforms.id'), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'success', 'failed', name='taskstatusenum'), 
                  nullable=False, index=True),
        sa.Column('result_location', sa.String(512), nullable=True),
        sa.Column('stdout', sa.Text(), nullable=True),
        sa.Column('stderr', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user', sa.String(255), nullable=False, index=True),
        sa.Column('action', sa.String(255), nullable=False, index=True),
        sa.Column('object_type', sa.String(100), nullable=False, index=True),
        sa.Column('object_id', sa.String(255), nullable=True, index=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('task_runs')
    op.drop_table('platforms')
    op.drop_table('ssh_keys')
    
    op.execute('DROP TYPE IF EXISTS taskstatusenum')
    op.execute('DROP TYPE IF EXISTS tasktypeenum')
    op.execute('DROP TYPE IF EXISTS authmethodenum')
