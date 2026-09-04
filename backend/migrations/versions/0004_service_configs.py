"""service_configs: control-plane owned service configuration

Adds one row per integration (n8n, playwright, gemini, ...) so the endpoints and
their secrets can be changed from the web panel instead of requiring an `.env`
edit and a redeploy. Purely additive: with no rows present the resolver falls
back to the environment and behaviour is unchanged.

Revision ID: 0004_service_configs
Revises: 0003_credential_types
Create Date: 2026-09-04
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004_service_configs"
down_revision: str | None = "0003_credential_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "service_configs",
        sa.Column("service", sa.String(length=32), primary_key=True),
        sa.Column("base_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=True),
        sa.Column("secret_hint", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("meta", _JSON, nullable=False, server_default="{}"),
        sa.Column(
            "updated_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_detail", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("service_configs")
