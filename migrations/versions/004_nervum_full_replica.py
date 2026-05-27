# SPDX-License-Identifier: MIT
"""T1-T4: Nervum replica tables — networks, nodes, projects, logical ports,
security groups, address pools, service objects, QoS policies, security
policies, trunk ports, routers, floating IPs, BGP peers, gateway bonds,
load balancers, apply schedules, mirror sessions, VPN tunnels, event
quarantine, sync state, SDN tasks, and project bindings.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004_nervum_full_replica"
down_revision = "003_add_pyjobkit_job_id"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid_col(name: str, **kw):
    if _is_pg():
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)
    return sa.Column(name, sa.String(36), **kw)


def upgrade() -> None:
    # ── nervum_sync_state ────────────────────────────────────────────────
    op.create_table(
        "nervum_sync_state",
        sa.Column("id",                   sa.Integer(),     primary_key=True),
        sa.Column("watermark",            sa.Integer(),     nullable=False, server_default="0"),
        sa.Column("subscription_id",      sa.String(255),   nullable=True),
        sa.Column("last_synced_at",       sa.DateTime(),    nullable=True),
        sa.Column("consecutive_failures", sa.Integer(),     nullable=False, server_default="0"),
    )

    # ── nervum_networks ──────────────────────────────────────────────────
    op.create_table(
        "nervum_networks",
        sa.Column("id",             sa.String(255), primary_key=True),
        sa.Column("name",           sa.String(255), nullable=False),
        sa.Column("type",           sa.String(50),  nullable=True),
        sa.Column("project_id",     sa.String(255), nullable=True),
        sa.Column("vni",            sa.Integer(),   nullable=True),
        sa.Column("vlan_id",        sa.Integer(),   nullable=True),
        sa.Column("mtu",            sa.Integer(),   nullable=True),
        sa.Column("intent_version", sa.Integer(),   nullable=True),
        sa.Column("spec_hash",      sa.String(255), nullable=True),
        sa.Column("node_ids",       sa.JSON(),      nullable=True),
        sa.Column("labels",         sa.JSON(),      nullable=True),
        sa.Column("raw",            sa.JSON(),      nullable=True),
        sa.Column("updated_at",     sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_networks_name",       "nervum_networks", ["name"])
    op.create_index("ix_nervum_networks_project_id", "nervum_networks", ["project_id"])

    # ── nervum_nodes ─────────────────────────────────────────────────────
    op.create_table(
        "nervum_nodes",
        sa.Column("id",            sa.String(255), primary_key=True),
        sa.Column("name",          sa.String(255), nullable=False),
        sa.Column("mgmt_ip",       sa.String(100), nullable=True),
        sa.Column("status",        sa.String(50),  nullable=True),
        sa.Column("agent_version", sa.String(100), nullable=True),
        sa.Column("roles",         sa.JSON(),      nullable=True),
        sa.Column("labels",        sa.JSON(),      nullable=True),
        sa.Column("raw",           sa.JSON(),      nullable=True),
        sa.Column("updated_at",    sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_nodes_name",   "nervum_nodes", ["name"])
    op.create_index("ix_nervum_nodes_status", "nervum_nodes", ["status"])

    # ── nervum_projects ──────────────────────────────────────────────────
    op.create_table(
        "nervum_projects",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("slug",       sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_projects_name",   "nervum_projects", ["name"])
    op.create_index("ix_nervum_projects_status", "nervum_projects", ["status"])

    # ── nervum_logical_ports ─────────────────────────────────────────────
    op.create_table(
        "nervum_logical_ports",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("network_id", sa.String(255), nullable=True),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("mac",        sa.String(50),  nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_logical_ports_name",       "nervum_logical_ports", ["name"])
    op.create_index("ix_nervum_logical_ports_network_id", "nervum_logical_ports", ["network_id"])
    op.create_index("ix_nervum_logical_ports_project_id", "nervum_logical_ports", ["project_id"])
    op.create_index("ix_nervum_logical_ports_status",     "nervum_logical_ports", ["status"])

    # ── nervum_security_groups ───────────────────────────────────────────
    op.create_table(
        "nervum_security_groups",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("rules",      sa.JSON(),      nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_security_groups_name",       "nervum_security_groups", ["name"])
    op.create_index("ix_nervum_security_groups_project_id", "nervum_security_groups", ["project_id"])

    # ── nervum_address_pools ─────────────────────────────────────────────
    op.create_table(
        "nervum_address_pools",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("cidr",       sa.String(100), nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_address_pools_name",       "nervum_address_pools", ["name"])
    op.create_index("ix_nervum_address_pools_project_id", "nervum_address_pools", ["project_id"])

    # ── nervum_service_objects ───────────────────────────────────────────
    op.create_table(
        "nervum_service_objects",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("protocol",   sa.String(50),  nullable=True),
        sa.Column("port_range", sa.String(100), nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_service_objects_name",       "nervum_service_objects", ["name"])
    op.create_index("ix_nervum_service_objects_project_id", "nervum_service_objects", ["project_id"])

    # ── nervum_qos_policies ──────────────────────────────────────────────
    op.create_table(
        "nervum_qos_policies",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_qos_policies_name",       "nervum_qos_policies", ["name"])
    op.create_index("ix_nervum_qos_policies_project_id", "nervum_qos_policies", ["project_id"])

    # ── nervum_security_policies ─────────────────────────────────────────
    op.create_table(
        "nervum_security_policies",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_security_policies_name",       "nervum_security_policies", ["name"])
    op.create_index("ix_nervum_security_policies_project_id", "nervum_security_policies", ["project_id"])
    op.create_index("ix_nervum_security_policies_status",     "nervum_security_policies", ["status"])

    # ── nervum_trunk_ports ───────────────────────────────────────────────
    op.create_table(
        "nervum_trunk_ports",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_trunk_ports_name",       "nervum_trunk_ports", ["name"])
    op.create_index("ix_nervum_trunk_ports_project_id", "nervum_trunk_ports", ["project_id"])

    # ── nervum_routers ───────────────────────────────────────────────────
    op.create_table(
        "nervum_routers",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("mode",       sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_routers_name",       "nervum_routers", ["name"])
    op.create_index("ix_nervum_routers_project_id", "nervum_routers", ["project_id"])
    op.create_index("ix_nervum_routers_status",     "nervum_routers", ["status"])

    # ── nervum_floating_ips ──────────────────────────────────────────────
    op.create_table(
        "nervum_floating_ips",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("router_id",  sa.String(255), nullable=True),
        sa.Column("address",    sa.String(100), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_floating_ips_project_id", "nervum_floating_ips", ["project_id"])
    op.create_index("ix_nervum_floating_ips_router_id",  "nervum_floating_ips", ["router_id"])
    op.create_index("ix_nervum_floating_ips_status",     "nervum_floating_ips", ["status"])

    # ── nervum_bgp_peers ─────────────────────────────────────────────────
    op.create_table(
        "nervum_bgp_peers",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("router_id",  sa.String(255), nullable=True),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("peer_ip",    sa.String(100), nullable=True),
        sa.Column("remote_asn", sa.Integer(),   nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_bgp_peers_router_id",  "nervum_bgp_peers", ["router_id"])
    op.create_index("ix_nervum_bgp_peers_project_id", "nervum_bgp_peers", ["project_id"])

    # ── nervum_gateway_bonds ─────────────────────────────────────────────
    op.create_table(
        "nervum_gateway_bonds",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("mode",       sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_gateway_bonds_name",       "nervum_gateway_bonds", ["name"])
    op.create_index("ix_nervum_gateway_bonds_project_id", "nervum_gateway_bonds", ["project_id"])

    # ── nervum_load_balancers ────────────────────────────────────────────
    op.create_table(
        "nervum_load_balancers",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("router_id",  sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_load_balancers_name",       "nervum_load_balancers", ["name"])
    op.create_index("ix_nervum_load_balancers_project_id", "nervum_load_balancers", ["project_id"])
    op.create_index("ix_nervum_load_balancers_router_id",  "nervum_load_balancers", ["router_id"])
    op.create_index("ix_nervum_load_balancers_status",     "nervum_load_balancers", ["status"])

    # ── nervum_apply_schedules ───────────────────────────────────────────
    op.create_table(
        "nervum_apply_schedules",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_apply_schedules_name",       "nervum_apply_schedules", ["name"])
    op.create_index("ix_nervum_apply_schedules_project_id", "nervum_apply_schedules", ["project_id"])
    op.create_index("ix_nervum_apply_schedules_status",     "nervum_apply_schedules", ["status"])

    # ── nervum_mirror_sessions ───────────────────────────────────────────
    op.create_table(
        "nervum_mirror_sessions",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_mirror_sessions_name",       "nervum_mirror_sessions", ["name"])
    op.create_index("ix_nervum_mirror_sessions_project_id", "nervum_mirror_sessions", ["project_id"])
    op.create_index("ix_nervum_mirror_sessions_status",     "nervum_mirror_sessions", ["status"])

    # ── nervum_vpn_tunnels ───────────────────────────────────────────────
    op.create_table(
        "nervum_vpn_tunnels",
        sa.Column("id",         sa.String(255), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("protocol",   sa.String(50),  nullable=True),
        sa.Column("status",     sa.String(50),  nullable=True),
        sa.Column("labels",     sa.JSON(),      nullable=True),
        sa.Column("raw",        sa.JSON(),      nullable=True),
        sa.Column("updated_at", sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_nervum_vpn_tunnels_name",       "nervum_vpn_tunnels", ["name"])
    op.create_index("ix_nervum_vpn_tunnels_project_id", "nervum_vpn_tunnels", ["project_id"])
    op.create_index("ix_nervum_vpn_tunnels_status",     "nervum_vpn_tunnels", ["status"])

    # ── nervum_event_quarantine ──────────────────────────────────────────
    op.create_table(
        "nervum_event_quarantine",
        sa.Column("id",             sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("event_id",       sa.Integer(),    nullable=True),
        sa.Column("schema_version", sa.Integer(),    nullable=True),
        sa.Column("event_type",     sa.String(255),  nullable=True),
        sa.Column("resource_type",  sa.String(100),  nullable=True),
        sa.Column("resource_id",    sa.String(255),  nullable=True),
        sa.Column("raw",            sa.JSON(),       nullable=True),
        sa.Column("received_at",    sa.DateTime(),   nullable=False),
    )
    op.create_index("ix_nervum_event_quarantine_event_id",    "nervum_event_quarantine", ["event_id"])
    op.create_index("ix_nervum_event_quarantine_received_at", "nervum_event_quarantine", ["received_at"])

    # ── sdn_tasks ────────────────────────────────────────────────────────
    op.create_table(
        "sdn_tasks",
        _uuid_col("id", primary_key=True),
        sa.Column("testum_task_id",      sa.String(255), nullable=True),
        sa.Column("nervum_operation_id", sa.String(255), nullable=False),
        sa.Column("project_id",          sa.String(255), nullable=True),
        sa.Column("resource_type",       sa.String(100), nullable=True),
        sa.Column("resource_id",         sa.String(255), nullable=True),
        sa.Column("kind",                sa.String(100), nullable=True),
        sa.Column("status",              sa.String(50),  nullable=False, server_default="accepted"),
        sa.Column("error_code",          sa.String(100), nullable=True),
        sa.Column("error_message",       sa.Text(),      nullable=True),
        sa.Column("initiated_by",        sa.String(255), nullable=True),
        sa.Column("started_at",          sa.DateTime(),  nullable=False),
        sa.Column("finished_at",         sa.DateTime(),  nullable=True),
        sa.Column("updated_at",          sa.DateTime(),  nullable=False),
    )
    op.create_index("ix_sdn_tasks_testum_task_id",      "sdn_tasks", ["testum_task_id"])
    op.create_index("ix_sdn_tasks_nervum_operation_id", "sdn_tasks", ["nervum_operation_id"])
    op.create_index("ix_sdn_tasks_project_id",          "sdn_tasks", ["project_id"])
    op.create_index("ix_sdn_tasks_status",              "sdn_tasks", ["status"])

    # ── nervum_project_bindings ──────────────────────────────────────────
    op.create_table(
        "nervum_project_bindings",
        _uuid_col("id", primary_key=True),
        sa.Column("testum_project_id",   sa.String(255), nullable=False),
        sa.Column("nervum_project_id",   sa.String(255), nullable=False),
        sa.Column("nervum_project_slug", sa.String(255), nullable=True),
        sa.Column("status",              sa.String(50),  nullable=False, server_default="active"),
        sa.Column("last_sync_at",        sa.DateTime(),  nullable=True),
        sa.Column("created_at",          sa.DateTime(),  nullable=False),
        sa.Column("updated_at",          sa.DateTime(),  nullable=False),
    )
    op.create_index(
        "ix_nervum_project_bindings_testum_project_id", "nervum_project_bindings",
        ["testum_project_id"], unique=True,
    )
    op.create_index(
        "ix_nervum_project_bindings_nervum_project_id", "nervum_project_bindings",
        ["nervum_project_id"],
    )


def downgrade() -> None:
    op.drop_table("nervum_project_bindings")
    op.drop_table("sdn_tasks")
    op.drop_table("nervum_event_quarantine")
    op.drop_table("nervum_vpn_tunnels")
    op.drop_table("nervum_mirror_sessions")
    op.drop_table("nervum_apply_schedules")
    op.drop_table("nervum_load_balancers")
    op.drop_table("nervum_gateway_bonds")
    op.drop_table("nervum_bgp_peers")
    op.drop_table("nervum_floating_ips")
    op.drop_table("nervum_routers")
    op.drop_table("nervum_trunk_ports")
    op.drop_table("nervum_security_policies")
    op.drop_table("nervum_qos_policies")
    op.drop_table("nervum_service_objects")
    op.drop_table("nervum_address_pools")
    op.drop_table("nervum_security_groups")
    op.drop_table("nervum_logical_ports")
    op.drop_table("nervum_projects")
    op.drop_table("nervum_nodes")
    op.drop_table("nervum_networks")
    op.drop_table("nervum_sync_state")
