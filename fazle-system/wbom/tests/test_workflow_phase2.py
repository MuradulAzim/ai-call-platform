# ============================================================
# WBOM Workflow Phase-2 API Tests
# Covers: case list/detail, escalation monitor,
#         case status transition, escalation actions
# ============================================================
import os
import sys
import types
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Ensure WBOM package root is importable
WBOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WBOM_DIR not in sys.path:
    sys.path.insert(0, WBOM_DIR)

# Provide lightweight psycopg2 stubs so database.py can import in tests.
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    extras_stub = types.ModuleType("psycopg2.extras")
    pool_stub = types.ModuleType("psycopg2.pool")

    class _SimpleConnectionPool:
        def __init__(self, *args, **kwargs):
            pass

    class _RealDictCursor:
        pass

    pool_stub.SimpleConnectionPool = _SimpleConnectionPool
    extras_stub.RealDictCursor = _RealDictCursor

    psycopg2_stub.extras = extras_stub
    psycopg2_stub.pool = pool_stub

    sys.modules["psycopg2"] = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub
    sys.modules["psycopg2.pool"] = pool_stub

from routes import workflow as workflow_routes


def _build_client():
    app = FastAPI()
    app.include_router(workflow_routes.router, prefix="/api/wbom")
    return TestClient(app, raise_server_exceptions=False)


def test_list_cases_with_filters_and_pagination(monkeypatch):
    client = _build_client()

    def fake_execute_query(sql, params=()):
        if "SELECT COUNT(*) AS total" in sql:
            return [{"total": 1}]
        if "FROM wbom_cases c" in sql:
            return [{
                "case_id": 101,
                "case_type": "complaint",
                "source_platform": "whatsapp",
                "source_channel": "inbound_message",
                "contact_id": 12,
                "employee_id": None,
                "related_program_id": None,
                "title": "Guard absent",
                "description": "No guard at post",
                "priority": "high",
                "severity": "critical",
                "status": "open",
                "owner_role": "operation_manager",
                "owner_user": None,
                "opened_at": "2026-04-21T01:00:00Z",
                "first_response_at": None,
                "due_at": "2026-04-21T03:00:00Z",
                "resolved_at": None,
                "closed_at": None,
                "metadata_json": {"source_message_id": "m-1"},
                "created_at": "2026-04-21T01:00:00Z",
                "updated_at": "2026-04-21T01:00:00Z",
                "pending_tasks": 1,
                "event_count": 2,
            }]
        return []

    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)

    res = client.get("/api/wbom/workflow/cases", params={"limit": 10, "offset": 0, "status": "open"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["total"] == 1
    assert payload["items"][0]["case_id"] == 101


def test_get_case_detail_with_events_and_tasks(monkeypatch):
    client = _build_client()

    def fake_get_row(table, pk_col, pk_val):
        if table == "wbom_cases" and pk_col == "case_id" and pk_val == 101:
            return {
                "case_id": 101,
                "case_type": "complaint",
                "status": "open",
                "title": "Guard issue",
                "metadata_json": {},
            }
        return None

    def fake_execute_query(sql, params=()):
        if "FROM wbom_case_events" in sql:
            return [{"event_id": 1, "event_type": "case_opened"}]
        if "FROM wbom_workflow_tasks" in sql:
            return [{"workflow_task_id": 7, "task_status": "pending"}]
        return []

    monkeypatch.setattr(workflow_routes, "get_row", fake_get_row)
    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)

    res = client.get("/api/wbom/workflow/cases/101")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["case"]["case_id"] == 101
    assert body["event_count"] == 1
    assert body["task_count"] == 1


def test_escalation_monitor_summary(monkeypatch):
    client = _build_client()

    def fake_execute_query(sql, params=()):
        if "FROM wbom_cases c" in sql:
            return [
                {"case_id": 1, "sla_state": "overdue"},
                {"case_id": 2, "sla_state": "due_soon"},
                {"case_id": 3, "sla_state": "within_sla"},
            ]
        if "FROM wbom_workflow_tasks wt" in sql:
            return [{"workflow_task_id": 9}, {"workflow_task_id": 10}]
        return []

    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)

    res = client.get("/api/wbom/workflow/escalations/monitor", params={"window_minutes": 90})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["summary"]["overdue_cases"] == 1
    assert body["summary"]["due_soon_cases"] == 1
    assert body["summary"]["overdue_tasks"] == 2


def test_transition_case_status_success(monkeypatch):
    client = _build_client()
    calls = {"update": [], "insert": [], "audit": [], "sql": []}

    state = {
        "case": {
            "case_id": 101,
            "status": "in_progress",
            "first_response_at": "2026-04-21T01:00:00Z",
            "metadata_json": {},
        }
    }

    def fake_get_row(table, pk_col, pk_val):
        if table == "wbom_cases" and pk_col == "case_id" and pk_val == 101:
            return state["case"]
        return None

    def fake_update_row(table, pk_col, pk_val, data):
        calls["update"].append((table, pk_col, pk_val, data))
        if table == "wbom_cases" and pk_val == 101:
            state["case"] = {**state["case"], **data}
        return state["case"]

    def fake_execute_query(sql, params=()):
        calls["sql"].append((sql, params))
        return []

    def fake_insert_row(table, data):
        calls["insert"].append((table, data))
        return {"event_id": 1}

    def fake_audit_log(*args, **kwargs):
        calls["audit"].append((args, kwargs))

    monkeypatch.setattr(workflow_routes, "get_row", fake_get_row)
    monkeypatch.setattr(workflow_routes, "update_row", fake_update_row)
    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)
    monkeypatch.setattr(workflow_routes, "insert_row", fake_insert_row)
    monkeypatch.setattr(workflow_routes, "audit_log", fake_audit_log)

    res = client.post(
        "/api/wbom/workflow/cases/101/status",
        json={"new_status": "resolved", "changed_by": "ops-admin", "reason": "Issue fixed"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["old_status"] == "in_progress"
    assert body["new_status"] == "resolved"
    assert len(calls["insert"]) == 1
    assert len(calls["audit"]) == 1


def test_transition_case_status_invalid_transition(monkeypatch):
    client = _build_client()

    monkeypatch.setattr(
        workflow_routes,
        "get_row",
        lambda table, pk_col, pk_val: {"case_id": 101, "status": "closed", "metadata_json": {}},
    )

    res = client.post(
        "/api/wbom/workflow/cases/101/status",
        json={"new_status": "in_progress", "changed_by": "ops-admin"},
    )
    assert res.status_code == 400


def test_case_escalation_action_escalate_success(monkeypatch):
    client = _build_client()
    calls = {"update": [], "insert": [], "audit": []}

    case_row = {
        "case_id": 202,
        "case_type": "complaint",
        "severity": "high",
        "status": "open",
        "metadata_json": {"escalation_level": 0},
    }

    def fake_get_row(table, pk_col, pk_val):
        if table == "wbom_cases" and pk_col == "case_id" and pk_val == 202:
            return case_row
        return None

    def fake_execute_query(sql, params=()):
        if "FROM wbom_escalation_rules" in sql:
            return [{
                "escalation_rule_id": 11,
                "escalation_level": 1,
                "target_role": "supervisor",
                "target_user": "ops-supervisor",
                "notify_channel": "whatsapp",
            }]
        return []

    def fake_update_row(table, pk_col, pk_val, data):
        calls["update"].append((table, data))
        case_row.update(data)
        return case_row

    def fake_insert_row(table, data):
        calls["insert"].append((table, data))
        return {"event_id": 2}

    def fake_audit_log(*args, **kwargs):
        calls["audit"].append((args, kwargs))

    monkeypatch.setattr(workflow_routes, "get_row", fake_get_row)
    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)
    monkeypatch.setattr(workflow_routes, "update_row", fake_update_row)
    monkeypatch.setattr(workflow_routes, "insert_row", fake_insert_row)
    monkeypatch.setattr(workflow_routes, "audit_log", fake_audit_log)

    res = client.post(
        "/api/wbom/workflow/cases/202/escalate",
        json={"action": "escalate", "actor": "ops-admin", "note": "Need supervisor review"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["to_level"] == 1
    assert body["target_role"] == "supervisor"
    assert len(calls["insert"]) == 1


def test_case_escalation_action_snooze(monkeypatch):
    client = _build_client()

    case_row = {
        "case_id": 303,
        "case_type": "complaint",
        "severity": "medium",
        "status": "open",
        "metadata_json": {},
    }

    def fake_get_row(table, pk_col, pk_val):
        if table == "wbom_cases" and pk_col == "case_id" and pk_val == 303:
            return case_row
        return None

    def fake_execute_query(sql, params=()):
        return []

    def fake_update_row(table, pk_col, pk_val, data):
        case_row.update(data)
        return case_row

    monkeypatch.setattr(workflow_routes, "get_row", fake_get_row)
    monkeypatch.setattr(workflow_routes, "execute_query", fake_execute_query)
    monkeypatch.setattr(workflow_routes, "update_row", fake_update_row)
    monkeypatch.setattr(workflow_routes, "insert_row", lambda *args, **kwargs: {"event_id": 3})
    monkeypatch.setattr(workflow_routes, "audit_log", lambda *args, **kwargs: None)

    res = client.post(
        "/api/wbom/workflow/cases/303/escalate",
        json={"action": "snooze", "actor": "ops-admin", "snooze_minutes": 45},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["action"] == "snooze"
