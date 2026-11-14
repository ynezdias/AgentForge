import uuid
from decimal import Decimal
from datetime import date

from sqlalchemy import String, ForeignKey, Numeric, Date, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    external_ref: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    vendor: Mapped["Vendor"] = relationship()


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("duplicate_key", name="uq_invoices_duplicate_key"),
        CheckConstraint("due_date IS NULL OR invoice_date IS NULL OR due_date >= invoice_date", name="ck_invoice_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    vendor: Mapped["Vendor"] = relationship()
    purchase_order: Mapped["PurchaseOrder"] = relationship()
