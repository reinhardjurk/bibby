"""Wertungs-Konfiguration je Strecke (AK-Schema + Geschlechtswertung)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-03

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE competition ADD COLUMN IF NOT EXISTS "
        "age_class_scheme TEXT NOT NULL DEFAULT 'five'"
    )
    op.execute(
        "ALTER TABLE competition ADD COLUMN IF NOT EXISTS "
        "gender_scoring BOOLEAN NOT NULL DEFAULT true"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE competition DROP COLUMN IF EXISTS gender_scoring")
    op.execute("ALTER TABLE competition DROP COLUMN IF EXISTS age_class_scheme")
