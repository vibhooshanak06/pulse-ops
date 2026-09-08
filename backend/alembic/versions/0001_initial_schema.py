"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-08-30

Creates all 13 tables for PulseOps AI V1:
  users, organizations, user_organizations,
  projects, api_keys,
  services, endpoints,
  telemetry_events, metric_aggregates,
  incidents, anomalies,
  incident_evidence, ai_explanations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",         sa.String(255), nullable=False),
        sa.Column("full_name",     sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active",     sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("is_verified",   sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_id",    "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("slug",       sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organizations_id",   "organizations", ["id"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # ── user_organizations ────────────────────────────────────────────────────
    op.create_table(
        "user_organizations",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",         postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role",            sa.String(50),  nullable=False, server_default="member"),
        sa.Column("joined_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"],         ["users.id"],         ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_org"),
    )
    op.create_index("ix_user_organizations_user_id",         "user_organizations", ["user_id"])
    op.create_index("ix_user_organizations_organization_id", "user_organizations", ["organization_id"])

    # ── projects ──────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name",            sa.String(255), nullable=False),
        sa.Column("slug",            sa.String(100), nullable=False),
        sa.Column("description",     sa.Text(),      nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
    )
    op.create_index("ix_projects_id",              "projects", ["id"])
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_slug",            "projects", ["slug"])

    # ── api_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id",   postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("key_prefix",   sa.String(20),  nullable=False),
        sa.Column("key_hash",     sa.String(64),  nullable=False),
        sa.Column("is_active",    sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at",   sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_id",         "api_keys", ["id"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])
    op.create_index("ix_api_keys_key_hash",   "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_is_active",  "api_keys", ["is_active"])

    # ── services ──────────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name",          sa.String(255), nullable=False),
        sa.Column("description",   sa.Text(),      nullable=True),
        sa.Column("health_status", sa.String(20),  nullable=False, server_default="unknown"),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at",  sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "name", name="uq_service_project_name"),
    )
    op.create_index("ix_services_id",            "services", ["id"])
    op.create_index("ix_services_project_id",    "services", ["project_id"])
    op.create_index("ix_services_health_status", "services", ["health_status"])

    # ── endpoints ─────────────────────────────────────────────────────────────
    op.create_table(
        "endpoints",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id",   postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path",         sa.String(1000), nullable=False),
        sa.Column("method",       sa.String(10),   nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("service_id", "path", "method", name="uq_endpoint_service_path_method"),
    )
    op.create_index("ix_endpoints_id",         "endpoints", ["id"])
    op.create_index("ix_endpoints_service_id", "endpoints", ["service_id"])

    # ── telemetry_events ──────────────────────────────────────────────────────
    op.create_table(
        "telemetry_events",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id",   postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("endpoint_path", sa.String(1000), nullable=False),
        sa.Column("method",        sa.String(10),   nullable=False),
        sa.Column("status_code",   sa.Integer(),    nullable=False),
        sa.Column("latency_ms",    sa.Float(),      nullable=False),
        sa.Column("is_error",      sa.Boolean(),    nullable=False, server_default="false"),
        sa.Column("timestamp",     sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"],  ["services.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_telemetry_events_status_code", "telemetry_events", ["status_code"])
    op.create_index("ix_telemetry_events_is_error",    "telemetry_events", ["is_error"])
    # Composite indexes — most critical for query performance
    op.create_index(
        "ix_telemetry_service_timestamp",
        "telemetry_events",
        ["service_id", sa.text("timestamp DESC")],
    )
    op.create_index(
        "ix_telemetry_endpoint_timestamp",
        "telemetry_events",
        ["endpoint_id", sa.text("timestamp DESC")],
    )

    # ── metric_aggregates ─────────────────────────────────────────────────────
    op.create_table(
        "metric_aggregates",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id",          postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id",         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("window_start",        sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end",          sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_size_minutes", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_count",       sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count",         sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rate",          sa.Float(),   nullable=False, server_default="0"),
        sa.Column("throughput_rpm",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("avg_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("min_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("max_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("p50_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("p95_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("p99_latency_ms",      sa.Float(),   nullable=False, server_default="0"),
        sa.Column("created_at",          sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"],  ["services.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_metric_aggregates_id", "metric_aggregates", ["id"])
    op.create_index(
        "ix_metric_service_window",
        "metric_aggregates",
        ["service_id", sa.text("window_start DESC")],
    )
    op.create_index(
        "ix_metric_endpoint_window",
        "metric_aggregates",
        ["endpoint_id", sa.text("window_start DESC")],
    )

    # ── incidents ─────────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id",         postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id",         postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title",              sa.String(500), nullable=False),
        sa.Column("affected_endpoints", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("severity",           sa.String(20),  nullable=False, server_default="LOW"),
        sa.Column("status",             sa.String(30),  nullable=False, server_default="OPEN"),
        sa.Column("started_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",         sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",         sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes",              sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"],  ondelete="CASCADE"),
    )
    op.create_index("ix_incidents_id",         "incidents", ["id"])
    op.create_index("ix_incidents_project_id", "incidents", ["project_id"])
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])
    op.create_index("ix_incidents_status",     "incidents", ["status"])
    op.create_index("ix_incidents_severity",   "incidents", ["severity"])
    op.create_index(
        "ix_incident_project_status_started",
        "incidents",
        ["project_id", "status", sa.text("started_at DESC")],
    )

    # ── anomalies ─────────────────────────────────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id",          postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id",         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_aggregate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id",         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_type",         sa.String(50),  nullable=False),
        sa.Column("baseline_value",      sa.Float(),     nullable=False),
        sa.Column("current_value",       sa.Float(),     nullable=False),
        sa.Column("deviation_percent",   sa.Float(),     nullable=False),
        sa.Column("statistical_score",   sa.Float(),     nullable=False, server_default="0"),
        sa.Column("ml_score",            sa.Float(),     nullable=False, server_default="0"),
        sa.Column("combined_score",      sa.Float(),     nullable=False, server_default="0"),
        sa.Column("severity",            sa.String(20),  nullable=False, server_default="LOW"),
        sa.Column("detected_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at",         sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["service_id"],          ["services.id"],          ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"],         ["endpoints.id"],         ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["metric_aggregate_id"], ["metric_aggregates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"],         ["incidents.id"],         ondelete="SET NULL"),
    )
    op.create_index("ix_anomalies_id",           "anomalies", ["id"])
    op.create_index("ix_anomalies_incident_id",  "anomalies", ["incident_id"])
    op.create_index("ix_anomalies_metric_type",  "anomalies", ["metric_type"])
    op.create_index("ix_anomalies_severity",     "anomalies", ["severity"])
    op.create_index("ix_anomalies_combined_score","anomalies", ["combined_score"])
    op.create_index(
        "ix_anomaly_service_detected",
        "anomalies",
        ["service_id", sa.text("detected_at DESC")],
    )
    op.create_index(
        "ix_anomaly_incident_detected",
        "anomalies",
        ["incident_id", "detected_at"],
    )

    # ── incident_evidence ─────────────────────────────────────────────────────
    op.create_table(
        "incident_evidence",
        sa.Column("id",                       postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id",              postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("baseline_metrics",         postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("current_metrics",          postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("metric_changes",           postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("anomaly_timeline",         postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("affected_services",        postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("affected_endpoints",       postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("baseline_window_minutes",  sa.Integer(), nullable=True),
        sa.Column("collected_at",             sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("incident_id", name="uq_evidence_incident"),
    )
    op.create_index("ix_incident_evidence_id",          "incident_evidence", ["id"])
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])

    # ── ai_explanations ───────────────────────────────────────────────────────
    op.create_table(
        "ai_explanations",
        sa.Column("id",                   postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id",          postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary",              sa.Text(),      nullable=False),
        sa.Column("probable_causes",      postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence",           sa.Float(),     nullable=False, server_default="0"),
        sa.Column("recommended_actions",  postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("limitations",          sa.Text(),      nullable=False),
        sa.Column("raw_response",         sa.Text(),      nullable=True),
        sa.Column("model_used",           sa.String(100), nullable=False, server_default=""),
        sa.Column("prompt_tokens",        sa.Integer(),   nullable=True),
        sa.Column("completion_tokens",    sa.Integer(),   nullable=True),
        sa.Column("generated_at",         sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("incident_id", name="uq_ai_explanation_incident"),
    )
    op.create_index("ix_ai_explanations_id",          "ai_explanations", ["id"])
    op.create_index("ix_ai_explanations_incident_id", "ai_explanations", ["incident_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("ai_explanations")
    op.drop_table("incident_evidence")
    op.drop_table("anomalies")
    op.drop_table("incidents")
    op.drop_table("metric_aggregates")
    op.drop_table("telemetry_events")
    op.drop_table("endpoints")
    op.drop_table("services")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("user_organizations")
    op.drop_table("organizations")
    op.drop_table("users")
