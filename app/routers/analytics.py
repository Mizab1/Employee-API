from typing import Optional
from fastapi import APIRouter, Query

from app.schemas.analytics import (
    DepartmentSummary,
    EmployeeMonthly,
    Leaderboard,
    Trend,
)
from app.services.analytics_service import (
    get_department_summary,
    get_department_trend,
    get_employee_monthly,
    get_late_leaderboard,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/employees/{emp_code}/monthly", response_model=EmployeeMonthly)
def get_employee_monthly_analytics(
    emp_code: str,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
):
    return get_employee_monthly(emp_code=emp_code, month=month)


@router.get("/departments/summary", response_model=DepartmentSummary)
def get_department_summary_analytics(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    department: Optional[str] = None,
):
    return get_department_summary(month=month, department=department)


@router.get("/leaderboard/late", response_model=Leaderboard)
def get_late_leaderboard_analytics(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None,
):
    return get_late_leaderboard(month=month, limit=limit, department=department)


@router.get("/departments/{department}/trend", response_model=Trend)
def get_department_trend_analytics(
    department: str,
    from_date: str = Query(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    return get_department_trend(department=department, from_date=from_date, to_date=to_date)
