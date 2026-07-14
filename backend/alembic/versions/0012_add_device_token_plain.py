"""Menschenlesbarer Klartext-Code am Geräte-Token (dauerhaft sichtbar)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-03

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE device_token ADD COLUMN IF NOT EXISTS token_plain TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE device_token DROP COLUMN IF EXISTS token_plain")
