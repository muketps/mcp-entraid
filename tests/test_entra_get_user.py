from typing import Any

import pytest

from mcp_entraid.schemas.common import ToolResponse
from mcp_entraid.schemas.users import EntraUser


class FakeUserService:
    async def get_user(self, user_upn: str) -> ToolResponse[EntraUser]:
        return ToolResponse[EntraUser](
            success=True,
            data=EntraUser(
                user_id="user-123",
                user_display_name="Alice Silva",
                user_principal_name=user_upn,
                mail="alice@example.com",
                job_title="Manager",
                department="IT",
                account_enabled=True,
                office_location="Sao Paulo",
                mobile_phone="+55 11 99999-9999",
            ),
        )


class FakeAuthorizer:
    def __init__(self) -> None:
        self.permissions: list[str] = []

    async def authorize(self, permission: str) -> None:
        self.permissions.append(permission)


class FakeAuditLogger:
    def log_tool_call(self, tool_name: str, metadata: dict[str, Any] | None = None) -> None:
        pass

    def log_tool_result(
        self,
        tool_name: str,
        success: bool,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass


@pytest.mark.asyncio
async def test_entra_get_user_returns_standardized_response():
    from fastmcp import FastMCP

    from mcp_entraid.security.permissions import ENTRA_USER_READ
    from mcp_entraid.tools.users import register_user_tools

    mcp = FastMCP(name="test")
    authorizer = FakeAuthorizer()
    register_user_tools(mcp, FakeUserService(), authorizer, FakeAuditLogger())

    tool = await mcp.get_tool("entra_get_user")
    tool_result = await tool.run({"user_upn": "alice@example.com"})
    result = tool_result.structured_content

    assert result["success"] is True
    assert result["data"]["user_id"] == "user-123"
    assert result["data"]["user_display_name"] == "Alice Silva"
    assert result["data"]["user_principal_name"] == "alice@example.com"
    assert result["error"] is None
    assert authorizer.permissions == [ENTRA_USER_READ]
