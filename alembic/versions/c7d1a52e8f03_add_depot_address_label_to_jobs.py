"""add depot_address_label to jobs

Revision ID: c7d1a52e8f03
Revises: bf29acd4765d
Create Date: 2026-07-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d1a52e8f03'
down_revision = 'bf29acd4765d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('depot_address_label', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'depot_address_label')
