"""Teamzugehörigkeit an registration ergänzen

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30

Additiv. IF NOT EXISTS, da die Baseline (0001) auf frischen DBs bereits das
aktuelle Modell inkl. team-Spalte erzeugt; auf bestehenden DBs fehlt sie.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS team TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS team")
