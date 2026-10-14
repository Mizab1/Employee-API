from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.core.timezone import utc_dt_to_epoch_ms
from app.db.client import get_db
from app.schemas.employee import EmployeeCreate


def create_employee(body: EmployeeCreate):
    db = get_db()
    doc = body.model_dump()
    created_at = datetime.now(timezone.utc)
    doc["created_at"] = created_at

    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="emp_code already exists")

    doc.pop("_id", None)
    doc["created_at"] = utc_dt_to_epoch_ms(created_at)
    return doc


def list_employees(department: Optional[str] = None, page: int = 1, page_size: int = 20):
    db = get_db()
    q = {}
    if department:
        q["department"] = department

    total = db.employees.count_documents(q)
    skip = (page - 1) * page_size
    cursor = db.employees.find(q, {"_id": 0}).sort("emp_code", 1).skip(skip).limit(page_size)

    items = []
    for emp in cursor:
        emp["created_at"] = utc_dt_to_epoch_ms(emp.get("created_at"))
        items.append(emp)

    return {"items": items, "total": total, "page": page, "page_size": page_size}
