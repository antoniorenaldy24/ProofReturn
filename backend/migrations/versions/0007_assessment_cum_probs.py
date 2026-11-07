"""Add cum_probs to assessments table (Round 4 Task T7: RV2-05, INV-10).

Revision ID: 0007_assessment_cum_probs
Revises: 0006_refund_action_next_attempt_at
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_assessment_cum_probs"
down_revision = "0006_refund_action_next_attempt_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("assessments")}
    if "cum_probs" not in cols:
        op.add_column(
            "assessments",
            sa.Column("cum_probs", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("assessments")}
    if "cum_probs" in cols:
        op.drop_column("assessments", "cum_probs")
