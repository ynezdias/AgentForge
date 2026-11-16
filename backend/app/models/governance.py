import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DecisionOverride(Base):
    """Append-only record of an admin replacing an approval decision.

    The original ApprovalRequest row is never edited; the effective decision is
    the newest override, or the original decision when there is none.
    """

    __tablename__ = "decision_overrides"
    __table_args__ = (
        CheckConstraint("original_decision IN ('APPROVED', 'REJECTED')", name="ck_override_original"),
        CheckConstraint("new_decision IN ('APPROVED', 'REJECTED')", name="ck_override_new"),
        CheckConstraint("original_decision <> new_decision", name="ck_override_changes_decision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_executions.id"), nullable=False, index=True)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    original_decision: Mapped[str] = mapped_column(String(20), nullable=False)
    new_decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
