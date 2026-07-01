"""Strecken dürfen dieselbe Rundenzahl haben

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-01

Entfernt die Eindeutigkeit (event_id, lap_count), damit mehrere Strecken je
Event dieselbe Rundenzahl haben können (z. B. Running vs. Walking).
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE competition DROP CONSTRAINT IF EXISTS uq_competition_event_lap")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE competition ADD CONSTRAINT uq_competition_event_lap "
        "UNIQUE (event_id, lap_count)"
    )
