from fastapi.encoders import jsonable_encoder

from app.models.audit import AuditEvent


def record_audit_event(db, execution_id, event_type, payload, *, actor=None,
                       company_id=None, invoice_id=None):
    """Add an audit row in the caller's transaction.

    `actor` is the authenticated user (None for the workflow engine). Company
    scope defaults to the actor's company so tenant activity feeds stay complete.
    """
    if actor is not None:
        payload = {**payload, "actor_email": actor.email, "actor_role": actor.role}
    event = AuditEvent(
        execution_id=execution_id, event_type=event_type,
        payload=jsonable_encoder(payload),
        actor_user_id=actor.id if actor is not None else None,
        company_id=company_id if company_id is not None else getattr(actor, "company_id", None),
        invoice_id=invoice_id,
    )
    db.add(event)
    return event
