# ============================================================
# WBOM — Payment Idempotency + Duplicate Guard Tests (Sprint-1 P0-03)
# Tests: duplicate run creation blocked, payout idempotency key guard,
#        transaction-level idempotency (existing behaviour), HTTP responses.
# All DB calls are monkeypatched — no real DB required.
# ============================================================
import os
import sys
import types
from decimal import Decimal

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
from routes import transactions as tx_routes


def _make_payroll_client():
    app = FastAPI()
    app.include_router(payroll_routes.router, prefix="/api/wbom")
    return TestClient(app, raise_server_exceptions=False)


def _make_tx_client():
    app = FastAPI()
    app.include_router(tx_routes.router, prefix="/api/wbom")
    return TestClient(app, raise_server_exceptions=False)


def _locked_run(run_id: int = 5) -> dict:
    return {
        "run_id": run_id, "employee_id": 10, "period_year": 2026, "period_month": 4,
        "status": "locked", "basic_salary": Decimal("10000"),
        "total_programs": 2, "per_program_rate": Decimal("500"),
        "program_allowance": Decimal("1000"), "other_allowance": Decimal("0"),
        "total_advances": Decimal("500"), "total_deductions": Decimal("0"),
        "gross_salary": Decimal("11000"), "net_salary": Decimal("10500"),
        "payout_target_date": "2026-05-10", "payment_method": None,
        "payment_reference": None, "payout_idempotency_key": None,
        "paid_at": None, "computed_by": "admin", "submitted_by": "reviewer",
        "approved_by": "mgr", "locked_by": "mgr", "paid_by": None,
        "correction_reason": None, "remarks": None,
        "created_at": "2026-04-21T00:00:00Z", "updated_at": "2026-04-21T00:00:00Z",
    }


# ── P0-03: Duplicate payroll run creation blocked ─────────────

def test_create_run_duplicate_blocked(monkeypatch):
    """create_payroll_run raises ValueError if non-cancelled run already exists."""
    monkeypatch.setattr(engine, "execute_query",
                        lambda sql, params=(): [{"run_id": 42, "status": "draft"}]
                        if "FROM wbom_payroll_runs" in sql else [])

    import pytest
    with pytest.raises(ValueError, match="already exists"):
        engine.create_payroll_run(
            employee_id=10, month=4, year=2026, computed_by="admin"
        )


def test_create_run_after_cancellation_allowed(monkeypatch):
    """create_payroll_run succeeds when prior run is cancelled."""
    call_counter = [0]
    employee = {"employee_id": 10, "employee_name": "Jane", "basic_salary": Decimal("8000")}

    def fake_execute_query(sql, params=()):
        # First call: duplicate guard query returns empty (no active run)
        # Subsequent calls: formula queries
        call_counter[0] += 1
        if "FROM wbom_payroll_runs" in sql:
            return []   # no active run — safe to create
        if "wbom_escort_programs" in sql:
            return [{"total": 1}]
        if "wbom_cash_transactions" in sql and "Advance" in sql:
            return [{"total": Decimal("0")}]
        if "wbom_cash_transactions" in sql and "Deduction" in sql:
            return [{"total": Decimal("0")}]
        return []

    inserted_run = {"run_id": 43, "employee_id": 10, "period_year": 2026,
                    "period_month": 4, "status": "draft", "basic_salary": "8000",
                    "total_programs": 1, "per_program_rate": "500",
                    "program_allowance": "500", "other_allowance": "0",
                    "total_advances": "0", "total_deductions": "0",
                    "gross_salary": "8500", "net_salary": "8500",
                    "payout_target_date": "2026-05-10", "computed_by": "admin",
                    "created_at": "2026-04-21", "updated_at": "2026-04-21"}

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        from unittest.mock import MagicMock
        conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = inserted_run
        conn.cursor.return_value = mock_cursor
        yield conn

    monkeypatch.setattr(engine, "execute_query", fake_execute_query)
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: employee)
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    run = engine.create_payroll_run(employee_id=10, month=4, year=2026, computed_by="admin")
    assert run["run_id"] == 43
    assert run["status"] == "draft"


def test_http_create_run_duplicate_returns_409(monkeypatch):
    """POST /payroll/runs returns 409 when active run already exists."""
    monkeypatch.setattr(engine, "execute_query",
                        lambda sql, params=(): [{"run_id": 42, "status": "reviewed"}]
                        if "FROM wbom_payroll_runs" in sql else [])

    client = _make_payroll_client()
    resp = client.post("/api/wbom/payroll/runs", json={
        "employee_id": 10, "period_year": 2026, "period_month": 4,
        "computed_by": "admin",
    })
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "duplicate_run"


# ── P0-03: Payout idempotency key guard ──────────────────────

def test_check_payout_idempotency_returns_existing(monkeypatch):
    """check_payout_idempotency returns run when key was already used."""
    existing = {"run_id": 5, "status": "paid", "payout_idempotency_key": "key-abc"}
    monkeypatch.setattr(engine, "execute_query", lambda sql, params=(): [existing])

    result = engine.check_payout_idempotency("key-abc")
    assert result is not None
    assert result["run_id"] == 5


def test_check_payout_idempotency_returns_none_for_new_key(monkeypatch):
    """check_payout_idempotency returns None when key is unused."""
    monkeypatch.setattr(engine, "execute_query", lambda sql, params=(): [])

    result = engine.check_payout_idempotency("brand-new-key")
    assert result is None


def test_http_pay_duplicate_idempotency_key_returns_duplicate_response(monkeypatch):
    """POST /payroll/runs/5/pay with already-used key returns duplicate=True."""
    existing_paid_run = {"run_id": 5, "status": "paid",
                         "payout_idempotency_key": "idem-xyz"}
    monkeypatch.setattr(engine, "execute_query",
                        lambda sql, params=(): [existing_paid_run])

    client = _make_payroll_client()
    resp = client.post("/api/wbom/payroll/runs/5/pay", json={
        "actor": "cashier",
        "payment_method": "Bkash",
        "payout_idempotency_key": "idem-xyz",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["duplicate"] is True
    assert body["existing_run_id"] == 5


def test_http_pay_fresh_idempotency_key_proceeds(monkeypatch):
    """POST /payroll/runs/5/pay with fresh key proceeds to transition."""
    locked_run = _locked_run(5)

    call_count = [0]
    def fake_execute_query(sql, params=()):
        call_count[0] += 1
        return []   # no existing run for idempotency check

    monkeypatch.setattr(engine, "execute_query", fake_execute_query)
    monkeypatch.setattr(engine, "get_row", lambda *a, **kw: locked_run)
    monkeypatch.setattr(engine, "update_row",
                        lambda *a, **kw: {**locked_run, "status": "paid", "paid_by": "cashier"})
    monkeypatch.setattr(engine, "audit_log", lambda *a, **kw: None)

    import contextlib
    @contextlib.contextmanager
    def fake_get_conn():
        from unittest.mock import MagicMock
        yield MagicMock()
    monkeypatch.setattr(engine, "get_conn", fake_get_conn)

    client = _make_payroll_client()
    resp = client.post("/api/wbom/payroll/runs/5/pay", json={
        "actor": "cashier",
        "payment_method": "Bkash",
        "payout_idempotency_key": "fresh-key-001",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"


# ── P0-03: Transaction-level idempotency (existing route) ────

def test_transaction_idempotency_duplicate_blocked(monkeypatch):
    """POST /transactions with same idempotency_key returns existing row.
    The route always returns 201 (default status_code); the body contains
    the pre-existing transaction, so we verify by transaction_id."""
    existing_tx = {
        "transaction_id": 77, "employee_id": 10, "transaction_type": "Advance",
        "amount": "500.00", "payment_method": "Cash", "transaction_date": "2026-04-01",
        "transaction_time": "2026-04-01T10:00:00Z", "status": "Completed",
        "idempotency_key": "idem-tx-001", "created_by": "admin",
        "reference_number": None, "remarks": None, "whatsapp_message_id": None,
        "source": "web", "approved_by": None, "approved_at": None, "program_id": None,
        "payment_mobile": None,
    }

    # Must patch the name in the route module, not in database module
    monkeypatch.setattr(tx_routes, "insert_row_dedup",
                        lambda table, data, conflict_cols: (existing_tx, False))
    monkeypatch.setattr(tx_routes, "audit_log", lambda *a, **kw: None)

    client = _make_tx_client()
    resp = client.post("/api/wbom/transactions", json={
        "employee_id": 10,
        "transaction_type": "Advance",
        "amount": "500.00",
        "payment_method": "Cash",
        "transaction_date": "2026-04-01",
        "idempotency_key": "idem-tx-001",
    })
    # Route default status_code=201 applies even to duplicate returns
    assert resp.status_code == 201
    body = resp.json()
    assert body["transaction_id"] == 77


def test_transaction_without_idempotency_key_creates_new(monkeypatch):
    """POST /transactions without idempotency_key always creates a new row."""
    new_tx = {
        "transaction_id": 78, "employee_id": 10, "transaction_type": "Advance",
        "amount": "500.00", "payment_method": "Cash", "transaction_date": "2026-04-01",
        "transaction_time": "2026-04-01T10:01:00Z", "status": "Completed",
        "idempotency_key": None, "created_by": "admin",
        "reference_number": None, "remarks": None, "whatsapp_message_id": None,
        "source": "web", "approved_by": None, "approved_at": None, "program_id": None,
        "payment_mobile": None,
    }
    # Patch names in the route module, not in database module
    monkeypatch.setattr(tx_routes, "insert_row", lambda table, data: new_tx)
    monkeypatch.setattr(tx_routes, "audit_log", lambda *a, **kw: None)

    client = _make_tx_client()
    resp = client.post("/api/wbom/transactions", json={
        "employee_id": 10,
        "transaction_type": "Advance",
        "amount": "500.00",
        "payment_method": "Cash",
        "transaction_date": "2026-04-01",
    })
    assert resp.status_code == 201
    assert resp.json()["transaction_id"] == 78


def test_duplicate_payout_idempotency_deterministic_response(monkeypatch):
    """Repeated payout with same key always returns the same existing_run_id."""
    existing = {"run_id": 9, "status": "paid", "payout_idempotency_key": "fixed-key"}
    monkeypatch.setattr(engine, "execute_query", lambda sql, params=(): [existing])

    client = _make_payroll_client()

    # Call it twice — must return the same result both times
    for _ in range(2):
        resp = client.post("/api/wbom/payroll/runs/9/pay", json={
            "actor": "cashier",
            "payment_method": "Bkash",
            "payout_idempotency_key": "fixed-key",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["duplicate"] is True
        assert body["existing_run_id"] == 9
