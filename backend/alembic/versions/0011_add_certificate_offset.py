"""Urkunden-Druckversatz am Event (Zeilen, +/-)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-03

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE event ADD COLUMN IF NOT EXISTS certificate_offset INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS certificate_offset")
