from typing import Any

import pytest

from mcp_entraid.schemas.common import ToolResponse
from mcp_entraid.schemas.users import EntraUser


class FakeUserService:
    async def get_direct_reports(self, user_upn: str) -> ToolResponse[list[EntraUser]]:
        return ToolResponse[list[EntraUser]](
            success=True,
            data=[
                EntraUser(
                    user_id="bob",
                    user_display_name="Bob Costa",
                    user_principal_name="bob@example.com",
                    mail="bob@example.com",
                    job_title="Analyst",
                    department="IT",
                )
            ],
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
async def test_entra_get_direct_reports_returns_standardized_response():
    from fastmcp import FastMCP

    from mcp_entraid.security.permissions import ENTRA_DIRECT_REPORTS_READ
    from mcp_entraid.tools.users import register_user_tools

    mcp = FastMCP(name="test")
    authorizer = FakeAuthorizer()
    register_user_tools(mcp, FakeUserService(), authorizer, FakeAuditLogger())

    tool = await mcp.get_tool("entra_get_direct_reports")
    tool_result = await tool.run({"user_upn": "alice@example.com"})
    result = tool_result.structured_content

    assert result["success"] is True
    assert result["data"][0]["user_id"] == "bob"
    assert result["data"][0]["user_display_name"] == "Bob Costa"
    assert result["data"][0]["user_principal_name"] == "bob@example.com"
    assert result["error"] is None
    assert authorizer.permissions == [ENTRA_DIRECT_REPORTS_READ]
