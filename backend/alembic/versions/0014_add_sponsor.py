"""Sponsoren-Logos (5 Klassen)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-03

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
Gewicht/Anzeigehöhe je Klasse liegen in app_setting (Key 'sponsor_tiers').
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sponsor (
            id          UUID PRIMARY KEY,
            tier        INTEGER NOT NULL,
            name        TEXT,
            image       BYTEA NOT NULL,
            image_mime  TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_sponsor_tier CHECK (tier BETWEEN 1 AND 5)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sponsor")
