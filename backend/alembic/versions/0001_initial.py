"""initiales Schema

Revision ID: 0001
Revises:
Create Date: 2026-06-30

Baseline-Migration: erzeugt alle Tabellen direkt aus den SQLAlchemy-Modellen,
damit Migration und Modelle garantiert deckungsgleich sind. Folgemigrationen
werden normal per `alembic revision --autogenerate` erstellt.
"""

from alembic import op

from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
