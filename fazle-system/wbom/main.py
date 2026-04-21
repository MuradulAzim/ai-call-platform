# ============================================================
# WBOM — WhatsApp Business Operations Manager
# FastAPI service entry-point  |  Port 9900
# ============================================================
import logging, os, uuid, json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from database import ensure_wbom_tables
from config import settings as _cfg

# ---- routers ------------------------------------------------
from routes.contacts import router as contacts_router
from routes.employees import router as employees_router
from routes.programs import router as programs_router
from routes.transactions import router as transactions_router
from routes.billing import router as billing_router
from routes.salary import router as salary_router
from routes.messages import router as messages_router
from routes.templates import router as templates_router
from routes.search import router as search_router
from routes.subagent import router as subagent_router
from routes.reports import router as reports_router
from routes.attendance import router as attendance_router
from routes.admin import router as admin_router
from routes.self_service import router as self_service_router
from routes.payment import router as payment_router
from routes.job_applications import router as job_applications_router
from routes.clients import router as clients_router
from routes.audit import router as audit_router
from routes.schema import router as schema_router
from routes.master_routes import router as master_router
from routes.csv_import import router as csv_import_router
from routes.workflow import router as workflow_router
from routes.payroll import router as payroll_router
from routes.dashboard import router as dashboard_router
from routes.recruitment import router as recruitment_router
from routes.complaints import router as complaints_router

# ---- logging ------------------------------------------------
from structured_log import setup_structured_logging
setup_structured_logging("wbom")
log = logging.getLogger("wbom")

# ── Paths that skip internal auth (health checks) ────────────
_PUBLIC_PATHS = frozenset(["/health", "/ready", "/version", "/", "/metrics"])


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid X-INTERNAL-KEY header.
    Health-check and root paths are exempt so Docker/Prometheus keep working."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        expected = _cfg.internal_key
        if expected:
            provided = request.headers.get("x-internal-key", "")
            if provided != expected:
                log.warning("Rejected request %s %s — bad/missing X-INTERNAL-KEY",
                            request.method, request.url.path)
                return Response(
                    content='{"detail":"Forbidden — invalid internal key"}',
                    status_code=403,
                    media_type="application/json",
                )
        return await call_next(request)


# ---- lifespan -----------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("WBOM starting — ensuring database tables …")
    ensure_wbom_tables()
    log.info("WBOM ready")
    yield
    log.info("WBOM shutting down")


# ---- app ----------------------------------------------------
app = FastAPI(
    title="WBOM — WhatsApp Business Operations Manager",
    version="1.6.0",
    description="Full CRUD API for employees, transactions, clients, job applications, audit logs, and payments. "
                "All list endpoints return a standard envelope: {success, data, meta, schema, version}.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal service auth (zero-trust)
app.add_middleware(InternalAuthMiddleware)

# Prometheus
Instrumentator().instrument(app).expose(app)


# X-Request-ID tracing
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handlers (S6-02) ────────────────────────

def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    log.warning(
        "HTTP %s on %s %s — %s",
        exc.status_code, request.method, request.url.path, exc.detail,
        extra={"request_id": _req_id(request), "action": "http_error"},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": str(exc.detail),
            "request_id": _req_id(request),
        },
        headers={"X-Request-ID": _req_id(request)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = "; ".join(
        f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
        for e in errors[:5]
    )
    log.warning(
        "Validation error on %s %s — %s",
        request.method, request.url.path, messages,
        extra={"request_id": _req_id(request), "action": "validation_error"},
    )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation failed",
            "detail": messages,
            "request_id": _req_id(request),
        },
        headers={"X-Request-ID": _req_id(request)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    log.exception(
        "Unhandled exception [error_id=%s] on %s %s",
        error_id, request.method, request.url.path,
        extra={"request_id": _req_id(request), "action": "unhandled_exception"},
    )
    # Never expose stack traces to clients in production
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "error_id": error_id,
            "request_id": _req_id(request),
        },
        headers={"X-Request-ID": _req_id(request)},
    )


# ---- mount routers ------------------------------------------
app.include_router(contacts_router, prefix="/api/wbom")
app.include_router(employees_router, prefix="/api/wbom")
app.include_router(programs_router, prefix="/api/wbom")
app.include_router(transactions_router, prefix="/api/wbom")
app.include_router(billing_router, prefix="/api/wbom")
app.include_router(salary_router, prefix="/api/wbom")
app.include_router(messages_router, prefix="/api/wbom")
app.include_router(templates_router, prefix="/api/wbom")
app.include_router(search_router, prefix="/api/wbom")
app.include_router(subagent_router, prefix="/api")
app.include_router(reports_router, prefix="/api/wbom")
app.include_router(attendance_router, prefix="/api/wbom")
app.include_router(admin_router, prefix="/api/wbom")
app.include_router(self_service_router, prefix="/api/wbom")
app.include_router(payment_router, prefix="/api/wbom")
app.include_router(job_applications_router, prefix="/api/wbom")
app.include_router(clients_router, prefix="/api/wbom")
app.include_router(audit_router, prefix="/api/wbom")
app.include_router(schema_router, prefix="/api/wbom")
app.include_router(master_router, prefix="/api/wbom")
app.include_router(csv_import_router, prefix="/api/wbom")
app.include_router(workflow_router, prefix="/api/wbom")
app.include_router(payroll_router, prefix="/api/wbom")
app.include_router(dashboard_router, prefix="/api/wbom")
app.include_router(recruitment_router, prefix="/api/wbom")
app.include_router(complaints_router, prefix="/api/wbom")


# ---- health --------------------------------------------------
_WBOM_VERSION = "wbom-v1.6.0"
_BUILD_DATE = "2026-04-21"


def _check_db() -> tuple[bool, str]:
    """Return (ok, message) for DB connectivity."""
    try:
        from database import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True, "connected"
    except Exception as exc:
        return False, str(exc)[:120]


@app.get("/health")
def health():
    """Liveness probe — always returns 200 if the process is alive.
    DB check is non-blocking: unhealthy DB is surfaced but does not
    make this endpoint return non-200 (so the container is not restarted
    just because Postgres is temporarily unavailable).
    """
    db_ok, db_msg = _check_db()
    from datetime import datetime, timezone
    return {
        "status": "ok",
        "db": db_msg,
        "db_ok": db_ok,
        "version": _WBOM_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
        "service": "wbom",
    }


@app.get("/ready")
def ready():
    """Readiness probe — returns 503 if DB is not reachable.
    Used by load balancers / K8s readiness probes.
    """
    from datetime import datetime, timezone
    db_ok, db_msg = _check_db()
    status_code = 200 if db_ok else 503
    return Response(
        content=__import__("json").dumps({
            "ready": db_ok,
            "db": db_msg,
            "version": _WBOM_VERSION,
            "time": datetime.now(timezone.utc).isoformat(),
        }),
        status_code=status_code,
        media_type="application/json",
    )


@app.get("/version")
def version():
    """Version metadata — safe for public consumption."""
    return {
        "version": _WBOM_VERSION,
        "build_date": _BUILD_DATE,
        "service": "wbom",
        "api_prefix": "/api/wbom",
    }


@app.get("/")
def root():
    return {"service": "WBOM", "version": _WBOM_VERSION}


# ---- run -----------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("WBOM_PORT", "9900")),
        reload=False,
    )
