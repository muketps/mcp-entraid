from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraphAPIError(Exception):
    status_code: int
    message: str
    request_id: str | None = None
    retry_after: int | None = None

    def __str__(self) -> str:
        return self.message


class GraphAuthenticationError(GraphAPIError):
    pass


class GraphPermissionError(GraphAPIError):
    pass


class GraphNotFoundError(GraphAPIError):
    pass


class GraphThrottlingError(GraphAPIError):
    pass


class GraphServerError(GraphAPIError):
    pass
