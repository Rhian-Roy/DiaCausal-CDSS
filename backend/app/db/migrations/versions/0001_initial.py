"""users, sessions, captcha challenges, audit log

Revision ID: 0001
Revises: (none — first migration)
"""

from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('event', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=True),
    sa.Column('request_id', sa.String(length=36), nullable=False),
    sa.Column('client_trace_id', sa.String(length=64), nullable=True),
    sa.Column('outcome', sa.String(length=32), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_id')
    )
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_log_at'), ['at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_client_trace_id'), ['client_trace_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_event'), ['event'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_user_id'), ['user_id'], unique=False)

    op.create_table('captcha_challenges',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('answer', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('totp_secret_enc', sa.Text(), nullable=True),
    sa.Column('mfa_enrolled', sa.Boolean(), nullable=False),
    sa.Column('last_totp_step', sa.Integer(), nullable=False),
    sa.Column('failed_attempts', sa.Integer(), nullable=False),
    sa.Column('last_failed_at', sa.DateTime(), nullable=True),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.Column('ack_version', sa.String(length=16), nullable=True),
    sa.Column('ack_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_user_id'), ['user_id'], unique=True)

    op.create_table('sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_pk', sa.Integer(), nullable=False),
    sa.Column('stage', sa.String(length=16), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_pk'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash')
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_user_pk'), ['user_pk'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_pk'))

    op.drop_table('sessions')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_user_id'))

    op.drop_table('users')
    op.drop_table('captcha_challenges')
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_log_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_event'))
        batch_op.drop_index(batch_op.f('ix_audit_log_client_trace_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_at'))

    op.drop_table('audit_log')
