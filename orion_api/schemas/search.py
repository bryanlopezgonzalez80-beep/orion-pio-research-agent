from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .papers import PaperResponse


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("query must contain at least two characters")
        return normalized


class SearchResponse(BaseModel):
    query: str
    origin: str
    results: list[PaperResponse]
    count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
