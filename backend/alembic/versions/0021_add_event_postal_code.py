"""PLZ des Veranstaltungsorts (Bezugspunkt der Anreise-Statistik)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-17

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS postal_code TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS postal_code")
