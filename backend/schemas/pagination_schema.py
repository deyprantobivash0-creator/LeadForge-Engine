from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(
        default=1,
        ge=1,
    )

    page_size: int = Field(
        default=50,
        ge=1,
        le=100,
    )


class PaginatedResponse(BaseModel):
    items: list
    page: int
    page_size: int
    total: int
    pages: int