"""
Test setup. Run from the backend folder:  python -m pytest

The tests use a throwaway SQLite database, so they never touch the app database in .env.
The phase 1 query engine needs PostgreSQL, so /api/query is not covered here.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# Settings are read when the app is imported, so set them first.
_tmp = Path(tempfile.mkdtemp(prefix="bi-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'app.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["CONNECTIONS_KEY"] = Fernet.generate_key().decode()
os.environ["SCHEDULER_ENABLED"] = "false"  # tests run refreshes themselves (refresh.run_due)

from fastapi.testclient import TestClient  # noqa: E402

from app.migrate import upgrade  # noqa: E402

upgrade()  # build the schema from the Alembic migrations, like a new install

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

seed()

MANAGER = ("manager@example.com", "Manager@123")
USER = ("user@example.com", "User@123")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="session")
def manager(client) -> dict:
    return _login(client, *MANAGER)


@pytest.fixture(scope="session")
def user(client) -> dict:
    return _login(client, *USER)


@pytest.fixture(scope="session")
def business_db() -> str:
    """A small SQLite file standing in for a company database."""
    path = _tmp / "business.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, region TEXT, amount REAL);
        CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE VIEW IF NOT EXISTS big_orders AS SELECT * FROM orders WHERE amount > 1000;
    """)
    con.close()
    return path.as_posix()


REPORT_CONFIG = {"params": {"period": "q1_2024", "measure": "net", "date_col": "sale_date", "region": "All"}}


@pytest.fixture
def make_report(client):
    def make(headers: dict, title: str = "Test report") -> dict:
        res = client.post("/api/reports", headers=headers, json={"title": title, "prompt": "p", "config": REPORT_CONFIG})
        assert res.status_code == 201, res.text
        return res.json()
    return make
