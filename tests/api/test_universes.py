"""Universe upload endpoint tests (offline: storage + DB faked)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import alphaforge_api.routes.universes as uni_mod
from alphaforge_api.auth import AuthUser, get_current_user
from alphaforge_api.deps import get_user_db
from alphaforge_api.main import create_app


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store):
        self.store = store
        self.op = None
        self.payload = None

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, *a):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        if self.op == "insert":
            row = {**self.payload, "id": "uni-1", "created_at": "2026-06-14T00:00:00Z"}
            self.store.append(row)
            return _Resp([row])
        return _Resp(list(self.store))


class FakeDB:
    def __init__(self):
        self.store = []

    def table(self, name):
        return _Query(self.store)


class _FakeStorage:
    def from_(self, bucket):
        return self

    def upload(self, *a, **k):
        return None


class _FakeService:
    storage = _FakeStorage()


def _client(monkeypatch):
    monkeypatch.setattr(uni_mod, "service_client", lambda: _FakeService())
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="u1", token="t")
    app.dependency_overrides[get_user_db] = lambda: FakeDB()
    return TestClient(app)


def test_upload_valid_membership_csv(monkeypatch):
    client = _client(monkeypatch)
    csv = b"symbol,start,end\nAAPL,2015-01-01,\nTWTR,2015-01-01,2022-10-27\n"
    r = client.post("/universes", data={"name": "sp-test"}, files={"file": ("m.csv", csv, "text/csv")})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "sp-test"
    assert body["n_symbols"] == 2


def test_upload_invalid_csv_is_400(monkeypatch):
    client = _client(monkeypatch)
    bad = b"foo,bar\n1,2\n"  # no symbol/start columns
    r = client.post("/universes", data={"name": "bad"}, files={"file": ("m.csv", bad, "text/csv")})
    assert r.status_code == 400


def test_upload_requires_auth():
    client = TestClient(create_app())
    csv = b"symbol,start,end\nAAPL,2015-01-01,\n"
    r = client.post("/universes", data={"name": "x"}, files={"file": ("m.csv", csv, "text/csv")})
    assert r.status_code == 401
