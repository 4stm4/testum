# SPDX-License-Identifier: MIT
"""Update users table for RBAC roles

Revision ID: 010
Revises: 009_add_scripts_table
Create Date: 2025-11-09
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009_add_scripts_table"
branch_labels = None
depends_on = None


def upgrade():
    role_enum = sa.Enum("admin", "operator", "viewer", name="userroleenum")
    bind = op.get_bind()
    role_enum.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column("role", role_enum, nullable=False, server_default="operator"),
    )
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = true")
    op.execute("UPDATE users SET role = 'operator' WHERE role IS NULL")

    op.alter_column("users", "role", server_default=None)

    op.drop_column("users", "is_admin")


def downgrade():
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute("UPDATE users SET is_admin = CASE WHEN role = 'admin' THEN 1 ELSE 0 END")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "role")

    sa.Enum(name="userroleenum").drop(op.get_bind(), checkfirst=True)
