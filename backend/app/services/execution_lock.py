import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session


def execution_lock_id(execution_id):
    digest = hashlib.sha256(str(execution_id).encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def acquire_execution_lock(db: Session, execution_id):
    return db.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": execution_lock_id(execution_id)},
    ).scalar()
