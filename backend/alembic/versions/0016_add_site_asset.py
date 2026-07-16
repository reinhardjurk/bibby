"""Globale Bild-Assets (Kopf-Logo)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-14

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS site_asset (
            key        TEXT PRIMARY KEY,
            image      BYTEA NOT NULL,
            mime       TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_asset")
