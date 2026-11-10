import os
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.session import engine
from app.services.execution_lock import acquire_execution_lock, execution_lock_id


def test_lock_id_is_stable_signed_bigint():
    value = uuid4()
    assert execution_lock_id(value) == execution_lock_id(str(value))
    assert -(2 ** 63) <= execution_lock_id(value) < 2 ** 63


@pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL")
@pytest.mark.parametrize("release", ["commit", "rollback"])
def test_lock_excludes_second_connection_and_releases(release):
    execution_id = uuid4()
    with Session(engine) as first, Session(engine) as second:
        assert acquire_execution_lock(first, execution_id) is True
        assert acquire_execution_lock(second, execution_id) is False
        getattr(first, release)()
        assert acquire_execution_lock(second, execution_id) is True
