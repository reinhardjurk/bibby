"""Urkunden-Hintergrund am Event (Bild in der DB)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-02

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS certificate_bg BYTEA")
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS certificate_bg_mime TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS certificate_bg_mime")
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS certificate_bg")
