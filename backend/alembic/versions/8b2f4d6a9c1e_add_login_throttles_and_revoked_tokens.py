"""Add sign-in throttling and server-side token revocation.

Revision ID: 8b2f4d6a9c1e
Revises: 5c1e8a3f2b7d
"""
from alembic import op
import sqlalchemy as sa

revision = "8b2f4d6a9c1e"
down_revision = "5c1e8a3f2b7d"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "login_throttles",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", TS, nullable=False),
        sa.Column("locked_until", TS, nullable=True),
    )
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("expires_at", TS, nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade():
    op.drop_index("ix_revoked_tokens_expires_at", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_table("login_throttles")
