from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from app.db.client import get_db

def create_indexes(db: Database | None = None):
    if db is None:
        db = get_db()

    # 1. employees indexes
    db.employees.create_index(
        [("emp_code", ASCENDING)],
        unique=True,
        name="uniq_emp_code",
    )
    db.employees.create_index(
        [("department", ASCENDING), ("joined_on", ASCENDING)],
        name="idx_dept_joined",
    )

    # 2. attendance_logs indexes
    db.attendance_logs.create_index(
        [("emp_code", ASCENDING), ("date", ASCENDING)],
        unique=True,
        name="uniq_emp_date",
    )
    db.attendance_logs.create_index(
        [("date", DESCENDING), ("emp_code", ASCENDING)],
        name="idx_date_emp",
    )
    db.attendance_logs.create_index(
        [("emp_code", ASCENDING), ("punch_in", DESCENDING)],
        name="idx_emp_punch_in",
    )
    db.attendance_logs.create_index(
        [("emp_code", ASCENDING), ("date", ASCENDING), ("late_minutes", ASCENDING)],
        name="idx_emp_date_late",
    )
    db.attendance_logs.create_index(
        [("date", ASCENDING), ("late_minutes", ASCENDING)],
        name="idx_date_late",
    )
