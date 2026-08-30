"""initial Automation Center schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-30
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", name="user_role"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", "pending", name="user_status"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("configuration", _JSON, nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_profile_user_name"),
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"])

    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "type",
            sa.Enum("api_key", "oauth2", "basic_auth", "service_token", name="credential_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("connected", "error", "untested", "disabled", name="credential_status"),
            nullable=False,
        ),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column("hint", sa.String(32), nullable=False, server_default=""),
        sa.Column("meta", _JSON, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_credential_user_name"),
    )
    op.create_index("ix_credentials_user_id", "credentials", ["user_id"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("slug", sa.String(120), nullable=False, server_default=""),
        sa.Column("category", sa.String(80), nullable=False, server_default=""),
        sa.Column("n8n_workflow_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "unknown", name="workflow_status"),
            nullable=False,
        ),
        sa.Column("meta", _JSON, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "n8n_workflow_id", name="uq_workflow_user_n8nid"),
    )
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])

    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("external_execution_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("success", "running", "failed", "waiting", "cancelled", name="execution_status"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "external_execution_id", name="uq_execution_ext"),
    )
    op.create_index("ix_executions_workflow_id", "executions", ["workflow_id"])

    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("debug", "info", "warning", "error", "critical", name="event_severity"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("meta", _JSON, nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_events_type", "system_events", ["type"])
    op.create_index("ix_system_events_correlation_id", "system_events", ["correlation_id"])


def downgrade() -> None:
    for table in ("system_events", "executions", "workflows", "credentials", "profiles", "users"):
        op.drop_table(table)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "event_severity",
            "execution_status",
            "workflow_status",
            "credential_status",
            "credential_type",
            "user_status",
            "user_role",
        ):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
