"""API tests with Supabase and the arq queue faked, so they run fully offline.

These pin the request contract: auth is required, creating a backtest persists a
queued row and enqueues exactly one worker job, and reads are shaped correctly.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from alphaforge_api.auth import AuthUser, get_current_user  # noqa: E402
from alphaforge_api.deps import get_queue, get_user_db  # noqa: E402
from alphaforge_api.main import create_app  # noqa: E402


class FakeResp:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self.op = None
        self.payload = None
        self.filters = {}

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def update(self, row):
        self.op, self.payload = "update", row
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.op == "insert":
            row = {**self.payload, "id": "bt-123", "created_at": "2026-06-14T00:00:00Z"}
            rows.append(row)
            return FakeResp([row])
        if self.op == "select":
            if "id" in self.filters:
                return FakeResp([r for r in rows if str(r["id"]) == str(self.filters["id"])])
            return FakeResp(list(rows))
        return FakeResp([])


class FakeDB:
    def __init__(self):
        self.store = {}

    def table(self, name):
        return FakeQuery(self.store, name)


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))


def _client():
    app = create_app()
    db, queue = FakeDB(), FakeQueue()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="u1", token="tok")
    app.dependency_overrides[get_user_db] = lambda: db
    app.dependency_overrides[get_queue] = lambda: queue
    return TestClient(app), db, queue


_BODY = {
    "config": {
        "data": {"symbols": ["AAPL", "MSFT"], "start": "2020-01-01", "end": "2021-01-01"},
        "factor": {"name": "momentum"},
        "name": "unit-test",
    }
}


def test_healthz_needs_no_auth():
    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_persists_queued_row_and_enqueues_one_job():
    client, db, queue = _client()
    r = client.post("/backtests", json=_BODY)
    assert r.status_code == 202
    body = r.json()
    assert body["id"] == "bt-123"
    assert body["status"] == "queued"
    # Exactly one job enqueued, carrying the new id.
    assert queue.jobs == [("run_backtest_job", ("bt-123",))]
    # The persisted row stored the serialized config.
    assert db.store["backtests"][0]["config"]["factor"]["name"] == "momentum"


def test_create_requires_auth():
    # No auth override -> the real dependency rejects the missing token.
    client = TestClient(create_app())
    r = client.post("/backtests", json=_BODY)
    assert r.status_code == 401


def test_get_missing_backtest_is_404():
    client, _, _ = _client()
    r = client.get("/backtests/does-not-exist")
    assert r.status_code == 404
