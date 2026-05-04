from typing import Any

import pytest

from mcp_entraid.schemas.applications import (
    AppRegistrationUserMatch,
    ExpiringAppCredentialItem,
    ExpiringAppCredentialsResponse,
    FindAppRegistrationsByUserResponse,
)


class FakeApplicationService:
    async def list_expiring_app_credentials(
        self,
        days_threshold: int = 30,
        include_expired: bool = True,
        include_certificates: bool = True,
        include_secrets: bool = True,
    ) -> ExpiringAppCredentialsResponse:
        return ExpiringAppCredentialsResponse(
            success=True,
            days_threshold=days_threshold,
            include_expired=include_expired,
            expiring_credentials_count=1,
            applications_count=1,
            items=[
                ExpiringAppCredentialItem(
                    application_object_id="app-1",
                    app_id="app-id-1",
                    display_name="Alice Portal",
                    credential={
                        "credential_id": "secret-1",
                        "credential_type": "secret",
                        "display_name": "primary secret",
                        "start_date_time": "2025-01-01T00:00:00Z",
                        "end_date_time": "2026-05-10T00:00:00Z",
                        "days_until_expiration": 6,
                        "status": "expiring_soon",
                    },
                )
            ],
            message="ok",
        )

    async def find_app_registrations_by_user(
        self,
        user_upn: str,
        search_display_name: bool = True,
        search_owned_apps: bool = True,
    ) -> FindAppRegistrationsByUserResponse:
        return FindAppRegistrationsByUserResponse(
            success=True,
            user_id="user-123",
            user_principal_name=user_upn,
            user_display_name="Alice Silva",
            matches_count=1,
            matches=[
                AppRegistrationUserMatch(
                    application_object_id="app-1",
                    app_id="app-id-1",
                    display_name="Alice Portal",
                    created_date_time="2025-01-01T00:00:00Z",
                    match_type="owner",
                    matched_reason="owner",
                    secret_credentials_count=1,
                    certificate_credentials_count=0,
                    nearest_credential_expiration="2026-05-10T00:00:00Z",
                )
            ],
            message="ok",
        )


class FakeAuthorizer:
    def __init__(self) -> None:
        self.permissions: list[str] = []

    async def authorize(self, permission: str) -> None:
        self.permissions.append(permission)

    async def require_application_read_permission(self) -> None:
        self.permissions.append("entra:application:read")


class FakeAuditLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log_application_query(self, tool_name: str, **kwargs) -> None:
        self.events.append({"tool_name": tool_name, **kwargs})


@pytest.mark.asyncio
async def test_application_tools_use_upn_and_authorization():
    from fastmcp import FastMCP

    from mcp_entraid.tools.applications import register_application_tools

    mcp = FastMCP(name="test")
    authorizer = FakeAuthorizer()
    audit_logger = FakeAuditLogger()
    register_application_tools(mcp, FakeApplicationService(), authorizer, audit_logger)

    tool = await mcp.get_tool("entra_find_app_registrations_by_user")
    result = (await tool.run({"user_upn": "alice@example.com"})).structured_content

    assert result["success"] is True
    assert result["user_principal_name"] == "alice@example.com"
    assert result["matches"][0]["display_name"] == "Alice Portal"
    assert authorizer.permissions.count("entra:application:read") >= 1

    tool = await mcp.get_tool("entra_list_expiring_app_credentials")
    result = (await tool.run({"days_threshold": 30})).structured_content

    assert result["success"] is True
    assert result["items"][0]["display_name"] == "Alice Portal"
