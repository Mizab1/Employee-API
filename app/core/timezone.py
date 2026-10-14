from datetime import datetime, time, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

def truncate_to_seconds(epoch_ms: int) -> int:
    """Rule R1."""
    return (epoch_ms // 1000) * 1000

def epoch_ms_to_utc_dt(epoch_ms: int) -> datetime:
    truncated = truncate_to_seconds(epoch_ms)
    return datetime.fromtimestamp(truncated / 1000, tz=UTC)

def utc_dt_to_epoch_ms(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)

def parse_hh_mm(time_str: str) -> time:
    h, m = map(int, time_str.split(":"))
    return time(hour=h, minute=m)
