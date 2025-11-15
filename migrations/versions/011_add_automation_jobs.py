# SPDX-License-Identifier: MIT
"""add automation jobs tables

Revision ID: 011
Revises: 010
Create Date: 2025-11-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    """Create automation_jobs and automation_job_platforms tables."""
    
    # Create automation_jobs table
    op.create_table(
        'automation_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('execution_type', sa.String(50), nullable=False, server_default='command'),
        sa.Column('command', sa.Text(), nullable=True),
        sa.Column('script_id', UUID(as_uuid=True), sa.ForeignKey('scripts.id'), nullable=True),
        sa.Column('trigger_type', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('cron_expression', sa.String(255), nullable=True),
        sa.Column('repository_url', sa.String(512), nullable=True),
        sa.Column('repository_branch', sa.String(120), nullable=True),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('environment', sa.JSON(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('notification_settings', sa.JSON(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='600'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('concurrency_limit', sa.Integer(), nullable=True),
        sa.Column('require_approval', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('run_on_all_platforms', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )
    
    # Create automation_job_platforms association table
    op.create_table(
        'automation_job_platforms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('automation_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform_id', UUID(as_uuid=True), sa.ForeignKey('platforms.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('job_id', 'platform_id', name='uq_automation_job_platform'),
    )


def downgrade():
    """Drop automation_jobs and automation_job_platforms tables."""
    op.drop_table('automation_job_platforms')
    op.drop_table('automation_jobs')
