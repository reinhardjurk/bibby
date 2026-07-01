"""Passwort-Hash an app_user ergänzen

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-30

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS password_hash TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE app_user DROP COLUMN IF EXISTS password_hash")
