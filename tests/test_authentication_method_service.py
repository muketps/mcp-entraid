import httpx
import pytest

from mcp_entraid.auth.graph_token_provider import GraphTokenProvider
from mcp_entraid.graph.client import GraphClient
from mcp_entraid.services.authentication_method_service import AuthenticationMethodService
from mcp_entraid.settings import Settings


def make_settings() -> Settings:
    return Settings(
        TENANT_ID="tenant",
        CLIENT_ID="client",
        CLIENT_SECRET="secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
    )


def make_service(handler) -> AuthenticationMethodService:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    token_provider = GraphTokenProvider(make_settings(), http_client=http_client)
    token_provider._cached_token = type(  # noqa: SLF001
        "Token",
        (),
        {"access_token": "token", "expires_at": 9_999_999_999},
    )()
    graph_client = GraphClient(make_settings(), token_provider, http_client=http_client)
    return AuthenticationMethodService(graph_client)


@pytest.mark.asyncio
async def test_lists_phone_methods_in_required_delete_order_and_masks_number():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/users/alice/authentication/phoneMethods"
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "3179e48a-750b-4051-897c-87b9720928f7",
                        "phoneType": "mobile",
                        "phoneNumber": "+55 11 99999-3333",
                    },
                    {
                        "id": "b6332ec1-7057-4abe-9331-3d72feddfe41",
                        "phoneType": "alternateMobile",
                        "phoneNumber": "+55 11 99999-1111",
                    },
                    {
                        "id": "e37fc753-ff3b-4958-9484-eaa9425c82bc",
                        "phoneType": "office",
                        "phoneNumber": "+55 11 99999-2222",
                    },
                ]
            },
        )

    service = make_service(handler)
    methods = await service.list_phone_methods("alice")

    assert [method.phone_type for method in methods] == ["alternateMobile", "office", "mobile"]
    assert [method.phone_number_masked for method in methods] == ["***-1111", "***-2222", "***-3333"]


@pytest.mark.asyncio
async def test_delete_method_404_returns_failed_operation_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(
            404,
            headers={"request-id": "req-404"},
            json={"error": {"message": "Not found"}},
        )

    service = make_service(handler)
    result = await service.delete_phone_method(
        "alice",
        method=type(
            "Method",
            (),
            {
                "id": "missing-method",
                "type": "phoneMethod",
                "display_name": "mobile",
            },
        )(),
    )

    assert result.status == "failed"
    assert result.reason == "Recurso não encontrado no Microsoft Graph."
