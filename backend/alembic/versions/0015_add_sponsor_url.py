"""Ziel-URL am Sponsorenlogo

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-14

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sponsor ADD COLUMN IF NOT EXISTS url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE sponsor DROP COLUMN IF EXISTS url")
