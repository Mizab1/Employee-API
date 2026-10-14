from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import ( EpochMillis, EpochMillisNullable, PresenceStatusEnum, StatusEnum)

class PunchInRequest(BaseModel):
    emp_code: str
    punched_at: Optional[EpochMillis] = None
    status: PresenceStatusEnum = PresenceStatusEnum.PRESENT

class PunchOutRequest(BaseModel):
    emp_code: str
    punched_at: Optional[EpochMillis] = None

class RegularizeRequest(BaseModel):
    status: Optional[StatusEnum] = None
    punch_in: Optional[EpochMillis] = None
    punch_out: Optional[EpochMillis] = None
    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)

class HistoryChange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: Any = Field(default=None, alias="from")
    to: Any = None

class HistoryEntry(BaseModel):
    at: EpochMillis
    by: str
    reason: str
    changes: dict[str, HistoryChange]

class AttendanceRecord(BaseModel):
    emp_code: str
    date: str
    status: StatusEnum
    punch_in: EpochMillisNullable = None
    punch_out: EpochMillisNullable = None
    work_hours: Optional[float] = None
    late_minutes: int = 0
    overtime_minutes: int = 0
    half_day: bool = False
    history: list[HistoryEntry] = Field(default_factory=list)

class AttendancePage(BaseModel):
    items: list[AttendanceRecord]
    total: int
    page: int
    page_size: int
