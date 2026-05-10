# SPDX-License-Identifier: MIT
"""Add pyjobkit_job_id to task_runs for queue tracking."""

from alembic import op
import sqlalchemy as sa


revision = "003_add_pyjobkit_job_id"
down_revision = "002_add_job_task_leasing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_runs", sa.Column("pyjobkit_job_id", sa.String(255), nullable=True))
    op.create_index("ix_task_runs_pyjobkit_job_id", "task_runs", ["pyjobkit_job_id"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_pyjobkit_job_id", table_name="task_runs")
    op.drop_column("task_runs", "pyjobkit_job_id")
