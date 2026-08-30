"""add bearer/custom to credential_type enum

Revision ID: 0003_credential_types
Revises: 0002_refresh_tokens
Create Date: 2026-08-31
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_credential_types"
down_revision: str | None = "0002_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite recreates the CHECK constraint from the model directly
    # ADD VALUE cannot run inside a transaction block on older PG; commit first.
    op.execute("COMMIT")
    for value in ("bearer", "custom"):
        op.execute(f"ALTER TYPE credential_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; leaving the values is harmless.
    pass
