"""Freiwillige Angaben bei der Anmeldung: Postleitzahl + wie erfahren

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-17

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS postal_code TEXT")
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS heard_about TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS heard_about")
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS postal_code")
