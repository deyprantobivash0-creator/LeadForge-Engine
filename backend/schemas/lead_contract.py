from enum import StrEnum


class LeadPriority(StrEnum):
    HOT = "Hot"
    WARM = "Warm"
    COLD = "Cold"


class LeadLifecycle(StrEnum):
    NEW = "New"
    QUALIFIED = "Qualified"
    CONTACTED = "Contacted"
    MEETING = "Meeting"
    WON = "Won"
    LOST = "Lost"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
