from datetime import datetime, timezone

import pytest

from mcp_entraid.schemas.users import EntraUser
from mcp_entraid.services import application_service as app_service_module
from mcp_entraid.services.application_service import ApplicationService


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls(2026, 5, 4, 12, 0, 0)
        return cls(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc)


class FakeUserService:
    async def get_user(self, user_upn: str):
        if user_upn in {"all", "*", "todos", "everyone", "tenant"}:
            return type(
                "Response",
                (),
                {
                    "success": False,
                    "data": None,
                    "request_id": None,
                    "error": "Informe apenas um UPN de usuario. Valores amplos nao sao permitidos.",
                },
            )()
        return type(
            "Response",
            (),
            {
                "success": True,
                "data": EntraUser(
                    user_id="user-123",
                    user_display_name="Alice Silva",
                    user_principal_name="alice@example.com",
                ),
                "request_id": None,
                "error": None,
            },
        )()


class FakeGraphClient:
    def __init__(self) -> None:
        self.application_calls: list[str] = []
        self.owned_object_calls: list[str] = []
        self.absolute_calls: list[str] = []

    async def get(self, path: str, params: dict[str, str] | None = None):
        if path == "/applications":
            self.application_calls.append(path)
            return {
                "value": [
                    {
                        "id": "app-1",
                        "appId": "app-id-1",
                        "displayName": "Alice Silva Portal",
                        "createdDateTime": "2025-01-01T00:00:00Z",
                        "passwordCredentials": [
                            {
                                "keyId": "secret-1",
                                "displayName": "primary secret",
                                "startDateTime": "2025-01-01T00:00:00Z",
                                "endDateTime": "2026-05-10T00:00:00Z",
                            }
                        ],
                        "keyCredentials": [
                            {
                                "keyId": "cert-1",
                                "displayName": "primary certificate",
                                "startDateTime": "2025-01-01T00:00:00Z",
                                "endDateTime": "2026-07-01T00:00:00Z",
                            }
                        ],
                    }
                ],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/applications?$skiptoken=2",
            }
        if path == "/users/user-123/ownedObjects":
            self.owned_object_calls.append(path)
            return {
                "value": [
                    {
                        "id": "app-1",
                        "@odata.type": "#microsoft.graph.application",
                    },
                    {
                        "id": "sp-1",
                        "@odata.type": "#microsoft.graph.servicePrincipal",
                    },
                ]
            }
        if path == "/applications?page=2":
            return {"value": []}
        return {"value": []}

    async def get_absolute(self, url: str):
        self.absolute_calls.append(url)
        if "applications" in url:
            return {
                "value": [
                    {
                        "id": "app-2",
                        "appId": "app-id-2",
                        "displayName": "alice@example.com Admin",
                        "createdDateTime": "2024-01-01T00:00:00Z",
                        "passwordCredentials": [
                            {
                                "keyId": "secret-2",
                                "displayName": "expired secret",
                                "startDateTime": "2024-01-01T00:00:00Z",
                                "endDateTime": "2026-04-30T00:00:00Z",
                            }
                        ],
                        "keyCredentials": [],
                    },
                    {
                        "id": "app-3",
                        "appId": "app-id-3",
                        "displayName": "No Credentials App",
                        "createdDateTime": "2024-06-01T00:00:00Z",
                        "passwordCredentials": [],
                        "keyCredentials": [],
                    },
                ]
            }
        return {"value": []}


@pytest.mark.asyncio
async def test_list_expiring_app_credentials_collects_and_sorts_credentials(monkeypatch):
    monkeypatch.setattr(app_service_module, "datetime", FrozenDateTime)
    service = ApplicationService(FakeGraphClient(), FakeUserService())

    response = await service.list_expiring_app_credentials(days_threshold=30)

    assert response.success is True
    assert response.expiring_credentials_count == 2
    assert response.applications_count == 2
    assert response.items[0].application_object_id == "app-2"
    assert response.items[0].credential.status == "expired"
    assert response.items[1].application_object_id == "app-1"
    assert response.items[1].credential.status == "expiring_soon"
    assert response.items[0].credential.credential_type == "secret"


@pytest.mark.asyncio
async def test_find_app_registrations_by_user_matches_owner_and_display_name(monkeypatch):
    monkeypatch.setattr(app_service_module, "datetime", FrozenDateTime)
    service = ApplicationService(FakeGraphClient(), FakeUserService())

    response = await service.find_app_registrations_by_user(
        "alice@example.com",
        search_display_name=True,
        search_owned_apps=True,
    )

    assert response.success is True
    assert response.user_id == "user-123"
    assert response.user_principal_name == "alice@example.com"
    assert response.matches_count == 2
    assert {item.match_type for item in response.matches} == {"owner_and_display_name", "display_name"}
    assert any(item.match_type == "owner_and_display_name" for item in response.matches)
    assert any(item.match_type == "display_name" for item in response.matches)


@pytest.mark.asyncio
async def test_application_service_rejects_wildcard_user_upn():
    service = ApplicationService(FakeGraphClient(), FakeUserService())

    response = await service.find_app_registrations_by_user("*")

    assert response.success is False
    assert response.matches_count == 0


@pytest.mark.asyncio
async def test_find_app_registrations_by_user_without_search_criteria_returns_empty_result():
    service = ApplicationService(FakeGraphClient(), FakeUserService())

    response = await service.find_app_registrations_by_user(
        "alice@example.com",
        search_display_name=False,
        search_owned_apps=False,
    )

    assert response.success is True
    assert response.matches_count == 0
    assert response.matches == []
    assert "nenhum criterio" in response.message.lower()
