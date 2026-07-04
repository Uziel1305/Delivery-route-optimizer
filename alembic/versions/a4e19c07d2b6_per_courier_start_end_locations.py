"""per-courier start/end locations replace the day-level depot

Revision ID: a4e19c07d2b6
Revises: c7d1a52e8f03
Create Date: 2026-07-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4e19c07d2b6'
down_revision = 'c7d1a52e8f03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default terminals on the courier's profile (nullable = not onboarded yet).
    op.add_column('courier_profiles', sa.Column('start_lat', sa.Float(), nullable=True))
    op.add_column('courier_profiles', sa.Column('start_lon', sa.Float(), nullable=True))
    op.add_column('courier_profiles', sa.Column('start_address_label', sa.String(length=255), nullable=True))
    op.add_column('courier_profiles', sa.Column('end_lat', sa.Float(), nullable=True))
    op.add_column('courier_profiles', sa.Column('end_lon', sa.Float(), nullable=True))
    op.add_column('courier_profiles', sa.Column('end_address_label', sa.String(length=255), nullable=True))

    # Per-day copy on the assignment row (copy-on-assign).
    op.add_column('job_couriers', sa.Column('start_lat', sa.Float(), nullable=True))
    op.add_column('job_couriers', sa.Column('start_lon', sa.Float(), nullable=True))
    op.add_column('job_couriers', sa.Column('start_address_label', sa.String(length=255), nullable=True))
    op.add_column('job_couriers', sa.Column('end_lat', sa.Float(), nullable=True))
    op.add_column('job_couriers', sa.Column('end_lon', sa.Float(), nullable=True))
    op.add_column('job_couriers', sa.Column('end_address_label', sa.String(length=255), nullable=True))

    op.create_table(
        'location_change_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('courier_id', sa.String(length=36), nullable=False),
        sa.Column('start_lat', sa.Float(), nullable=False),
        sa.Column('start_lon', sa.Float(), nullable=False),
        sa.Column('start_address_label', sa.String(length=255), nullable=False),
        sa.Column('end_lat', sa.Float(), nullable=False),
        sa.Column('end_lon', sa.Float(), nullable=False),
        sa.Column('end_address_label', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'APPROVED', 'DECLINED', 'CANCELLED', name='locationrequeststatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['courier_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_location_change_requests_courier_id'), 'location_change_requests', ['courier_id'], unique=False
    )

    # The day-level depot is gone.
    op.drop_column('jobs', 'depot_lat')
    op.drop_column('jobs', 'depot_lon')
    op.drop_column('jobs', 'depot_address_label')


def downgrade() -> None:
    op.add_column('jobs', sa.Column('depot_address_label', sa.String(length=255), nullable=True))
    op.add_column('jobs', sa.Column('depot_lon', sa.Float(), nullable=False, server_default='0'))
    op.add_column('jobs', sa.Column('depot_lat', sa.Float(), nullable=False, server_default='0'))

    op.drop_index(op.f('ix_location_change_requests_courier_id'), table_name='location_change_requests')
    op.drop_table('location_change_requests')
    sa.Enum(name='locationrequeststatus').drop(op.get_bind(), checkfirst=True)

    for col in ('start_lat', 'start_lon', 'start_address_label', 'end_lat', 'end_lon', 'end_address_label'):
        op.drop_column('job_couriers', col)
        op.drop_column('courier_profiles', col)
