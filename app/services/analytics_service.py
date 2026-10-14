from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from fastapi import HTTPException
from app.core.rules import count_working_days_in_month
from app.db.client import get_db

def get_month_date_range(month_str: str):
    year, month = map(int, month_str.split("-"))
    start_date = f"{month_str}-01"
    if month == 12:
        end_date = (date(year + 1, 1, 1) - timedelta(days=1)).isoformat()
    else:
        end_date = (date(year, month + 1, 1) - timedelta(days=1)).isoformat()
    return start_date, end_date

def build_employee_monthly_pipeline(emp_code: str, start_date: str, end_date: str):
    return [
        {
            "$match": {
                "emp_code": emp_code,
                "date": {"$gte": start_date, "$lte": end_date},
            }
        },
        {
            "$project": {
                "date": 1,
                "status": 1,
                "late_minutes": 1,
                "overtime_minutes": 1,
                "half_day": 1,
                "day_of_week": {
                    "$isoDayOfWeek": {
                        "$dateFromString": {"dateString": "$date"}
                    }
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "present_days": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$in": ["$status", ["PRESENT", "WFH", "ON_DUTY"]]},
                                    {"$lte": ["$day_of_week", 5]},
                                ]
                            },
                            {"$cond": ["$half_day", 0.5, 1.0]},
                            0.0,
                        ]
                    }
                },
                "leave_days": {
                    "$sum": {"$cond": [{"$eq": ["$status", "LEAVE"]}, 1, 0]}
                },
                "late_count": {
                    "$sum": {"$cond": [{"$gt": ["$late_minutes", 0]}, 1, 0]}
                },
                "total_late_minutes": {"$sum": "$late_minutes"},
                "total_overtime_minutes": {"$sum": "$overtime_minutes"},
            }
        },
    ]


def get_employee_monthly(emp_code: str, month: str):
    db = get_db()
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    start_date, end_date = get_month_date_range(month)
    working_days = count_working_days_in_month(month, emp["joined_on"])

    pipeline = build_employee_monthly_pipeline(emp_code, start_date, end_date)
    cursor = list(db.attendance_logs.aggregate(pipeline))

    if cursor:
        res = cursor[0]
        present_days = float(res.get("present_days", 0.0))
        leave_days = int(res.get("leave_days", 0))
        late_count = int(res.get("late_count", 0))
        total_late_minutes = int(res.get("total_late_minutes", 0))
        total_overtime_minutes = int(res.get("total_overtime_minutes", 0))
    else:
        present_days = 0.0
        leave_days = 0
        late_count = 0
        total_late_minutes = 0
        total_overtime_minutes = 0

    if working_days > 0:
        pct_dec = (Decimal(str(present_days)) / Decimal(working_days)) * Decimal(100)
        attendance_pct = float(pct_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    else:
        attendance_pct = None

    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": leave_days,
        "late_count": late_count,
        "total_late_minutes": total_late_minutes,
        "total_overtime_minutes": total_overtime_minutes,
        "attendance_pct": attendance_pct,
    }


def build_department_summary_pipeline(start_date: str, end_date: str, department: Optional[str] = None):
    emp_match: dict[str, Any] = {"joined_on": {"$lte": end_date}}
    if department:
        emp_match["department"] = department

    return [
        {"$match": emp_match},
        {
            "$group": {
                "_id": "$department",
                "headcount": {"$sum": 1},
                "emp_codes": {"$push": "$emp_code"},
            }
        },
        {
            "$lookup": {
                "from": "attendance_logs",
                "let": {"dept_emps": "$emp_codes"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$in": ["$emp_code", "$$dept_emps"]},
                                    {"$gte": ["$date", start_date]},
                                    {"$lte": ["$date", end_date]},
                                ]
                            }
                        }
                    },
                    {
                        "$project": {
                            "status": 1,
                            "work_hours": 1,
                            "late_minutes": 1,
                            "half_day": 1,
                            "day_of_week": {
                                "$isoDayOfWeek": {
                                    "$dateFromString": {"dateString": "$date"}
                                }
                            },
                        }
                    },
                ],
                "as": "logs",
            }
        },
        {
            "$project": {
                "department": "$_id",
                "headcount": 1,
                "present_days": {
                    "$sum": {
                        "$map": {
                            "input": "$logs",
                            "as": "l",
                            "in": {
                                "$cond": [
                                    {
                                        "$and": [
                                            {
                                                "$in": [
                                                    "$$l.status",
                                                    ["PRESENT", "WFH", "ON_DUTY"],
                                                ]
                                            },
                                            {"$lte": ["$$l.day_of_week", 5]},
                                        ]
                                    },
                                    {"$cond": ["$$l.half_day", 0.5, 1.0]},
                                    0.0,
                                ]
                            },
                        }
                    }
                },
                "late_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "l",
                            "cond": {"$gt": ["$$l.late_minutes", 0]},
                        }
                    }
                },
                "total_late_minutes": {"$sum": "$logs.late_minutes"},
                "leave_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "l",
                            "cond": {"$eq": ["$$l.status", "LEAVE"]},
                        }
                    }
                },
                "on_duty_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "l",
                            "cond": {"$eq": ["$$l.status", "ON_DUTY"]},
                        }
                    }
                },
                "valid_work_hours": {
                    "$filter": {
                        "input": "$logs",
                        "as": "l",
                        "cond": {
                            "$and": [
                                {
                                    "$in": [
                                        "$$l.status",
                                        ["PRESENT", "WFH", "ON_DUTY"],
                                    ]
                                },
                                {"$ne": ["$$l.work_hours", None]},
                            ]
                        },
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "department": 1,
                "headcount": 1,
                "present_days": 1,
                "late_count": 1,
                "total_late_minutes": 1,
                "leave_count": 1,
                "on_duty_count": 1,
                "avg_work_hours": {
                    "$cond": [
                        {"$gt": [{"$size": "$valid_work_hours"}, 0]},
                        {"$avg": "$valid_work_hours.work_hours"},
                        None,
                    ]
                },
            }
        },
        {"$sort": {"department": 1}},
    ]


def get_department_summary(month: str, department: Optional[str] = None):
    db = get_db()
    start_date, end_date = get_month_date_range(month)
    pipeline = build_department_summary_pipeline(start_date, end_date, department)
    results = list(db.employees.aggregate(pipeline))

    items = []
    for row in results:
        avg_wh = row.get("avg_work_hours")
        if avg_wh is not None:
            avg_wh = float(Decimal(str(avg_wh)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        items.append(
            {
                "department": row["department"],
                "headcount": row["headcount"],
                "present_days": float(row.get("present_days", 0.0)),
                "avg_work_hours": avg_wh,
                "late_count": row.get("late_count", 0),
                "total_late_minutes": row.get("total_late_minutes", 0),
                "leave_count": row.get("leave_count", 0),
                "on_duty_count": row.get("on_duty_count", 0),
            }
        )

    return {"month": month, "items": items}

def build_late_leaderboard_pipeline(start_date: str, end_date: str, limit: int = 10, department: Optional[str] = None):
    pipeline: list[dict] = [
        {
            "$match": {
                "date": {"$gte": start_date, "$lte": end_date},
                "late_minutes": {"$gt": 0},
            }
        },
        {
            "$group": {
                "_id": "$emp_code",
                "total_late_minutes": {"$sum": "$late_minutes"},
                "late_count": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": "employees",
                "localField": "_id",
                "foreignField": "emp_code",
                "as": "emp",
            }
        },
        {"$unwind": "$emp"},
    ]

    if department:
        pipeline.append({"$match": {"emp.department": department}})

    pipeline.extend(
        [
            {
                "$setWindowFields": {
                    "sortBy": {"total_late_minutes": -1},
                    "output": {"rank": {"$rank": {}}},
                }
            },
            {"$match": {"rank": {"$lte": limit}}},
            {
                "$project": {
                    "_id": 0,
                    "rank": 1,
                    "emp_code": "$_id",
                    "name": "$emp.name",
                    "department": "$emp.department",
                    "total_late_minutes": 1,
                    "late_count": 1,
                }
            },
            {"$sort": {"total_late_minutes": -1, "emp_code": 1}},
        ]
    )
    return pipeline

def get_late_leaderboard(month: str, limit: int = 10, department: Optional[str] = None):
    db = get_db()
    start_date, end_date = get_month_date_range(month)
    pipeline = build_late_leaderboard_pipeline(start_date, end_date, limit, department)
    items = list(db.attendance_logs.aggregate(pipeline))
    return {"month": month, "items": items}

def build_department_trend_pipeline(department: str, from_date: str, to_date: str):
    from_d = date.fromisoformat(from_date)
    to_d = date.fromisoformat(to_date)
    num_days = (to_d - from_d).days + 1

    return [
        {"$match": {"department": department}},
        {
            "$group": {
                "_id": "$department",
                "all_emps": {"$push": {"emp_code": "$emp_code", "joined_on": "$joined_on"}},
            }
        },
        {
            "$project": {
                "day_offset": {"$range": [0, num_days]},
                "all_emps": 1,
            }
        },
        {"$unwind": "$day_offset"},
        {
            "$project": {
                "date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": {
                            "$dateAdd": {
                                "startDate": {
                                    "$dateFromString": {"dateString": from_date}
                                },
                                "unit": "day",
                                "amount": "$day_offset",
                            }
                        },
                    }
                },
                "all_emps": 1,
            }
        },
        {
            "$project": {
                "date": 1,
                "is_working_day": {
                    "$lte": [
                        {
                            "$isoDayOfWeek": {
                                "$dateFromString": {"dateString": "$date"}
                            }
                        },
                        5,
                    ]
                },
                "dept_emps": {
                    "$filter": {
                        "input": "$all_emps",
                        "as": "e",
                        "cond": {"$lte": ["$$e.joined_on", "$date"]},
                    }
                },
            }
        },
        {
            "$project": {
                "date": 1,
                "is_working_day": 1,
                "headcount": {"$size": "$dept_emps"},
                "emp_codes": "$dept_emps.emp_code",
            }
        },
        {
            "$lookup": {
                "from": "attendance_logs",
                "let": {"curr_date": "$date", "codes": "$emp_codes"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$date", "$$curr_date"]},
                                    {"$in": ["$emp_code", "$$codes"]},
                                ]
                            }
                        }
                    }
                ],
                "as": "logs",
            }
        },
        {
            "$project": {
                "date": 1,
                "is_working_day": 1,
                "headcount": 1,
                "present_count": {
                    "$sum": {
                        "$map": {
                            "input": "$logs",
                            "as": "l",
                            "in": {
                                "$cond": [
                                    {
                                        "$in": [
                                            "$$l.status",
                                            ["PRESENT", "WFH", "ON_DUTY"],
                                        ]
                                    },
                                    {"$cond": ["$$l.half_day", 0.5, 1.0]},
                                    0.0,
                                ]
                            },
                        }
                    }
                },
                "late_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "l",
                            "cond": {"$gt": ["$$l.late_minutes", 0]},
                        }
                    }
                },
            }
        },
        {
            "$project": {
                "date": 1,
                "is_working_day": 1,
                "headcount": 1,
                "present_count": 1,
                "late_count": 1,
                "attendance_rate": {
                    "$cond": [
                        {
                            "$and": [
                                "$is_working_day",
                                {"$gt": ["$headcount", 0]},
                            ]
                        },
                        {"$divide": ["$present_count", "$headcount"]},
                        None,
                    ]
                },
            }
        },
        {
            "$setWindowFields": {
                "sortBy": {"date": 1},
                "output": {
                    "moving_avg_7d": {
                        "$avg": "$attendance_rate",
                        "window": {"documents": [-6, 0]},
                    }
                },
            }
        },
        {"$sort": {"date": 1}},
    ]

def get_department_trend(department: str, from_date: str, to_date: str):
    db = get_db()
    # 404 if department has 0 employees
    if not db.employees.find_one({"department": department}):
        raise HTTPException(status_code=404, detail="Department not found")

    from_d = date.fromisoformat(from_date)
    to_d = date.fromisoformat(to_date)
    if to_d < from_d:
        raise HTTPException(status_code=422, detail="to date must not be earlier than from date")
    if (to_d - from_d).days > 92:
        raise HTTPException(status_code=422, detail="Date range must not exceed 92 days")

    pipeline = build_department_trend_pipeline(department, from_date, to_date)
    raw_items = list(db.employees.aggregate(pipeline))

    items = []
    for row in raw_items:
        rate = row.get("attendance_rate")
        if rate is not None:
            rate = float(Decimal(str(rate)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

        m_avg = row.get("moving_avg_7d")
        if m_avg is not None:
            m_avg = float(Decimal(str(m_avg)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

        items.append(
            {
                "date": row["date"],
                "is_working_day": row["is_working_day"],
                "headcount": row["headcount"],
                "present_count": float(row["present_count"]),
                "late_count": row["late_count"],
                "attendance_rate": rate,
                "moving_avg_7d": m_avg,
            }
        )

    return {"department": department, "items": items}

def explain_query(endpoint: str, params: dict[str, Any]):
    db = get_db()

    if endpoint == "attendance_list":
        q: dict[str, Any] = {}
        if params.get("emp_code"):
            q["emp_code"] = params["emp_code"]
        if params.get("date_from") or params.get("date_to"):
            q["date"] = {}
            if params.get("date_from"):
                q["date"]["$gte"] = params["date_from"]
            if params.get("date_to"):
                q["date"]["$lte"] = params["date_to"]
        if params.get("status"):
            q["status"] = params["status"]

        page = params.get("page", 1)
        page_size = params.get("page_size", 20)
        skip = (page - 1) * page_size

        cursor = (
            db.attendance_logs.find(q)
            .sort([("date", -1), ("emp_code", 1)])
            .skip(skip)
            .limit(page_size)
        )
        explain_res = cursor.explain()
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": explain_res,
        }

    elif endpoint == "employee_monthly":
        emp_code = params.get("emp_code")
        month = params.get("month")
        if not emp_code or not month:
            raise HTTPException(
                status_code=422, detail="emp_code and month are required"
            )
        start_date, end_date = get_month_date_range(month)
        pipeline = build_employee_monthly_pipeline(emp_code, start_date, end_date)
        explain_res = db.command(
            "explain",
            {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": explain_res,
        }

    elif endpoint == "department_summary":
        month = params.get("month")
        if not month:
            raise HTTPException(status_code=422, detail="month is required")
        start_date, end_date = get_month_date_range(month)
        dept = params.get("department")
        pipeline = build_department_summary_pipeline(start_date, end_date, dept)
        explain_res = db.command(
            "explain",
            {"aggregate": "employees", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "employees",
            "explain": explain_res,
        }

    elif endpoint == "late_leaderboard":
        month = params.get("month")
        if not month:
            raise HTTPException(status_code=422, detail="month is required")
        start_date, end_date = get_month_date_range(month)
        limit = params.get("limit", 10)
        dept = params.get("department")
        pipeline = build_late_leaderboard_pipeline(start_date, end_date, limit, dept)
        explain_res = db.command(
            "explain",
            {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": explain_res,
        }

    elif endpoint == "department_trend":
        dept = params.get("department")
        from_date = params.get("from")
        to_date = params.get("to")
        if not dept or not from_date or not to_date:
            raise HTTPException(
                status_code=422, detail="department, from, and to are required"
            )
        pipeline = build_department_trend_pipeline(dept, from_date, to_date)
        explain_res = db.command(
            "explain",
            {"aggregate": "employees", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "employees",
            "explain": explain_res,
        }

    else:
        raise HTTPException(status_code=422, detail=f"Unknown endpoint: {endpoint}")
