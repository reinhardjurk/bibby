"""T-Shirt-Optionen (Event) und -Auswahl (Registration)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-01

Additiv (IF NOT EXISTS), kompatibel mit der create_all-Baseline.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE event ADD COLUMN IF NOT EXISTS tshirt_options JSONB")
    op.execute("ALTER TABLE registration ADD COLUMN IF NOT EXISTS tshirt TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE registration DROP COLUMN IF EXISTS tshirt")
    op.execute("ALTER TABLE event DROP COLUMN IF EXISTS tshirt_options")
