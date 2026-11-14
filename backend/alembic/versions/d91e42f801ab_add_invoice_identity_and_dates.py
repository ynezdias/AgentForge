"""Add invoice identity, dates, and concurrent duplicate protection.

Existing sample invoices remain unnumbered; no guessed identifiers or dates.
"""
from alembic import op
import sqlalchemy as sa

revision = "d91e42f801ab"
down_revision = "27e10c63e12d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("invoice_number", sa.String(100), nullable=True))
    op.add_column("invoices", sa.Column("invoice_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("duplicate_key", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_invoices_duplicate_key", "invoices", ["duplicate_key"])
    op.create_check_constraint("ck_invoice_dates", "invoices", "due_date IS NULL OR invoice_date IS NULL OR due_date >= invoice_date")


def downgrade():
    op.drop_constraint("ck_invoice_dates", "invoices", type_="check")
    op.drop_constraint("uq_invoices_duplicate_key", "invoices", type_="unique")
    for name in ("duplicate_key", "due_date", "invoice_date", "invoice_number"):
        op.drop_column("invoices", name)
