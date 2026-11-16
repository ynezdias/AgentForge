
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, ForeignKey, Integer, DateTime,
    JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )

    definition: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )

    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Reserved for a future claim/retry mechanism, not an accurate retry metric.
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    input_data: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    context: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False
    )

    # Copied from the invoice at creation so every query can scope by tenant.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    # Escalated executions can only be decided by an admin.
    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )


class StepExecution(Base):
    __tablename__ = "step_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id"),
        nullable=False
    )

    step_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    result: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "execution_id", "step_id",
            name="uq_execution_step"
        ),
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_executions.id"),
        unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    requested_role: Mapped[str] = mapped_column(
        String(30), default="manager", nullable=False
    )
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
