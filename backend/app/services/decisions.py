"""Effective approval decision = newest admin override, else the original decision."""

from sqlalchemy import select

from app.models.governance import DecisionOverride


def latest_override(db, approval):
    return db.scalar(select(DecisionOverride).where(
        DecisionOverride.approval_request_id == approval.id
    ).order_by(DecisionOverride.created_at.desc(), DecisionOverride.id.desc()).limit(1))


def effective_decision(db, approval) -> str:
    override = latest_override(db, approval)
    return override.new_decision if override is not None else approval.status
