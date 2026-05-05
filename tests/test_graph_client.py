from __future__ import annotations

import httpx
import pytest

from mcp_entraid.auth.graph_token_provider import GraphTokenProvider
from mcp_entraid.graph.client import GraphClient
from mcp_entraid.graph.errors import GraphThrottlingError
from mcp_entraid.settings import Settings


def make_settings() -> Settings:
    return Settings(
        TENANT_ID="tenant",
        CLIENT_ID="client",
        CLIENT_SECRET="secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
    )


class StaticTokenProvider(GraphTokenProvider):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        super().__init__(settings, http_client=http_client)
        self._cached_token = type(  # noqa: SLF001
            "Token",
            (),
            {"access_token": "token", "expires_at": 9_999_999_999},
        )()


@pytest.mark.asyncio
async def test_graph_client_raises_throttling_error_with_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "5", "request-id": "req-429"},
            json={"error": {"message": "Too Many Requests"}},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    token_provider = StaticTokenProvider(make_settings(), http_client=http_client)
    client = GraphClient(make_settings(), token_provider, http_client=http_client)

    with pytest.raises(GraphThrottlingError) as exc_info:
        await client.get("/users/alice@example.com")

    assert exc_info.value.retry_after == 5
    assert exc_info.value.request_id == "req-429"
