# ============================================================
# WBOM — Payroll Approval State Machine Tests  (Sprint-1 P0-02)
# Tests: valid transitions, invalid transitions, lock enforcement,
#        role guard on locked runs, correction flow audit trail.
# All DB calls are monkeypatched — no real DB required.
# ============================================================
import os
import sys
import types
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

# ── Bootstrap ─────────────────────────────────────────────────
WBOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WBOM_DIR not in sys.path:
    sys.path.insert(0, WBOM_DIR)

# ── psycopg2 stub ─────────────────────────────────────────────
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    extras_stub = types.ModuleType("psycopg2.extras")
    pool_stub = types.ModuleType("psycopg2.pool")

    class _ThreadedConnectionPool:
        def __init__(self, *a, **kw): pass
        def getconn(self): return _FakeConn()
        def putconn(self, c): pass

    class _RealDictCursor:
        pass

    class _FakeConn:
        def cursor(self, *a, **kw): return _FakeCursor()
        def commit(self): pass
        def rollback(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class _FakeCursor:
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        def __enter__(self): return self
        def __exit__(self, *a): pass

    pool_stub.ThreadedConnectionPool = _ThreadedConnectionPool
    extras_stub.RealDictCursor = _RealDictCursor
    psycopg2_stub.extras = extras_stub
    psycopg2_stub.pool = pool_stub
    sys.modules["psycopg2"] = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub
    sys.modules["psycopg2.pool"] = pool_stub

if "prometheus_fastapi_instrumentator" not in sys.modules:
    pfi = types.ModuleType("prometheus_fastapi_instrumentator")
    class _Inst:
        def instrument(self, *a, **kw): return self
        def expose(self, *a, **kw): return self
    pfi.Instrumentator = _Inst
    sys.modules["prometheus_fastapi_instrumentator"] = pfi

import services.payroll_engine as engine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import payroll as payroll_routes


def _make_client():
    app = FastAPI()
    app.include_router(payroll_routes.router, prefix="/api/wbom")
    return TestClient(app, raise_server_exceptions=False)


def _draft_run(run_id: int = 1, employee_id: int = 10) -> dict:
    return {
        "run_id": run_id, "employee_id": employee_id, "period_year": 2026,
        "period_month": 4, "status": "draft", "basic_salary": Decimal("10000"),
        "total_programs": 2, "per_program_rate": Decimal("500"),
        "program_allowance": Decimal("1000"), "other_allowance": Decimal("0"),
        "total_advances": Decimal("500"), "total_deductions": Decimal("0"),
        "gross_salary": Decimal("11000"), "net_salary": Decimal("10500"),
        "payout_target_date": "2026-05-10", "payment_method": None,
        "payment_reference": None, "payout_idempotency_key": None,
        "paid_at": None, "computed_by": "admin", "submitted_by": None,
        "approved_by": None, "locked_by": None, "paid_by": None,
        "correction_reason": None, "remarks": None,
        "created_at": "2026-04-21T00:00:00Z", "updated_at": "2026-04-21T00:00:00Z",
    }


def _run_in_status(status: str, run_id: int = 1) -> dict:
    r = _draft_run(run_id)
    r["status"] = status
    return r


# ── P0-02: Valid state transitions ───────────────────────────

def test_valid_submit(monkeypatch):
    """draft → reviewed succeeds."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    monkeypatch.setattr(engine, "update_row", lambda *a, **kw: {**run, "status": "reviewed", "submitted_by": "user1"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    log_calls = []
    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: MagicMock()
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        yield conn
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    result = engine.transition_run(1, "submit", actor="user1")
    assert result["status"] == "reviewed"


def test_valid_approve(monkeypatch):
    """reviewed → approved succeeds."""
    run = _run_in_status("reviewed")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    monkeypatch.setattr(engine, "update_row", lambda *a, **kw: {**run, "status": "approved", "approved_by": "mgr1"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        yield MagicMock()
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    result = engine.transition_run(1, "approve", actor="mgr1")
    assert result["status"] == "approved"


def test_valid_lock(monkeypatch):
    """approved → locked succeeds."""
    run = _run_in_status("approved")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    monkeypatch.setattr(engine, "update_row", lambda *a, **kw: {**run, "status": "locked", "locked_by": "mgr1"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        yield MagicMock()
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    result = engine.transition_run(1, "lock", actor="mgr1")
    assert result["status"] == "locked"


def test_valid_pay(monkeypatch):
    """locked → paid succeeds."""
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    monkeypatch.setattr(engine, "update_row", lambda *a, **kw: {**run, "status": "paid", "paid_by": "cashier"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        yield MagicMock()
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    result = engine.transition_run(1, "pay", actor="cashier",
                                   extra={"payment_method": "Bkash"})
    assert result["status"] == "paid"


# ── P0-02: Invalid transitions rejected ──────────────────────

def test_skip_submit_direct_approve_rejected(monkeypatch):
    """draft cannot go directly to approved — must be reviewed first."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="requires status 'reviewed'"):
        engine.transition_run(1, "approve", actor="mgr1")


def test_draft_to_pay_rejected(monkeypatch):
    """draft cannot skip to paid."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="requires status 'locked'"):
        engine.transition_run(1, "pay", actor="cashier")


def test_reviewed_to_lock_rejected(monkeypatch):
    """reviewed → lock requires approved in between."""
    run = _run_in_status("reviewed")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="requires status 'approved'"):
        engine.transition_run(1, "lock", actor="mgr1")


def test_unknown_action_rejected(monkeypatch):
    """Unknown action raises ValueError."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="Unknown action"):
        engine.transition_run(1, "magic_approve", actor="hacker")


# ── P0-02: Locked run immutability ───────────────────────────

def test_locked_run_rejects_submit(monkeypatch):
    """Locked run refuses submit (or any non-cancel mutation)."""
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="locked"):
        engine.transition_run(1, "submit", actor="someone")


def test_locked_run_rejects_approve(monkeypatch):
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="locked"):
        engine.transition_run(1, "approve", actor="someone")


def test_paid_run_rejects_cancel(monkeypatch):
    """Paid run cannot be cancelled."""
    run = _run_in_status("paid")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="Cannot cancel a paid"):
        engine.transition_run(1, "cancel", actor="admin")


def test_locked_run_rejects_correction(monkeypatch):
    """Correction flow must reject locked/paid runs."""
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    import pytest
    with pytest.raises(ValueError, match="locked"):
        engine.correct_payroll_run(1, actor="admin", reason="typo fix")


# ── P0-02: Run not found ─────────────────────────────────────

def test_transition_run_not_found(monkeypatch):
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: None)
    import pytest
    with pytest.raises(ValueError, match="not found"):
        engine.transition_run(999, "submit", actor="user")


# ── P0-02: HTTP endpoint tests ────────────────────────────────

def test_http_submit_draft_run(monkeypatch):
    """POST /payroll/runs/1/submit returns 200 when transition succeeds."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)
    monkeypatch.setattr(engine, "update_row", lambda *a, **kw: {**run, "status": "reviewed"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        yield MagicMock()
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    client = _make_client()
    resp = client.post("/api/wbom/payroll/runs/1/submit",
                       json={"actor": "reviewer1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"


def test_http_approve_wrong_status_returns_422(monkeypatch):
    """POST /payroll/runs/1/approve on a draft run returns 422."""
    run = _run_in_status("draft")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)

    client = _make_client()
    resp = client.post("/api/wbom/payroll/runs/1/approve",
                       json={"actor": "mgr1"})
    assert resp.status_code == 422


def test_http_lock_locked_run_returns_409(monkeypatch):
    """POST /payroll/runs/1/lock on a locked run returns 409."""
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)

    client = _make_client()
    resp = client.post("/api/wbom/payroll/runs/1/lock",
                       json={"actor": "admin"})
    assert resp.status_code == 409


def test_http_correct_locked_run_returns_409(monkeypatch):
    """POST /payroll/runs/1/correct on a locked run returns 409."""
    run = _run_in_status("locked")
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: run)

    client = _make_client()
    resp = client.post("/api/wbom/payroll/runs/1/correct",
                       json={"actor": "admin", "reason": "need to fix typo"})
    assert resp.status_code == 409


def test_http_run_not_found_returns_404(monkeypatch):
    """GET /payroll/runs/999 returns 404."""
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: None)
    monkeypatch.setattr(engine, "execute_query", lambda *a, **kw: [])

    client = _make_client()
    resp = client.get("/api/wbom/payroll/runs/999")
    assert resp.status_code == 404
