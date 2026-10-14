from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.employee import EmployeeCreate, EmployeePage, EmployeeResponse
from app.services.employee_service import create_employee, list_employees

router = APIRouter(prefix="/employees", tags=["employees"])

@router.post("", status_code=201, response_model=EmployeeResponse)
def post_employee(body: EmployeeCreate):
    return create_employee(body)

@router.get("", response_model=EmployeePage)
def get_employees(
    department: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return list_employees(department=department, page=page, page_size=page_size)
