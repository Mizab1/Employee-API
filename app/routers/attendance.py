from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.attendance import (
    AttendancePage,
    AttendanceRecord,
    PunchInRequest,
    PunchOutRequest,
    RegularizeRequest,
)
from app.services.attendance_service import (
    list_attendance,
    punch_in,
    punch_out,
    regularize_attendance,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])

@router.post("/punch-in", status_code=201, response_model=AttendanceRecord)
def post_punch_in(body: PunchInRequest):
    return punch_in(body)

@router.post("/punch-out", status_code=200, response_model=AttendanceRecord)
def post_punch_out(body: PunchOutRequest):
    return punch_out(body)

@router.get("", response_model=AttendancePage)
def get_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return list_attendance(
        emp_code=emp_code,
        date_from=date_from,
        date_to=date_to,
        status=status,
        page=page,
        page_size=page_size,
    )

@router.patch("/{emp_code}/{date}", response_model=AttendanceRecord)
def patch_regularize(emp_code: str, date: str, body: RegularizeRequest):
    return regularize_attendance(emp_code, date, body)
