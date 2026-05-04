import httpx
import pytest

from mcp_entraid.auth.graph_token_provider import GraphTokenProvider
from mcp_entraid.graph.client import GraphClient
from mcp_entraid.services.user_service import UserService
from mcp_entraid.settings import Settings


def make_settings() -> Settings:
    return Settings(
        TENANT_ID="tenant",
        CLIENT_ID="client",
        CLIENT_SECRET="secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
    )


def make_service(handler) -> UserService:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    token_provider = GraphTokenProvider(make_settings(), http_client=http_client)
    token_provider._cached_token = type(  # noqa: SLF001
        "Token",
        (),
        {"access_token": "token", "expires_at": 9_999_999_999},
    )()
    graph_client = GraphClient(make_settings(), token_provider, http_client=http_client)
    return UserService(graph_client)


@pytest.mark.asyncio
async def test_user_service_maps_graph_user_to_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/users/alice@example.com"
        assert request.url.params["$select"] == (
            "id,displayName,userPrincipalName,mail,jobTitle,department,"
            "accountEnabled,officeLocation,mobilePhone"
        )
        return httpx.Response(
            200,
            json={
                "id": "user-123",
                "displayName": "Alice Silva",
                "userPrincipalName": "alice@example.com",
                "mail": "alice@example.com",
                "jobTitle": "Manager",
                "department": "IT",
                "accountEnabled": True,
                "officeLocation": "Sao Paulo",
                "mobilePhone": "+55 11 99999-9999",
            },
        )

    service = make_service(handler)
    response = await service.get_user("alice@example.com")

    assert response.success is True
    assert response.data is not None
    assert response.data.user_id == "user-123"
    assert response.data.display_name == "Alice Silva"
    assert response.data.user_principal_name == "alice@example.com"
    assert response.error is None


@pytest.mark.asyncio
async def test_user_service_maps_graph_errors_to_tool_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"request-id": "req-123"},
            json={"error": {"message": "Forbidden"}},
    )

    service = make_service(handler)
    response = await service.get_user("alice@example.com")

    assert response.success is False
    assert response.data is None
    assert response.error == "Permissão insuficiente para consultar o Microsoft Graph."
    assert response.request_id == "req-123"
