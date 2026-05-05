from __future__ import annotations

from typing import Any

import pytest


class DumpableResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return self._payload


class FakeRunbookService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def unlock_user(
        self,
        user_upn: str,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> DumpableResponse:
        self.calls.append(("unlock_user", user_upn, wait_for_completion, timeout_seconds))
        return DumpableResponse(
            {
                "success": True,
                "runbook_name": "Unlock-User",
                "job_name": "job-123",
                "status": "Completed",
            }
        )


@pytest.mark.asyncio
async def test_azure_unlock_user_tool_routes_user_upn_to_service():
    from fastmcp import FastMCP

    from mcp_entraid.tools.runbooks import register_azure_unlock_user_tool

    mcp = FastMCP(name="test")
    service = FakeRunbookService()
    register_azure_unlock_user_tool(mcp, service)

    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert "azure_unlock_user" in tool_names

    tool = await mcp.get_tool("azure_unlock_user")
    result = (await tool.run({"user_upn": "alice@example.com"})).structured_content

    assert result["success"] is True
    assert result["runbook_name"] == "Unlock-User"
    assert service.calls == [("unlock_user", "alice@example.com", True, 60)]
