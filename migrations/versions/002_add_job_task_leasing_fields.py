# SPDX-License-Identifier: MIT
"""Add leasing metadata expected by pyjobkit workers."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002_add_job_task_leasing_fields"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_tasks", sa.Column("leased_by", sa.String(), nullable=True))
    op.add_column("job_tasks", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "job_tasks",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("job_tasks", "version")
    op.drop_column("job_tasks", "lease_until")
    op.drop_column("job_tasks", "leased_by")
