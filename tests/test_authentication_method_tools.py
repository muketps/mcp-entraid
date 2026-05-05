from __future__ import annotations

import pytest


class DumpableResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict:
        return self._payload


class FakeResetMfaWorkflow:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def start(self, user_upn: str) -> DumpableResponse:
        self.calls.append(("start", user_upn))
        return DumpableResponse(
            {
                "success": True,
                "reset_request_id": "reset-123",
                "user_upn": user_upn,
            }
        )

    async def status(self, reset_request_id: str) -> DumpableResponse:
        self.calls.append(("status", reset_request_id))
        return DumpableResponse(
            {
                "success": True,
                "reset_request_id": reset_request_id,
                "status": "pending_confirmation",
            }
        )

    async def confirm_next_step(self, user_upn: str) -> DumpableResponse:
        self.calls.append(("confirm_next_step", user_upn))
        return DumpableResponse(
            {
                "success": True,
                "user_upn": user_upn,
                "step_completed": "delete_authentication_methods",
                "next_step": None,
                "sessions_revoked": True,
            }
        )


@pytest.mark.asyncio
async def test_reset_mfa_facade_is_the_only_public_mfa_tool_and_routes_actions():
    from fastmcp import FastMCP

    from mcp_entraid.tools.authentication_methods import register_authentication_method_tools

    mcp = FastMCP(name="test")
    workflow = FakeResetMfaWorkflow()
    register_authentication_method_tools(mcp, workflow)

    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert "entra_reset_mfa" in tool_names
    assert "entra_reset_user_mfa_start" not in tool_names
    assert "entra_reset_user_mfa_execute_step" not in tool_names
    assert "entra_reset_user_mfa_status" not in tool_names

    tool = await mcp.get_tool("entra_reset_mfa")

    start = (await tool.run({"action": "start", "user_upn": "alice@example.com"})).structured_content
    status = (await tool.run({"action": "status", "reset_request_id": "reset-123"})).structured_content
    confirm = (await tool.run({"action": "confirm", "user_upn": "alice@example.com"})).structured_content

    assert start["user_upn"] == "alice@example.com"
    assert status["status"] == "pending_confirmation"
    assert confirm["next_step"] is None
    assert confirm["sessions_revoked"] is True
    assert workflow.calls == [
        ("start", "alice@example.com"),
        ("status", "reset-123"),
        ("confirm_next_step", "alice@example.com"),
    ]


@pytest.mark.asyncio
async def test_reset_mfa_facade_validates_required_fields():
    from fastmcp import FastMCP

    from mcp_entraid.tools.authentication_methods import register_authentication_method_tools

    mcp = FastMCP(name="test")
    register_authentication_method_tools(mcp, FakeResetMfaWorkflow())

    tool = await mcp.get_tool("entra_reset_mfa")

    result = (await tool.run({"action": "start"})).structured_content
    assert result["success"] is False
    assert "user_upn" in result["message"]
