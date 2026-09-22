from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


LeadStatus = Literal[
    "New",
    "Qualified",
    "Contacted",
    "Meeting",
    "Won",
    "Lost",
]


class LeadLifecycleUpdate(BaseModel):

    status: LeadStatus | None = None

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    last_contacted: datetime | None = None

    next_follow_up: datetime | None = None