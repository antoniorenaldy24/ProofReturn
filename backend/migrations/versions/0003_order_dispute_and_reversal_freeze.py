"""Add dispute and capture reversal freeze columns to orders (RV3-11, FR-75).

Adds frozen_by_dispute, frozen_at, frozen_reason, capture_reversed, and reversed_at
to orders table so freeze enforcement lives on the database refund path.

Revision ID: 0003_order_dispute_and_reversal_freeze
Revises: 0002_complete_canonical_schema
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_order_dispute_and_reversal_freeze"
down_revision = "0002_complete_canonical_schema"
branch_labels = None
depends_on = None


def _add_col_if_missing(inspector: sa.Inspector, table: str, column: sa.Column) -> None:
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _add_col_if_missing(
        inspector,
        "orders",
        sa.Column("frozen_by_dispute", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_col_if_missing(
        inspector,
        "orders",
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_col_if_missing(
        inspector,
        "orders",
        sa.Column("frozen_reason", sa.String(), nullable=True),
    )
    _add_col_if_missing(
        inspector,
        "orders",
        sa.Column("capture_reversed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_col_if_missing(
        inspector,
        "orders",
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("orders")}
    for col in ("reversed_at", "capture_reversed", "frozen_reason", "frozen_at", "frozen_by_dispute"):
        if col in existing:
            op.drop_column("orders", col)
