from __future__ import annotations

import base64
import json

import pytest

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.schemas.runbooks import RunbookExecutionResponse
from mcp_entraid.schemas.users import EntraUser
from mcp_entraid.settings import Settings
from mcp_entraid.workflows.reset_password_workflow import ResetPasswordWorkflow
from mcp_entraid.workflows.workflow_store import WorkflowStore


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        TENANT_ID="tenant",
        CLIENT_ID="client",
        CLIENT_SECRET="secret",
        PASSWORD_RESET_RUNBOOK_NAME="Reset-Password",
        AZURE_ALLOWED_RUNBOOKS="Reset-Password",
    )


class FakeUserService:
    async def get_user(self, user_upn: str):
        return type(
            "Response",
            (),
            {
                "success": True,
                "data": EntraUser(
                    user_id="user-123",
                    user_display_name="Alice Silva",
                    user_principal_name=user_upn,
                ),
                "request_id": None,
                "error": None,
            },
        )()


class FakePasswordResetService:
    def __init__(self) -> None:
        self.generated_passwords: list[str] = []

    def generate_temporary_password(self):
        password = f"Aa{len(self.generated_passwords)}9@#$%xY"
        self.generated_passwords.append(password)
        return password, None


class FakeRunbookService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute_runbook(
        self,
        runbook_name: str,
        parameters: dict[str, str] | None = None,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> RunbookExecutionResponse:
        self.calls.append(
            {
                "runbook_name": runbook_name,
                "parameters": parameters,
                "wait_for_completion": wait_for_completion,
                "timeout_seconds": timeout_seconds,
            }
        )
        encoded = base64.b64encode(json.dumps({"changed": True}).encode("utf-8")).decode("ascii")
        return RunbookExecutionResponse(
            success=True,
            runbook_name=runbook_name,
            job_name="job-123",
            job_id="job-id-123",
            status="Completed",
            output=encoded,
            streams=[],
            timed_out=False,
            message="Runbook concluido.",
        )


class FakeAuthorizer:
    def __init__(self) -> None:
        self.users: list[str] = []

    async def require_reset_password_permission(self, user_upn: str) -> None:
        self.users.append(user_upn)


class FakeAuditLogger(AuditLogger):
    def log_password_reset_event(self, tool_name: str, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_reset_password_first_call_only_creates_confirmation_state():
    password_service = FakePasswordResetService()
    runbook_service = FakeRunbookService()
    workflow = ResetPasswordWorkflow(
        settings=make_settings(),
        user_service=FakeUserService(),
        password_reset_service=password_service,
        runbook_service=runbook_service,
        workflow_store=WorkflowStore(),
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    response = await workflow.start("alice@example.com")

    assert response.success is True
    assert response.status == "pending_confirmation"
    assert response.confirmation_phrase == "CONFIRMO RESET SENHA alice@example.com"
    assert response.password_generated is False
    assert password_service.generated_passwords == []
    assert runbook_service.calls == []


@pytest.mark.asyncio
async def test_reset_password_start_reuses_existing_pending_workflow_for_same_user():
    password_service = FakePasswordResetService()
    runbook_service = FakeRunbookService()
    workflow = ResetPasswordWorkflow(
        settings=make_settings(),
        user_service=FakeUserService(),
        password_reset_service=password_service,
        runbook_service=runbook_service,
        workflow_store=WorkflowStore(),
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    first = await workflow.start("alice@example.com")
    second = await workflow.start("alice@example.com")

    assert second.success is True
    assert second.status == "pending_confirmation"
    assert second.reset_password_request_id == first.reset_password_request_id
    assert second.confirmation_phrase == "CONFIRMO RESET SENHA alice@example.com"
    assert password_service.generated_passwords == []
    assert runbook_service.calls == []


@pytest.mark.asyncio
async def test_reset_password_confirmation_generates_password_runs_runbook_and_decodes_output():
    password_service = FakePasswordResetService()
    runbook_service = FakeRunbookService()
    store = WorkflowStore()
    authorizer = FakeAuthorizer()
    workflow = ResetPasswordWorkflow(
        settings=make_settings(),
        user_service=FakeUserService(),
        password_reset_service=password_service,
        runbook_service=runbook_service,
        workflow_store=store,
        authorizer=authorizer,
        audit_logger=FakeAuditLogger(),
    )
    start = await workflow.start("alice@example.com")

    response = await workflow.execute(
        reset_password_request_id=start.reset_password_request_id or "",
        confirmation="CONFIRMO RESET SENHA alice@example.com",
    )

    assert response.success is True
    assert response.status == "completed"
    assert response.password_generated is True
    assert response.decoded_runbook_output == {"changed": True}
    assert response.temporary_password == password_service.generated_passwords[-1]
    assert len(password_service.generated_passwords) == 1
    assert runbook_service.calls[0]["parameters"] == {
        "UserPrincipalName": "alice@example.com",
        "TemporaryPassword": password_service.generated_passwords[-1],
    }
    assert authorizer.users == ["alice@example.com", "alice@example.com"]


@pytest.mark.asyncio
async def test_reset_password_can_execute_pending_workflow_from_user_upn_and_confirmation():
    password_service = FakePasswordResetService()
    runbook_service = FakeRunbookService()
    workflow = ResetPasswordWorkflow(
        settings=make_settings(),
        user_service=FakeUserService(),
        password_reset_service=password_service,
        runbook_service=runbook_service,
        workflow_store=WorkflowStore(),
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )
    await workflow.start("alice@example.com")

    response = await workflow.execute_by_user_upn(
        user_upn="alice@example.com",
        confirmation="CONFIRMO RESET SENHA alice@example.com",
    )

    assert response.success is True
    assert response.status == "completed"
    assert runbook_service.calls[0]["parameters"]["UserPrincipalName"] == "alice@example.com"
