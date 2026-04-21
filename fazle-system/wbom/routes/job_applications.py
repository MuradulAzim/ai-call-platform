# ============================================================
# WBOM — Job Applications Routes  [DEPRECATED — Sprint-5 S5-04]
#
# This module is a historical read-only archive.
# All new candidate management uses /api/wbom/recruitment/candidates
# backed by wbom_candidates (migration 021 + 025).
#
# POST / PUT / DELETE are disabled with HTTP 410 Gone.
# GET endpoints remain for historical access.
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import get_row, list_rows, count_rows, audit_log
from models import JobApplicationCreate, JobApplicationUpdate, JobApplicationResponse

_GONE_DETAIL = (
    "This endpoint is deprecated. "
    "Use POST /api/wbom/recruitment/intake for new candidates. "
    "Historical data is available via GET /api/wbom/job-applications."
)

router = APIRouter(prefix="/job-applications", tags=["job_applications"])


@router.post("", status_code=410)
def create_application(data: JobApplicationCreate):
    raise HTTPException(
        status_code=410,
        detail=_GONE_DETAIL,
        headers={"X-WBOM-Migrate-To": "/api/wbom/recruitment/intake"},
    )


@router.get("")
def list_applications(
    status: Optional[str] = None,
    position: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Read-only historical list. Write endpoints removed in Sprint-5."""
    filters = {}
    if status:
        filters["status"] = status
    if position:
        filters["position"] = position
    rows = list_rows("wbom_job_applications", filters=filters, limit=limit, offset=offset)
    total = count_rows("wbom_job_applications", filters if filters else None)
    return {
        "items": rows,
        "total": total,
        "note": "DEPRECATED — historical data only. New candidates: GET /api/wbom/recruitment/candidates",
    }


@router.get("/{application_id}")
def get_application(application_id: int):
    """Read-only historical record. Write endpoints removed in Sprint-5."""
    row = get_row("wbom_job_applications", "application_id", application_id)
    if not row:
        raise HTTPException(404, "Application not found")
    return dict(row) | {
        "note": "DEPRECATED — historical data only. New candidates: GET /api/wbom/recruitment/candidates"
    }


@router.put("/{application_id}", status_code=410)
def update_application(application_id: int, data: JobApplicationUpdate):
    raise HTTPException(
        status_code=410,
        detail=_GONE_DETAIL,
        headers={"X-WBOM-Migrate-To": "/api/wbom/recruitment/candidates"},
    )


@router.delete("/{application_id}", status_code=410)
def delete_application(application_id: int):
    raise HTTPException(
        status_code=410,
        detail=_GONE_DETAIL,
        headers={"X-WBOM-Migrate-To": "/api/wbom/recruitment/candidates"},
    )
