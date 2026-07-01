"""Altersabhängige Preise + T-Shirt-inklusive

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE competition ADD COLUMN IF NOT EXISTS price_junior_cents INT")
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS junior_cutoff_date DATE")
    op.execute(
        "ALTER TABLE event ADD COLUMN IF NOT EXISTS tshirt_included BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS tshirt_included")
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS junior_cutoff_date")
    op.execute("ALTER TABLE competition DROP COLUMN IF EXISTS price_junior_cents")
