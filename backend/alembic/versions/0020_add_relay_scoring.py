"""Staffelwertung: competition.relay_scoring + registration.relay_id

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-17

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE competition ADD COLUMN IF NOT EXISTS "
        "relay_scoring BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS relay_id UUID")
    # Nachschlagen der Staffelmitglieder je Strecke geht über diese Spalte.
    op.execute("CREATE INDEX IF NOT EXISTS ix_registration_relay_id ON registration (relay_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_registration_relay_id")
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS relay_id")
    op.execute("ALTER TABLE competition DROP COLUMN IF EXISTS relay_scoring")
