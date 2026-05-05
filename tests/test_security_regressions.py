from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest

from mcp_entraid.graph.errors import GraphThrottlingError
from mcp_entraid.schemas.authentication_methods import (
    AuthenticationMethodSummary,
    ResetMfaWorkflowState,
)
from mcp_entraid.services.application_service import ApplicationService
from mcp_entraid.services.user_service import UserService
from mcp_entraid.workflows.reset_mfa_workflow import (
    ResetMfaWorkflow,
    STEP_DELETE_AUTHENTICATION_METHODS,
)
from mcp_entraid.workflows.workflow_store import WorkflowStore


EXPECTED_PUBLIC_TOOLS = {
    "azure_unlock_user",
    "entra_check_required_groups_by_platform",
    "entra_find_app_registrations_by_user",
    "entra_find_groups",
    "entra_get_direct_reports",
    "entra_get_user",
    "entra_list_expiring_app_credentials",
    "entra_list_microsoft_authenticator_methods",
    "entra_list_group_members",
    "entra_list_phone_methods",
    "entra_list_user_groups",
    "entra_reset_mfa",
}


class FakeGraphClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    async def get(self, path: str, params: dict[str, str] | None = None):
        self.calls.append((path, params))
        raise AssertionError("Graph client should not be called for invalid inputs.")

    async def post(self, path: str, json: dict | None = None):
        raise AssertionError("Graph client should not be called for invalid inputs.")

    async def delete(self, path: str):
        raise AssertionError("Graph client should not be called for invalid inputs.")


class FakeAppGraphClient:
    async def get(self, path: str, params: dict[str, str] | None = None):
        if path == "/applications":
            return {"value": []}
        raise AssertionError(f"Unexpected path: {path}")

    async def get_absolute(self, url: str):
        return {"value": []}


class FakeUserServiceForApps:
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


class FakeAuthMethodService:
    async def list_phone_methods(self, user_id: str):
        return [
            AuthenticationMethodSummary(
                id="phone-1",
                type="phoneMethod",
                display_name="mobile",
                phone_type="mobile",
                phone_number_masked="***-1234",
            )
        ]

    async def list_microsoft_authenticator_methods(self, user_id: str):
        return []

    async def delete_phone_method(self, user_id: str, method: AuthenticationMethodSummary):
        raise AssertionError("Should not delete in this regression test.")

    async def delete_microsoft_authenticator_method(self, user_id: str, method: AuthenticationMethodSummary):
        raise AssertionError("Should not delete in this regression test.")

    async def revoke_sign_in_sessions(self, user_id: str) -> bool:
        raise AssertionError("Should not revoke in this regression test.")


class AllowAllAuthorizer:
    async def authorize(self, permission: str) -> None:
        return None

    async def require_reset_mfa_permission(self) -> None:
        return None

    async def require_application_read_permission(self) -> None:
        return None


class NullAuditLogger:
    def log_workflow_event(self, tool_name: str, **kwargs) -> None:
        return None

    def log_application_query(self, tool_name: str, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_user_service_rejects_ambiguous_and_wildcard_upns():
    service = UserService(FakeGraphClient())

    bad_inputs = [
        "*",
        "all",
        "everyone",
        "tenant",
        "alice@example.com, bob@example.com",
        "alice@example.com;bob@example.com",
        "alice@example.com bob@example.com",
        ["alice@example.com"],
    ]

    for user_upn in bad_inputs:
        response = await service.get_user(user_upn)  # type: ignore[arg-type]
        assert response.success is False
        assert response.data is None


@pytest.mark.asyncio
async def test_application_service_rejects_invalid_thresholds():
    service = ApplicationService(FakeAppGraphClient(), FakeUserServiceForApps())

    for invalid_threshold in [0, -1, 366, 999]:
        with pytest.raises(ValueError):
            await service.list_expiring_app_credentials(days_threshold=invalid_threshold)


@pytest.mark.asyncio
async def test_application_service_handles_graph_throttling():
    class ThrottledGraphClient(FakeAppGraphClient):
        async def get(self, path: str, params: dict[str, str] | None = None):
            raise GraphThrottlingError(
                status_code=429,
                message="Microsoft Graph aplicou throttling. Retry-After: 5 segundo(s).",
                request_id="req-429",
                retry_after=5,
            )

    service = ApplicationService(ThrottledGraphClient(), FakeUserServiceForApps())
    response = await service.list_expiring_app_credentials(days_threshold=30)

    assert response.success is False
    assert response.request_id == "req-429"
    assert "throttling" in response.message.lower()


@pytest.mark.asyncio
async def test_reset_mfa_workflow_rejects_expired_and_replayed_steps():
    class UserServiceStub:
        async def get_user(self, user_upn):
            return type(
                "Resp",
                (),
                {
                    "success": True,
                    "data": type(
                        "User",
                        (),
                        {
                            "user_id": "user-123",
                            "user_principal_name": "alice@example.com",
                            "display_name": "Alice Silva",
                        },
                    )(),
                    "request_id": None,
                    "error": None,
                },
            )()

    workflow = ResetMfaWorkflow(
        user_service=UserServiceStub(),
        authentication_method_service=FakeAuthMethodService(),
        workflow_store=WorkflowStore(),
        authorizer=AllowAllAuthorizer(),
        audit_logger=NullAuditLogger(),
    )

    start = await workflow.start("alice@example.com")
    state = workflow._workflow_store.get_reset_mfa_state(start.reset_request_id)  # noqa: SLF001
    assert state is not None
    expired_state = ResetMfaWorkflowState(
        reset_request_id=state.reset_request_id,
        user_id=state.user_id,
        user_principal_name=state.user_principal_name,
        user_display_name=state.user_display_name,
        phone_methods=state.phone_methods,
        mfa_methods=state.mfa_methods,
        status=state.status,
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        deleted_phone_methods=state.deleted_phone_methods,
        deleted_mfa_methods=state.deleted_mfa_methods,
        failed_methods=state.failed_methods,
        sessions_revoked=state.sessions_revoked,
        created_at=state.created_at,
        expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    workflow._workflow_store.save_reset_mfa_state(expired_state)  # noqa: SLF001

    status = await workflow.status(start.reset_request_id)
    assert status.status == "expired"
    assert status.success is False

    replay = await workflow.execute_step(start.reset_request_id, STEP_DELETE_AUTHENTICATION_METHODS, True)
    assert replay.success is False
    assert replay.status == "expired"


@pytest.mark.asyncio
async def test_public_server_exposes_only_unlock_user_runbook_tool(monkeypatch):
    env = {
        "TENANT_ID": "tenant",
        "CLIENT_ID": "client",
        "CLIENT_SECRET": "secret",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    module = importlib.import_module("mcp_entraid.server")
    mcp = module.mcp

    tool_names = {tool.name for tool in await mcp.list_tools()}
    assert tool_names == EXPECTED_PUBLIC_TOOLS
