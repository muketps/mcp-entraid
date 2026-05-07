from __future__ import annotations

from typing import Any

import pytest


class DumpableResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return self._payload


class FakeResetPasswordWorkflow:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def start(self, user_upn: str) -> DumpableResponse:
        self.calls.append(("start", user_upn))
        return DumpableResponse({"success": True, "status": "pending_confirmation"})

    async def execute(self, reset_password_request_id: str, confirmation: str) -> DumpableResponse:
        self.calls.append(("execute", reset_password_request_id, confirmation))
        return DumpableResponse({"success": True, "status": "completed"})

    async def execute_by_user_upn(self, user_upn: str, confirmation: str) -> DumpableResponse:
        self.calls.append(("execute_by_user_upn", user_upn, confirmation))
        return DumpableResponse({"success": True, "status": "completed"})


@pytest.mark.asyncio
async def test_entra_reset_user_password_is_single_public_facade():
    from fastmcp import FastMCP

    from mcp_entraid.tools.passwords import register_password_tools

    mcp = FastMCP(name="test")
    workflow = FakeResetPasswordWorkflow()
    register_password_tools(mcp, workflow)

    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert tool_names == {"entra_reset_user_password"}

    tool = await mcp.get_tool("entra_reset_user_password")
    first = (await tool.run({"user_upn": "alice@example.com"})).structured_content
    second = (
        await tool.run(
            {
                "reset_password_request_id": "req-123",
                "confirmation": "CONFIRMO RESET SENHA alice@example.com",
            }
        )
    ).structured_content
    invalid = (
        await tool.run(
            {
                "user_upn": "alice@example.com",
                "reset_password_request_id": "req-123",
            }
        )
    ).structured_content

    assert first["status"] == "pending_confirmation"
    assert second["status"] == "completed"
    assert invalid["success"] is False
    assert workflow.calls == [
        ("start", "alice@example.com"),
        ("execute", "req-123", "CONFIRMO RESET SENHA alice@example.com"),
    ]


@pytest.mark.asyncio
async def test_entra_reset_user_password_accepts_confirmation_with_user_upn_for_pending_workflow():
    from fastmcp import FastMCP

    from mcp_entraid.tools.passwords import register_password_tools

    mcp = FastMCP(name="test")
    workflow = FakeResetPasswordWorkflow()
    register_password_tools(mcp, workflow)

    tool = await mcp.get_tool("entra_reset_user_password")
    result = (
        await tool.run(
            {
                "user_upn": "alice@example.com",
                "confirmation": "CONFIRMO RESET SENHA alice@example.com",
            }
        )
    ).structured_content

    assert result["status"] == "completed"
    assert workflow.calls == [
        ("execute_by_user_upn", "alice@example.com", "CONFIRMO RESET SENHA alice@example.com")
    ]
