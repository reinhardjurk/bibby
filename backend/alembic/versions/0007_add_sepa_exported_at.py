"""SEPA-Export-Zeitstempel an payment

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payment ADD COLUMN IF NOT EXISTS sepa_exported_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE payment DROP COLUMN IF EXISTS sepa_exported_at")
