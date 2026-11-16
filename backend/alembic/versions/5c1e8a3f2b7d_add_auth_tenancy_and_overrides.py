"""Add companies, users, tenant ownership, escalation, actor audit, and decision overrides.

Additive only: existing rows keep company_id NULL (admin-visible) until the
local demo setup assigns them. No passwords or accounts are created here.

Revision ID: 5c1e8a3f2b7d
Revises: d91e42f801ab
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "5c1e8a3f2b7d"
down_revision = "d91e42f801ab"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_login_at", TS, nullable=True),
        sa.CheckConstraint("role IN ('admin', 'company')", name="ck_users_role"),
        sa.CheckConstraint(
            "(role = 'admin' AND company_id IS NULL) OR (role = 'company' AND company_id IS NOT NULL)",
            name="ck_users_role_company"),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])

    for table in ("purchase_orders", "invoices", "workflow_executions"):
        op.add_column(table, sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=True))
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.add_column("workflow_executions", sa.Column("escalated_at", TS, nullable=True))

    op.add_column("approval_requests", sa.Column(
        "decided_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("approval_requests", sa.Column("decided_at", TS, nullable=True))

    op.alter_column("audit_events", "execution_id", existing_type=UUID, nullable=True)
    op.add_column("audit_events", sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("audit_events", sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=True))
    op.add_column("audit_events", sa.Column("invoice_id", UUID, sa.ForeignKey("invoices.id"), nullable=True))
    op.create_index("ix_audit_events_execution_id", "audit_events", ["execution_id"])
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "decision_overrides",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("execution_id", UUID, sa.ForeignKey("workflow_executions.id"), nullable=False),
        sa.Column("approval_request_id", UUID, sa.ForeignKey("approval_requests.id"), nullable=False),
        sa.Column("admin_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_decision", sa.String(20), nullable=False),
        sa.Column("new_decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("original_decision IN ('APPROVED', 'REJECTED')", name="ck_override_original"),
        sa.CheckConstraint("new_decision IN ('APPROVED', 'REJECTED')", name="ck_override_new"),
        sa.CheckConstraint("original_decision <> new_decision", name="ck_override_changes_decision"),
    )
    op.create_index("ix_decision_overrides_execution_id", "decision_overrides", ["execution_id"])


def downgrade():
    op.drop_index("ix_decision_overrides_execution_id", table_name="decision_overrides")
    op.drop_table("decision_overrides")
    for name in ("created_at", "company_id", "execution_id"):
        op.drop_index(f"ix_audit_events_{name}", table_name="audit_events")
    for column in ("invoice_id", "company_id", "actor_user_id"):
        op.drop_column("audit_events", column)
    # Fails if engine-less events exist; delete or reassign them before downgrading.
    op.alter_column("audit_events", "execution_id", existing_type=UUID, nullable=False)
    op.drop_column("approval_requests", "decided_at")
    op.drop_column("approval_requests", "decided_by_user_id")
    op.drop_column("workflow_executions", "escalated_at")
    for table in ("workflow_executions", "invoices", "purchase_orders"):
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_column(table, "company_id")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_table("users")
    op.drop_table("companies")
