from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ToolResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None
    request_id: str | None = None
