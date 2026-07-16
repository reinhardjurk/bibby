"""Hintergrundvorlage für die Startnummer

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-16

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS bib_bg BYTEA")
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS bib_bg_mime TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS bib_bg_mime")
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS bib_bg")
