"""Neue Rollen sponsor_management + sepa (user_role CHECK erweitern)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-16

Erweitert die Prüfbedingung um die engen Bereichsrollen. Idempotent über
DROP CONSTRAINT IF EXISTS + neu anlegen.
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_ALL = "'admin','race_office','timing','sponsor_management','sepa','viewer'"
_OLD = "'admin','race_office','timing','viewer'"


def upgrade() -> None:
    op.execute("ALTER TABLE user_role DROP CONSTRAINT IF EXISTS ck_user_role")
    op.execute(f"ALTER TABLE user_role ADD CONSTRAINT ck_user_role CHECK (role IN ({_ALL}))")


def downgrade() -> None:
    op.execute("ALTER TABLE user_role DROP CONSTRAINT IF EXISTS ck_user_role")
    op.execute(f"ALTER TABLE user_role ADD CONSTRAINT ck_user_role CHECK (role IN ({_OLD}))")
