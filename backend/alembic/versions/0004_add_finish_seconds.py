"""Gespeicherte Laufzeit an registration ergänzen

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-30

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS finish_seconds DOUBLE PRECISION")


def downgrade() -> None:
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS finish_seconds")
