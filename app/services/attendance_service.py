from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.rules import (
    compute_half_day,
    compute_late_minutes,
    compute_overtime,
    compute_work_hours,
    get_shift_bounds_for_date,
    resolve_shift_and_date,
)
from app.core.timezone import (
    epoch_ms_to_utc_dt,
    truncate_to_seconds,
    utc_dt_to_epoch_ms,
)
from app.db.client import get_db
from app.schemas.attendance import (
    PunchInRequest,
    PunchOutRequest,
    RegularizeRequest,
)


def format_attendance_doc(doc: dict):
    doc.pop("_id", None)
    doc.pop("id", None)

    # Convert punch instants
    doc["punch_in"] = utc_dt_to_epoch_ms(doc.get("punch_in"))
    doc["punch_out"] = utc_dt_to_epoch_ms(doc.get("punch_out"))

    # Legacy defaults
    doc["late_minutes"] = doc.get("late_minutes", 0)
    doc["overtime_minutes"] = doc.get("overtime_minutes", 0)
    doc["half_day"] = doc.get("half_day", False)

    # Format history entries
    formatted_history = []
    for entry in doc.get("history", []):
        entry_copy = dict(entry)
        entry_copy["at"] = utc_dt_to_epoch_ms(entry_copy.get("at"))

        formatted_changes = {}
        for field, change in entry_copy.get("changes", {}).items():
            ch = dict(change)
            from_val = ch.get("from")
            to_val = ch.get("to")

            if field in ("punch_in", "punch_out"):
                if isinstance(from_val, datetime):
                    from_val = utc_dt_to_epoch_ms(from_val)
                if isinstance(to_val, datetime):
                    to_val = utc_dt_to_epoch_ms(to_val)

            formatted_changes[field] = {"from": from_val, "to": to_val}

        entry_copy["changes"] = formatted_changes
        formatted_history.append(entry_copy)

    doc["history"] = formatted_history
    return doc

def punch_in(body: PunchInRequest):
    db = get_db()
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if body.punched_at is not None:
        raw_ms = body.punched_at
    else:
        raw_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # R1
    ts_ms = truncate_to_seconds(raw_ms)
    punch_in_dt = epoch_ms_to_utc_dt(ts_ms)

    att_date, shift_start_dt, _ = resolve_shift_and_date(
        punch_in_dt, emp["shift_start"], emp["shift_end"]
    )
    late_minutes = compute_late_minutes(punch_in_dt, shift_start_dt)

    doc = {
        "emp_code": body.emp_code,
        "date": att_date,
        "status": body.status.value,
        "punch_in": punch_in_dt,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": late_minutes,
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }

    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="already punched in for this date")

    return format_attendance_doc(doc)

def punch_out(body: PunchOutRequest):
    db = get_db()
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if body.punched_at is not None:
        raw_ms = body.punched_at
    else:
        raw_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    out_ms = truncate_to_seconds(raw_ms)
    punch_out_dt = epoch_ms_to_utc_dt(out_ms)

    # Find most recent record with punch_in <= punch_out_dt
    record = db.attendance_logs.find_one(
        {"emp_code": body.emp_code, "punch_in": {"$lte": punch_out_dt}},
        sort=[("punch_in", -1)],
    )
    if not record:
        raise HTTPException(status_code=404, detail="no punch-in found")

    if record.get("punch_out") is not None:
        raise HTTPException(status_code=409, detail="already punched out")

    punch_in_dt = record["punch_in"]
    if punch_out_dt <= punch_in_dt:
        raise HTTPException(
            status_code=422,
            detail="punch_out cannot be earlier than or equal to punch_in",
        )

    if (punch_out_dt - punch_in_dt).total_seconds() > 86400:
        raise HTTPException(
            status_code=422,
            detail="punch_out cannot be more than 24 hours after punch_in",
        )

    # R4, R5, R3
    work_hours = compute_work_hours(punch_in_dt, punch_out_dt)
    half_day = compute_half_day(work_hours)

    _, shift_end_dt = get_shift_bounds_for_date(
        record["date"], emp["shift_start"], emp["shift_end"]
    )
    overtime_minutes = compute_overtime(punch_out_dt, shift_end_dt)

    updated = db.attendance_logs.find_one_and_update(
        {"_id": record["_id"], "punch_out": None},
        {
            "$set": {
                "punch_out": punch_out_dt,
                "work_hours": work_hours,
                "overtime_minutes": overtime_minutes,
                "half_day": half_day,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=409, detail="already punched out")

    return format_attendance_doc(updated)

def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from must not be after date_to"
        )

    db = get_db()
    q: dict[str, Any] = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status

    total = db.attendance_logs.count_documents(q)
    skip = (page - 1) * page_size
    cursor = (
        db.attendance_logs.find(q)
        .sort([("date", -1), ("emp_code", 1)])
        .skip(skip)
        .limit(page_size)
    )

    items = [format_attendance_doc(doc) for doc in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def regularize_attendance(emp_code: str, date_str: str, body: RegularizeRequest):
    db = get_db()
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    record = db.attendance_logs.find_one({"emp_code": emp_code, "date": date_str})
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    target_status = body.status.value if body.status else record["status"]

    if body.punch_in is not None:
        target_punch_in = epoch_ms_to_utc_dt(body.punch_in)
    else:
        target_punch_in = record.get("punch_in")

    if body.punch_out is not None:
        target_punch_out = epoch_ms_to_utc_dt(body.punch_out)
    else:
        target_punch_out = record.get("punch_out")

    # Business rule validations
    if target_status in ("ABSENT", "LEAVE"):
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(
                status_code=422,
                detail="Supplying punch_in or punch_out when setting status ABSENT or LEAVE is invalid",
            )
        target_punch_in = None
        target_punch_out = None
    else:
        # Presence status requires punch_in
        if target_punch_in is None:
            raise HTTPException(
                status_code=422, detail="A presence status requires a punch_in"
            )

        # R1
        resolved_date, _, _ = resolve_shift_and_date(
            target_punch_in, emp["shift_start"], emp["shift_end"]
        )
        if resolved_date != date_str:
            raise HTTPException(
                status_code=422,
                detail=f"punch_in belongs to attendance date {resolved_date}, not {date_str}",
            )

        if target_punch_out is not None:
            if target_punch_out <= target_punch_in:
                raise HTTPException(
                    status_code=422,
                    detail="punch_out must be after punch_in",
                )
            if (target_punch_out - target_punch_in).total_seconds() > 86400:
                raise HTTPException(
                    status_code=422,
                    detail="punch_out cannot be more than 24 hours after punch_in",
                )

    # Recompute derived fields
    shift_start_dt, shift_end_dt = get_shift_bounds_for_date(
        date_str, emp["shift_start"], emp["shift_end"]
    )

    if target_status in ("ABSENT", "LEAVE"):
        target_work_hours = None
        target_late_minutes = 0
        target_overtime_minutes = 0
        target_half_day = False
    else:
        target_late_minutes = compute_late_minutes(target_punch_in, shift_start_dt)
        if target_punch_out is not None:
            target_work_hours = compute_work_hours(target_punch_in, target_punch_out)
            target_overtime_minutes = compute_overtime(target_punch_out, shift_end_dt)
            target_half_day = compute_half_day(target_work_hours)
        else:
            target_work_hours = None
            target_overtime_minutes = 0
            target_half_day = False

    # Detect fields that actually changed
    changes_bson = {}
    if record.get("status") != target_status:
        changes_bson["status"] = {"from": record.get("status"), "to": target_status}
    if record.get("punch_in") != target_punch_in:
        changes_bson["punch_in"] = {
            "from": record.get("punch_in"),
            "to": target_punch_in,
        }
    if record.get("punch_out") != target_punch_out:
        changes_bson["punch_out"] = {
            "from": record.get("punch_out"),
            "to": target_punch_out,
        }
    if record.get("work_hours") != target_work_hours:
        changes_bson["work_hours"] = {
            "from": record.get("work_hours"),
            "to": target_work_hours,
        }
    if record.get("late_minutes", 0) != target_late_minutes:
        changes_bson["late_minutes"] = {
            "from": record.get("late_minutes", 0),
            "to": target_late_minutes,
        }
    if record.get("overtime_minutes", 0) != target_overtime_minutes:
        changes_bson["overtime_minutes"] = {
            "from": record.get("overtime_minutes", 0),
            "to": target_overtime_minutes,
        }
    if bool(record.get("half_day", False)) != target_half_day:
        changes_bson["half_day"] = {
            "from": bool(record.get("half_day", False)),
            "to": target_half_day,
        }

    if not changes_bson:
        raise HTTPException(status_code=422, detail="Request changes nothing")

    history_entry = {
        "at": datetime.now(timezone.utc),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes_bson,
    }

    # Optimistic concurrency check: match current history array
    updated = db.attendance_logs.find_one_and_update(
        {"_id": record["_id"], "history": record.get("history", [])},
        {
            "$set": {
                "status": target_status,
                "punch_in": target_punch_in,
                "punch_out": target_punch_out,
                "work_hours": target_work_hours,
                "late_minutes": target_late_minutes,
                "overtime_minutes": target_overtime_minutes,
                "half_day": target_half_day,
            },
            "$push": {"history": history_entry},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        raise HTTPException(
            status_code=409, detail="Concurrent modification conflict"
        )

    return format_attendance_doc(updated)
