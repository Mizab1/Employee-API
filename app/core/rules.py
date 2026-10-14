from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from app.core.timezone import IST, parse_hh_mm

def resolve_shift_and_date(punch_in_dt: datetime, shift_start_str: str, shift_end_str: str) -> Tuple[str, datetime, datetime]:
    """Rule R1."""
    punch_in_ist = punch_in_dt.astimezone(IST)
    start_time = parse_hh_mm(shift_start_str)
    end_time = parse_hh_mm(shift_end_str)

    is_overnight = end_time <= start_time

    if is_overnight and punch_in_ist.time() < end_time:
        att_date_obj = punch_in_ist.date() - timedelta(days=1)
        shift_start_dt = datetime.combine(att_date_obj, start_time, tzinfo=IST)
        shift_end_dt = datetime.combine(punch_in_ist.date(), end_time, tzinfo=IST)
    else:
        att_date_obj = punch_in_ist.date()
        shift_start_dt = datetime.combine(att_date_obj, start_time, tzinfo=IST)
        if is_overnight:
            shift_end_dt = datetime.combine(att_date_obj + timedelta(days=1), end_time, tzinfo=IST)
        else:
            shift_end_dt = datetime.combine(att_date_obj, end_time, tzinfo=IST)

    return att_date_obj.isoformat(), shift_start_dt, shift_end_dt

def get_shift_bounds_for_date(date_str: str, shift_start_str: str, shift_end_str: str) -> Tuple[datetime, datetime]:
    """Rule R1."""
    att_date = date.fromisoformat(date_str)
    start_time = parse_hh_mm(shift_start_str)
    end_time = parse_hh_mm(shift_end_str)

    is_overnight = end_time <= start_time
    shift_start_dt = datetime.combine(att_date, start_time, tzinfo=IST)
    if is_overnight:
        shift_end_dt = datetime.combine(att_date + timedelta(days=1), end_time, tzinfo=IST)
    else:
        shift_end_dt = datetime.combine(att_date, end_time, tzinfo=IST)

    return shift_start_dt, shift_end_dt

def compute_late_minutes(punch_in_dt: datetime, shift_start_dt: datetime) -> int:
    """Rule R2."""
    punch_in_ist = punch_in_dt.astimezone(IST)
    diff_seconds = int((punch_in_ist - shift_start_dt).total_seconds())
    if diff_seconds > 600:
        return diff_seconds // 60
    return 0

def compute_work_hours(punch_in_dt: datetime, punch_out_dt: datetime) -> float:
    """Rule R4."""
    diff_seconds = int((punch_out_dt - punch_in_dt).total_seconds())
    hours_dec = Decimal(diff_seconds) / Decimal(3600)
    rounded = hours_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded)

def compute_overtime(punch_out_dt: datetime, shift_end_dt: datetime) -> int:
    """Rule R3."""
    punch_out_ist = punch_out_dt.astimezone(IST)
    diff_seconds = int((punch_out_ist - shift_end_dt).total_seconds())
    if diff_seconds >= 1800:
        return diff_seconds // 60
    return 0

def compute_half_day(work_hours: float) -> bool:
    """Rule R5."""
    return work_hours < 4.50

def count_working_days_in_month(month_str: str, joined_on_str: str) -> int:
    """Rule R7."""
    year, month = map(int, month_str.split("-"))
    start_date = date(year, month, 1)

    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    joined_date = date.fromisoformat(joined_on_str)
    effective_start = max(start_date, joined_date)

    if effective_start > end_date:
        return 0

    count = 0
    curr = effective_start
    while curr <= end_date:
        if curr.weekday() < 5:
            count += 1
        curr += timedelta(days=1)
    return count
