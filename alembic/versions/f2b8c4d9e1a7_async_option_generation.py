"""async option generation: PENDING/FAILED statuses and error_detail

Revision ID: f2b8c4d9e1a7
Revises: a4e19c07d2b6
Create Date: 2026-07-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2b8c4d9e1a7'
down_revision = 'a4e19c07d2b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PG16 allows ADD VALUE inside a transaction as long as the new value is
    # not used by this same migration. IF NOT EXISTS makes reruns harmless.
    op.execute("ALTER TYPE optionstatus ADD VALUE IF NOT EXISTS 'PENDING'")
    op.execute("ALTER TYPE optionstatus ADD VALUE IF NOT EXISTS 'FAILED'")

    # Human-readable failure reason for FAILED options (worker-side errors
    # can no longer surface as HTTP 422s — the response is long gone).
    op.add_column('options', sa.Column('error_detail', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('options', 'error_detail')
    # Postgres cannot remove enum values; PENDING/FAILED stay in the type.
