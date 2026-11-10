from fastapi.encoders import jsonable_encoder

from app.models.audit import AuditEvent


def record_audit_event(db, execution_id, event_type, payload):
    event = AuditEvent(
        execution_id=execution_id, event_type=event_type,
        payload=jsonable_encoder(payload),
    )
    db.add(event)
    return event
