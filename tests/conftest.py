import os
from pathlib import Path

_TEST_DB_PATH = Path(__file__).resolve().parent / "test_gestordecontrato.db"
os.environ["GESTORDECONTRATO_DB_PATH"] = str(_TEST_DB_PATH)

import pytest  # noqa: E402  (o ambiente precisa estar montado antes de qualquer import de app)

@pytest.fixture(autouse=True)
def _clean_test_db():
    yield
    from app import database

    database.engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
