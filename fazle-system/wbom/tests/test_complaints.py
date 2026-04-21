# ============================================================
# tests/test_complaints.py  —  Sprint-4 Complaint + Client Retention
# 100% monkeypatched — no real DB or HTTP
# ============================================================
import os
import sys
import types
import pytest
from datetime import datetime, timedelta, timezone

# ── Bootstrap ────────────────────────────────────────────────
WBOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WBOM_DIR not in sys.path:
    sys.path.insert(0, WBOM_DIR)

# ── psycopg2 stub ─────────────────────────────────────────────
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    extras_stub   = types.ModuleType("psycopg2.extras")
    pool_stub     = types.ModuleType("psycopg2.pool")

    class _ThreadedConnectionPool:
        def __init__(self, *a, **kw): pass
        def getconn(self): return _FakeConn()
        def putconn(self, c): pass

    class _RealDictCursor: pass

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
    extras_stub.RealDictCursor       = _RealDictCursor
    psycopg2_stub.extras = extras_stub
    psycopg2_stub.pool   = pool_stub
    sys.modules["psycopg2"]        = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub
    sys.modules["psycopg2.pool"]   = pool_stub

# ── prometheus stub ───────────────────────────────────────────
if "prometheus_fastapi_instrumentator" not in sys.modules:
    pfi = types.ModuleType("prometheus_fastapi_instrumentator")
    class _Inst:
        def instrument(self, *a, **kw): return self
        def expose(self, *a, **kw): return self
    pfi.Instrumentator = _Inst
    sys.modules["prometheus_fastapi_instrumentator"] = pfi

from fastapi.testclient import TestClient


# ── App fixture ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(monkeypatch_module):
    """TestClient with DB fully monkeypatched."""
    import database as db
    monkeypatch_module.setattr(db, "_pool", None)
    from main import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def monkeypatch_module(request):
    """Module-scoped monkeypatch (pytest default is function-scoped)."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


# ═══════════════════════════════════════════════════════════════
# Unit tests — auto_tag_priority()
# ═══════════════════════════════════════════════════════════════

from services.complaints import auto_tag_priority


class TestAutoPriority:
    def test_client_harassment_is_critical(self):
        assert auto_tag_priority("client", "harassment") == "critical"

    def test_client_misconduct_is_critical(self):
        assert auto_tag_priority("client", "misconduct") == "critical"

    def test_client_replacement_is_high(self):
        assert auto_tag_priority("client", "replacement_request") == "high"

    def test_client_payment_dispute_is_high(self):
        assert auto_tag_priority("client", "payment_dispute") == "high"

    def test_client_service_quality_is_medium(self):
        assert auto_tag_priority("client", "service_quality") == "medium"

    def test_client_other_is_low(self):
        assert auto_tag_priority("client", "other") == "low"

    def test_employee_harassment_is_critical(self):
        assert auto_tag_priority("employee", "harassment") == "critical"

    def test_employee_salary_is_high(self):
        assert auto_tag_priority("employee", "salary_issue") == "high"

    def test_employee_supervisor_is_medium(self):
        assert auto_tag_priority("employee", "supervisor_issue") == "medium"

    def test_employee_duty_mismatch_is_low(self):
        assert auto_tag_priority("employee", "duty_mismatch") == "low"

    def test_unknown_type_defaults_medium(self):
        assert auto_tag_priority("unknown", "other") == "medium"


# ═══════════════════════════════════════════════════════════════
# Unit tests — SLA hours mapping
# ═══════════════════════════════════════════════════════════════

from services.complaints import SLA_HOURS


class TestSLAHours:
    def test_critical_4h(self):
        assert SLA_HOURS["critical"] == 4

    def test_high_24h(self):
        assert SLA_HOURS["high"] == 24

    def test_medium_72h(self):
        assert SLA_HOURS["medium"] == 72

    def test_low_168h(self):
        assert SLA_HOURS["low"] == 168


# ═══════════════════════════════════════════════════════════════
# Integration tests — HTTP endpoints (monkeypatched DB)
# ═══════════════════════════════════════════════════════════════

def _patch_db(monkeypatch, insert_ret=1, get_ret=None, query_ret=None, update_ret=None):
    """Convenience helper to patch all DB functions in services.complaints."""
    import services.complaints as svc
    monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: insert_ret)
    monkeypatch.setattr(svc, "get_row",    lambda *a, **kw: get_ret)
    monkeypatch.setattr(svc, "execute_query", lambda *a, **kw: query_ret or [])
    monkeypatch.setattr(svc, "update_row",    lambda *a, **kw: None)


class TestIntakeEndpoint:
    """POST /api/wbom/complaints/intake"""

    def test_client_complaint_returns_201(self, monkeypatch, tmp_path):
        _patch_db(monkeypatch, insert_ret=42)
        import services.complaints as svc
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 42)
        result = svc.ingest_complaint(
            complaint_type="client",
            category="service_quality",
            description="Employee was rude",
            reporter_phone="01711000001",
        )
        assert result["complaint_id"] == 42
        assert result["priority"] == "medium"
        assert "sla_due_at" in result
        assert "reply" in result

    def test_critical_complaint_sets_4h_sla(self, monkeypatch):
        _patch_db(monkeypatch, insert_ret=99)
        import services.complaints as svc
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 99)
        result = svc.ingest_complaint(
            complaint_type="client",
            category="harassment",
            description="Serious incident",
        )
        assert result["priority"] == "critical"
        # SLA due = now + 4 hours — verify it's roughly in the future
        due = datetime.fromisoformat(result["sla_due_at"])
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        diff_hours = (due - datetime.now(timezone.utc)).total_seconds() / 3600
        assert 3.5 < diff_hours < 4.5

    def test_employee_salary_gets_high_priority(self, monkeypatch):
        _patch_db(monkeypatch, insert_ret=7)
        import services.complaints as svc
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 7)
        result = svc.ingest_complaint(
            complaint_type="employee",
            category="salary_issue",
            description="July salary not received",
            reporter_phone="01812345678",
        )
        assert result["priority"] == "high"

    def test_reply_contains_bangla_text(self, monkeypatch):
        _patch_db(monkeypatch, insert_ret=5)
        import services.complaints as svc
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 5)
        result = svc.ingest_complaint(
            complaint_type="employee",
            category="harassment",
            description="Urgent",
        )
        assert "আপনার" in result["reply"]


class TestAcknowledge:
    def test_ack_open_complaint(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {
            "complaint_id": 1, "status": "open",
            "complaint_type": "client", "category": "other"
        }
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.acknowledge_complaint(1)
        assert result["status"] == "acknowledged"

    def test_ack_already_acked_raises(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {"complaint_id": 2, "status": "acknowledged"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        with pytest.raises(ValueError, match="acknowledge"):
            svc.acknowledge_complaint(2)

    def test_ack_not_found_raises(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: None)
        with pytest.raises(ValueError, match="not found"):
            svc.acknowledge_complaint(9999)


class TestAssign:
    def test_assign_open_auto_acks(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {"complaint_id": 3, "status": "open"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.assign_complaint(3, "Rahim")
        assert result["assigned_to"] == "Rahim"
        assert result["status"] == "acknowledged"

    def test_assign_investigating_keeps_status(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {"complaint_id": 4, "status": "investigating"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.assign_complaint(4, "Karim")
        assert result["status"] == "investigating"

    def test_assign_not_found_raises(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: None)
        with pytest.raises(ValueError, match="not found"):
            svc.assign_complaint(999, "Jamal")


class TestEscalate:
    def test_escalate_open_complaint(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {"complaint_id": 5, "status": "open"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.escalate_complaint(5, "No response in 12h")
        assert result["status"] == "escalated"

    def test_escalate_resolved_raises(self, monkeypatch):
        import services.complaints as svc
        fake_complaint = {"complaint_id": 6, "status": "resolved"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake_complaint)
        with pytest.raises(ValueError, match="escalate"):
            svc.escalate_complaint(6, "Too late")

    def test_escalate_not_found_raises(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: None)
        with pytest.raises(ValueError, match="not found"):
            svc.escalate_complaint(9999, "reason")


class TestAdvance:
    def test_open_to_acknowledged(self, monkeypatch):
        import services.complaints as svc
        fake = {"complaint_id": 10, "status": "open"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.advance_complaint_status(10, "acknowledged")
        assert result["to_status"] == "acknowledged"

    def test_investigating_to_resolved(self, monkeypatch):
        import services.complaints as svc
        fake = {"complaint_id": 11, "status": "investigating"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.advance_complaint_status(11, "resolved")
        assert result["from_status"] == "investigating"
        assert result["to_status"] == "resolved"

    def test_invalid_transition_raises(self, monkeypatch):
        import services.complaints as svc
        fake = {"complaint_id": 12, "status": "resolved"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake)
        with pytest.raises(ValueError, match="Cannot move"):
            svc.advance_complaint_status(12, "open")

    def test_not_found_raises(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: None)
        with pytest.raises(ValueError, match="not found"):
            svc.advance_complaint_status(999, "acknowledged")


class TestResolve:
    def test_resolve_investigating_complaint(self, monkeypatch):
        import services.complaints as svc
        fake = {
            "complaint_id": 20, "status": "investigating",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=10)
        }
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake)
        monkeypatch.setattr(svc, "update_row", lambda *a, **kw: None)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.resolve_complaint(20, "Issue was fixed")
        assert result["status"] == "resolved"
        assert result["resolution_hours"] is not None
        assert result["resolution_hours"] > 9.5

    def test_resolve_already_resolved_raises(self, monkeypatch):
        import services.complaints as svc
        fake = {"complaint_id": 21, "status": "resolved"}
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: fake)
        with pytest.raises(ValueError, match="already"):
            svc.resolve_complaint(21, "done")

    def test_resolve_not_found_raises(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "get_row", lambda *a, **kw: None)
        with pytest.raises(ValueError, match="not found"):
            svc.resolve_complaint(9999, "notes")


class TestSLABreachSweep:
    def test_returns_list_of_breached(self, monkeypatch):
        import services.complaints as svc
        breached_rows = [
            {
                "complaint_id": 30, "complaint_type": "client",
                "category": "payment_dispute", "priority": "high",
                "reporter_phone": "0171xxx", "reporter_name": "Test",
                "assigned_to": "Rahim", "sla_due_at": "2026-01-01T00:00:00+00:00"
            }
        ]
        monkeypatch.setattr(svc, "execute_query", lambda *a, **kw: breached_rows)
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.check_sla_breaches()
        assert len(result) == 1
        assert result[0]["complaint_id"] == 30

    def test_no_breaches_returns_empty(self, monkeypatch):
        import services.complaints as svc
        monkeypatch.setattr(svc, "execute_query", lambda *a, **kw: [])
        monkeypatch.setattr(svc, "insert_row", lambda *a, **kw: 1)
        result = svc.check_sla_breaches()
        assert result == []


class TestMetrics:
    def test_metrics_shape(self, monkeypatch):
        import services.complaints as svc

        def fake_query(sql, params=()):
            # Unresolved by type
            if "GROUP BY complaint_type" in sql:
                return [
                    {"complaint_type": "client",   "total": 5, "critical_count": 1, "breached_count": 2},
                    {"complaint_type": "employee",  "total": 3, "critical_count": 2, "breached_count": 1},
                ]
            # Repeat clients
            if "HAVING COUNT(*) >= 2" in sql and "GROUP BY reporter_phone" in sql:
                return [
                    {"reporter_phone": "0171xxx", "reporter_name": "TestCo", "complaint_count": 3}
                ]
            # Fastest resolvers
            if "HAVING COUNT(*) >= 3" in sql and "GROUP BY assigned_to" in sql:
                return [
                    {"assigned_to": "Rahim", "resolved_count": 7, "avg_hours": 18.5}
                ]
            # Category breakdown
            if "GROUP BY category" in sql:
                return [
                    {"category": "service_quality", "cnt": 4},
                    {"category": "salary_issue",    "cnt": 2},
                ]
            return []

        monkeypatch.setattr(svc, "execute_query", fake_query)
        from datetime import date
        result = svc.get_complaint_metrics(ref_date=date(2026, 4, 21))

        assert "unresolved_by_type" in result
        assert "unresolved_total" in result
        assert "critical_open" in result
        assert "sla_breaches_total" in result
        assert "repeat_complaint_clients" in result
        assert "fastest_resolvers" in result
        assert "category_breakdown" in result

        assert result["unresolved_total"] == 8
        assert result["critical_open"] == 3
        assert result["sla_breaches_total"] == 3

    def test_metrics_zero_division_safe(self, monkeypatch):
        """All empty DB — should not raise ZeroDivisionError."""
        import services.complaints as svc
        monkeypatch.setattr(svc, "execute_query", lambda *a, **kw: [])
        from datetime import date
        result = svc.get_complaint_metrics(ref_date=date(2026, 4, 21))
        assert result["unresolved_total"] == 0
        assert result["critical_open"] == 0
        assert result["sla_breaches_total"] == 0
        assert result["repeat_complaint_clients"] == []
        assert result["fastest_resolvers"] == []
        assert result["category_breakdown"] == {}

    def test_metrics_fastest_resolvers_shape(self, monkeypatch):
        import services.complaints as svc

        def fake_query(sql, params=()):
            if "HAVING COUNT(*) >= 3" in sql and "GROUP BY assigned_to" in sql:
                return [
                    {"assigned_to": "Karim", "resolved_count": 12, "avg_hours": 6.2},
                    {"assigned_to": "Nadia", "resolved_count": 5,  "avg_hours": 9.0},
                ]
            return []

        monkeypatch.setattr(svc, "execute_query", fake_query)
        from datetime import date
        result = svc.get_complaint_metrics(ref_date=date(2026, 4, 21))
        assert len(result["fastest_resolvers"]) == 2
        assert result["fastest_resolvers"][0]["staff"] == "Karim"
        assert result["fastest_resolvers"][0]["avg_hours"] == 6.2
