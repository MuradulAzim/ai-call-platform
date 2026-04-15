# ============================================================
# WBOM — WhatsApp Business Operations Manager
# FastAPI service entry-point  |  Port 9900
# ============================================================
import logging, os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from database import ensure_wbom_tables

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

# ---- logging ------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("wbom")


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
    version="1.0.0",
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

# Prometheus
Instrumentator().instrument(app).expose(app)

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


# ---- health --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "healthy", "service": "wbom"}


@app.get("/")
def root():
    return {"service": "WBOM", "version": "1.0.0"}


# ---- run -----------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("WBOM_PORT", "9900")),
        reload=False,
    )
