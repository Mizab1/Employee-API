from enum import Enum
from typing import Annotated, Optional
from pydantic import Field

EpochMillis = Annotated[int, Field(ge=100000000000, le=4102444800000, description="Epoch milliseconds")]
EpochMillisNullable = Optional[Annotated[int, Field(ge=100000000000, le=4102444800000, description="Epoch milliseconds or null")]]

class StatusEnum(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    WFH = "WFH"
    ON_DUTY = "ON_DUTY"

class PresenceStatusEnum(str, Enum):
    PRESENT = "PRESENT"
    WFH = "WFH"
    ON_DUTY = "ON_DUTY"
