from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.schemas.analytics import ExplainResponse
from app.services.analytics_service import explain_query

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ENDPOINTS = {
    "attendance_list",
    "employee_monthly",
    "department_summary",
    "late_leaderboard",
    "department_trend",
}

@router.get("/explain/{endpoint}", response_model=ExplainResponse)
def get_explain(
    endpoint: str,
    emp_code: Optional[str] = None,
    month: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if endpoint not in VALID_ENDPOINTS:
        raise HTTPException(status_code=422, detail=f"Invalid endpoint for explain: {endpoint}")

    params = {
        "emp_code": emp_code,
        "month": month,
        "department": department,
        "limit": limit,
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "from": from_date,
        "to": to_date,
        "page": page,
        "page_size": page_size,
    }

    return explain_query(endpoint, params)
