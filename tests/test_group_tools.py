from __future__ import annotations

from typing import Any

import pytest


class DumpableResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        for key, value in payload.items():
            setattr(self, key, value)

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return self._payload


class FakeGroupService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def add_user_to_group(self, user_upn: str, group_id: str) -> DumpableResponse:
        self.calls.append(("add_user_to_group", user_upn, group_id))
        return DumpableResponse(
            {
                "success": True,
                "group_id": group_id,
                "user_id": "user-123",
                "user_principal_name": user_upn,
                "user_display_name": "Alice Silva",
                "action": "add",
                "message": "Usuario adicionado ao grupo com sucesso.",
                "request_id": None,
            }
        )

    async def remove_user_from_group(self, user_upn: str, group_id: str) -> DumpableResponse:
        self.calls.append(("remove_user_from_group", user_upn, group_id))
        return DumpableResponse(
            {
                "success": True,
                "group_id": group_id,
                "user_id": "user-123",
                "user_principal_name": user_upn,
                "user_display_name": "Alice Silva",
                "action": "remove",
                "message": "Usuario removido do grupo com sucesso.",
                "request_id": None,
            }
        )


class FakeAuthorizer:
    def __init__(self) -> None:
        self.permissions: list[str] = []

    async def require_group_read_permission(self) -> None:
        self.permissions.append("read")

    async def require_group_write_permission(self) -> None:
        self.permissions.append("write")


class FakeAuditLogger:
    def log_group_query(self, tool_name: str, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_group_membership_tools_route_to_service_and_require_write_permission():
    from fastmcp import FastMCP

    from mcp_entraid.tools.groups import register_group_tools

    mcp = FastMCP(name="test")
    service = FakeGroupService()
    authorizer = FakeAuthorizer()
    register_group_tools(mcp, service, authorizer, FakeAuditLogger())

    group_id = "00000000-0000-0000-0000-000000000010"
    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert "entra_add_user_to_group" in tool_names
    assert "entra_remove_user_from_group" in tool_names

    add_tool = await mcp.get_tool("entra_add_user_to_group")
    add_result = (
        await add_tool.run({"user_upn": "alice@example.com", "group_id": group_id})
    ).structured_content

    remove_tool = await mcp.get_tool("entra_remove_user_from_group")
    remove_result = (
        await remove_tool.run({"user_upn": "alice@example.com", "group_id": group_id})
    ).structured_content

    assert add_result["action"] == "add"
    assert remove_result["action"] == "remove"
    assert service.calls == [
        ("add_user_to_group", "alice@example.com", group_id),
        ("remove_user_from_group", "alice@example.com", group_id),
    ]
    assert authorizer.permissions == ["write", "write"]
