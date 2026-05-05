from __future__ import annotations

import pytest

from mcp_entraid.schemas.authentication_methods import AuthenticationMethodSummary


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


class FakeUserService:
    async def get_user(self, user_upn: str):
        return type(
            "Response",
            (),
            {
                "success": True,
                "data": type(
                    "User",
                    (),
                    {
                        "user_id": "user-123",
                        "user_principal_name": user_upn,
                        "display_name": "Alice Silva",
                    },
                )(),
                "request_id": None,
                "error": None,
            },
        )()


class FakeAuthenticationMethodService:
    async def list_phone_methods(self, user_id: str):
        return [
            AuthenticationMethodSummary(
                id="phone-1",
                type="phoneMethod",
                display_name="mobile",
                phone_type="mobile",
                phone_number_masked="***-1234",
                status="notAllowedByPolicy",
            )
        ]

    async def list_microsoft_authenticator_methods(self, user_id: str):
        return [
            AuthenticationMethodSummary(
                id="mfa-1",
                type="microsoftAuthenticatorMethod",
                display_name="Microsoft Authenticator",
            )
        ]


class AllowResetMfaAuthorizer:
    async def require_reset_mfa_permission(self) -> None:
        return None


@pytest.mark.asyncio
async def test_authentication_method_tools_include_read_only_methods_and_mfa_facade():
    from fastmcp import FastMCP

    from mcp_entraid.tools.authentication_methods import register_authentication_method_tools

    mcp = FastMCP(name="test")
    workflow = FakeResetMfaWorkflow()
    register_authentication_method_tools(
        mcp,
        user_service=FakeUserService(),
        authentication_method_service=FakeAuthenticationMethodService(),
        reset_mfa_workflow=workflow,
        authorizer=AllowResetMfaAuthorizer(),
    )

    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert "entra_list_phone_methods" in tool_names
    assert "entra_list_microsoft_authenticator_methods" in tool_names
    assert "entra_reset_mfa" in tool_names
    assert "entra_reset_user_mfa_start" not in tool_names
    assert "entra_reset_user_mfa_execute_step" not in tool_names
    assert "entra_reset_user_mfa_status" not in tool_names

    phone_tool = await mcp.get_tool("entra_list_phone_methods")
    phone_result = (await phone_tool.run({"user_upn": "alice@example.com"})).structured_content
    assert phone_result["methods_kind"] == "phone"
    assert phone_result["methods"][0]["phone_type"] == "mobile"

    mfa_tool = await mcp.get_tool("entra_list_microsoft_authenticator_methods")
    mfa_result = (await mfa_tool.run({"user_upn": "alice@example.com"})).structured_content
    assert mfa_result["methods_kind"] == "microsoft_authenticator"
    assert mfa_result["methods"][0]["display_name"] == "Microsoft Authenticator"

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
    register_authentication_method_tools(
        mcp,
        user_service=FakeUserService(),
        authentication_method_service=FakeAuthenticationMethodService(),
        reset_mfa_workflow=FakeResetMfaWorkflow(),
        authorizer=AllowResetMfaAuthorizer(),
    )

    tool = await mcp.get_tool("entra_reset_mfa")

    result = (await tool.run({"action": "start"})).structured_content
    assert result["success"] is False
    assert "user_upn" in result["message"]
