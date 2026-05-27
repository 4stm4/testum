# SPDX-License-Identifier: MIT
"""T7: vm_sdn_ports — track VM NIC → Nervum LogicalPort bindings."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005_vm_sdn_ports"
down_revision = "004_nervum_full_replica"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid_col(name: str, **kw):
    if _is_pg():
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)
    return sa.Column(name, sa.String(36), **kw)


def upgrade() -> None:
    op.create_table(
        "vm_sdn_ports",
        _uuid_col("id", primary_key=True),
        _uuid_col("platform_id", nullable=False),
        sa.Column("vm_name",    sa.String(255), nullable=False),
        sa.Column("port_id",    sa.String(255), nullable=False),
        sa.Column("network_id", sa.String(255), nullable=True),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("mac",        sa.String(50),  nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(),  nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("platform_id", "vm_name", name="uq_vm_sdn_port"),
    )
    op.create_index("ix_vm_sdn_ports_vm_name", "vm_sdn_ports", ["vm_name"])
    op.create_index("ix_vm_sdn_ports_port_id", "vm_sdn_ports", ["port_id"])


def downgrade() -> None:
    op.drop_table("vm_sdn_ports")
