# ============================================================
# WBOM — Dispatcher Tests  (Sprint-5 S5-03)
# Tests: dispatch routing logic, duplicate guard, keyword set
# All DB + service calls are monkeypatched — no real DB required.
# ============================================================
import os
import sys
import types
from unittest.mock import patch, MagicMock

# ── Bootstrap WBOM package ───────────────────────────────────
WBOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WBOM_DIR not in sys.path:
    sys.path.insert(0, WBOM_DIR)

# ── psycopg2 stub ─────────────────────────────────────────────
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    extras_stub = types.ModuleType("psycopg2.extras")
    pool_stub = types.ModuleType("psycopg2.pool")

    class _FakeConn:
        def cursor(self, **kw): return _FakeCursor()
        def commit(self): pass
        def rollback(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class _FakeCursor:
        def execute(self, *a, **kw): pass
        def fetchall(self): return []
        def fetchone(self): return None
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class _ThreadedPool:
        def __init__(self, *a, **kw): pass
        def getconn(self): return _FakeConn()
        def putconn(self, c): pass

    pool_stub.ThreadedConnectionPool = _ThreadedPool
    extras_stub.RealDictCursor = type("RealDictCursor", (), {})
    psycopg2_stub.extras = extras_stub
    psycopg2_stub.pool = pool_stub
    sys.modules["psycopg2"] = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub
    sys.modules["psycopg2.pool"] = pool_stub

# ── prometheus_client stub ────────────────────────────────────
if "prometheus_client" not in sys.modules:
    prom = types.ModuleType("prometheus_client")
    prom.Counter = lambda *a, **kw: MagicMock()
    prom.Histogram = lambda *a, **kw: MagicMock()
    prom.Gauge = lambda *a, **kw: MagicMock()
    sys.modules["prometheus_client"] = prom

# ── httpx stub ───────────────────────────────────────────────
if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")
    sys.modules["httpx"] = httpx_stub

import pytest  # noqa: E402

# ── Import routing helpers directly ──────────────────────────
from routes.messages import _is_recruitment_message, _message_already_processed  # noqa: E402


# ── _is_recruitment_message ───────────────────────────────────

class TestIsRecruitmentMessage:
    def test_english_job_keyword(self):
        assert _is_recruitment_message("I am looking for a job") is True

    def test_bangla_chakri(self):
        assert _is_recruitment_message("আমি চাকরি খুঁজছি") is True

    def test_bangla_kaj(self):
        assert _is_recruitment_message("কাজ করতে চাই") is True

    def test_join_keyword(self):
        assert _is_recruitment_message("I want to join your team") is True

    def test_work_keyword(self):
        assert _is_recruitment_message("need work") is True

    def test_escort_order_not_recruitment(self):
        assert _is_recruitment_message(
            "MV Padma, capacity 1200 MT, destination Chittagong, mob 01711000000"
        ) is False

    def test_payment_not_recruitment(self):
        assert _is_recruitment_message("ID: 01711000000 (B) 5000/-") is False

    def test_empty_string(self):
        assert _is_recruitment_message("") is False

    def test_case_insensitive(self):
        assert _is_recruitment_message("JOB OFFER") is True


# ── _message_already_processed ────────────────────────────────

class TestMessageAlreadyProcessed:
    def test_none_id_returns_false(self):
        # Should not hit DB
        assert _message_already_processed(None) is False

    def test_empty_id_returns_false(self):
        assert _message_already_processed("") is False

    def test_existing_message_returns_true(self):
        with patch("routes.messages.execute_query", return_value=[{"message_id": 1}]):
            assert _message_already_processed("WA-123") is True

    def test_new_message_returns_false(self):
        with patch("routes.messages.execute_query", return_value=[]):
            assert _message_already_processed("WA-999") is False


# ── Dispatch routing logic ────────────────────────────────────

class TestDispatchRouting:
    """Test that the dispatch endpoint calls the correct downstream service."""

    def _make_request(self, message_body: str, wa_id: str = None):
        req = MagicMock()
        req.sender_number = "+8801700000000"
        req.message_body = message_body
        req.whatsapp_msg_id = wa_id
        return req

    def test_recruitment_message_routes_to_intake(self):
        req = self._make_request("আমি চাকরি খুঁজছি", "WA-001")
        mock_intake_result = {
            "message_id": 0, "reply": "স্বাগতম! আপনার পুরো নাম কি?",
            "funnel_stage": "collecting",
        }
        with patch("routes.messages._message_already_processed", return_value=False), \
             patch("services.recruitment.intake_message", return_value=mock_intake_result) as mock_intake, \
             patch("routes.messages.execute_query", return_value=[]):
            from routes.messages import dispatch_message
            result = dispatch_message(req)
            mock_intake.assert_called_once_with(
                phone=req.sender_number, message=req.message_body
            )
            assert result["classification"] == "recruitment"

    def test_non_recruitment_routes_to_processor(self):
        req = self._make_request("MV Padma 1200MT Chittagong 01711000000", "WA-002")
        mock_process_result = {
            "message_id": 5, "classification": "escort_order",
            "confidence": 0.9, "is_multi_lighter": False,
            "extracted_data": {}, "suggested_template": None,
            "draft_reply": "", "requires_admin_input": False,
            "missing_fields": [], "unfilled_fields": [],
            "confidence_scores": {},
        }
        with patch("routes.messages._message_already_processed", return_value=False), \
             patch("routes.messages.process_incoming_message",
                   return_value=mock_process_result) as mock_proc:
            from routes.messages import dispatch_message
            result = dispatch_message(req)
            mock_proc.assert_called_once()
            assert result["classification"] == "escort_order"

    def test_duplicate_message_raises_409(self):
        from fastapi import HTTPException
        req = self._make_request("some message", "WA-DUPLICATE")
        with patch("routes.messages._message_already_processed", return_value=True):
            from routes.messages import dispatch_message
            with pytest.raises(HTTPException) as exc_info:
                dispatch_message(req)
            assert exc_info.value.status_code == 409

    def test_dispatch_logs_route_taken(self, caplog):
        import logging
        req = self._make_request("I want a job", "WA-003")
        mock_result = {
            "message_id": 0, "reply": "Name?", "funnel_stage": "collecting",
        }
        with patch("routes.messages._message_already_processed", return_value=False), \
             patch("services.recruitment.intake_message", return_value=mock_result), \
             patch("routes.messages.execute_query", return_value=[]), \
             caplog.at_level(logging.INFO, logger="wbom.messages"):
            from routes.messages import dispatch_message
            dispatch_message(req)
            assert "recruitment" in caplog.text.lower()
