import pytest

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.schemas.authentication_methods import (
    AuthenticationMethodOperationResult,
    AuthenticationMethodSummary,
)
from mcp_entraid.schemas.common import ToolResponse
from mcp_entraid.schemas.users import EntraUser
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.workflows.reset_mfa_workflow import (
    STEP_DELETE_AUTHENTICATION_METHODS,
    STEP_REVOKE_SESSIONS,
    ResetMfaWorkflow,
)
from mcp_entraid.workflows.workflow_store import WorkflowStore


class FakeUserService:
    async def get_user(self, user_upn: str) -> ToolResponse[EntraUser]:
        return ToolResponse[EntraUser](
            success=True,
            data=EntraUser(
                user_id="user-123",
                user_display_name="Alice Silva",
                user_principal_name=user_upn,
            ),
        )


class FakeAuthenticationMethodService:
    def __init__(self) -> None:
        self.phone_methods = [
            AuthenticationMethodSummary(
                id="phone-1",
                type="phoneMethod",
                display_name="mobile",
                phone_type="mobile",
                phone_number_masked="***-1234",
            )
        ]
        self.mfa_methods = [
            AuthenticationMethodSummary(
                id="mfa-1",
                type="microsoftAuthenticatorMethod",
                display_name="Microsoft Authenticator",
            )
        ]
        self.deleted_phone_ids: list[str] = []
        self.deleted_mfa_ids: list[str] = []
        self.sessions_revoked = False
        self.fail_mfa_delete = False

    async def list_phone_methods(self, user_id: str) -> list[AuthenticationMethodSummary]:
        return self.phone_methods

    async def list_microsoft_authenticator_methods(
        self,
        user_id: str,
    ) -> list[AuthenticationMethodSummary]:
        return self.mfa_methods

    async def delete_phone_method(
        self,
        user_id: str,
        method: AuthenticationMethodSummary,
    ) -> AuthenticationMethodOperationResult:
        self.deleted_phone_ids.append(method.id)
        return AuthenticationMethodOperationResult(
            id=method.id,
            type=method.type,
            display_name=method.display_name,
            status="deleted",
        )

    async def delete_microsoft_authenticator_method(
        self,
        user_id: str,
        method: AuthenticationMethodSummary,
    ) -> AuthenticationMethodOperationResult:
        self.deleted_mfa_ids.append(method.id)
        if self.fail_mfa_delete:
            return AuthenticationMethodOperationResult(
                id=method.id,
                type=method.type,
                display_name=method.display_name,
                status="failed",
                reason="Metodo MFA padrao nao pode ser removido.",
            )
        return AuthenticationMethodOperationResult(
            id=method.id,
            type=method.type,
            display_name=method.display_name,
            status="deleted",
        )

    async def revoke_sign_in_sessions(self, user_id: str) -> bool:
        self.sessions_revoked = True
        return True


class CapturingAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.events: list[dict] = []

    def log_workflow_event(self, tool_name: str, **kwargs) -> None:
        self.events.append({"tool_name": tool_name, **kwargs})


def make_workflow(authentication_method_service: FakeAuthenticationMethodService):
    audit_logger = CapturingAuditLogger()
    workflow = ResetMfaWorkflow(
        user_service=FakeUserService(),
        authentication_method_service=authentication_method_service,
        workflow_store=WorkflowStore(),
        authorizer=Authorizer(),
        audit_logger=audit_logger,
    )
    return workflow, audit_logger


@pytest.mark.asyncio
async def test_reset_mfa_start_never_deletes_or_revokes():
    authentication_methods = FakeAuthenticationMethodService()
    workflow, _ = make_workflow(authentication_methods)

    response = await workflow.start("alice@example.com")
    payload = response.model_dump(mode="json")

    assert response.success is True
    assert response.user_upn == "alice@example.com"
    assert "user_id" not in payload
    assert "user_principal_name" not in payload
    assert response.current_step == STEP_DELETE_AUTHENTICATION_METHODS
    assert response.phone_methods_found == 1
    assert response.mfa_methods_found == 1
    assert "***-1234" in response.confirmation_message
    assert "Microsoft Authenticator" in response.confirmation_message
    assert response.confirmation_required is True
    assert authentication_methods.deleted_phone_ids == []
    assert authentication_methods.deleted_mfa_ids == []
    assert authentication_methods.sessions_revoked is False


@pytest.mark.asyncio
async def test_reset_mfa_start_is_idempotent_while_workflow_is_active():
    authentication_methods = FakeAuthenticationMethodService()
    workflow, _ = make_workflow(authentication_methods)

    first = await workflow.start("alice@example.com")
    second = await workflow.start("alice@example.com")

    assert second.reset_request_id == first.reset_request_id
    assert second.current_step == STEP_DELETE_AUTHENTICATION_METHODS
    assert "ja iniciado" in second.confirmation_message


@pytest.mark.asyncio
async def test_reset_mfa_confirm_next_step_uses_active_workflow_by_upn():
    authentication_methods = FakeAuthenticationMethodService()
    workflow, _ = make_workflow(authentication_methods)
    start = await workflow.start("alice@example.com")

    response = await workflow.confirm_next_step("alice@example.com")

    assert response.success is True
    assert response.reset_request_id == start.reset_request_id
    assert response.step_completed == STEP_DELETE_AUTHENTICATION_METHODS
    assert response.next_step is None
    assert response.confirmation_required is False
    assert response.sessions_revoked is True
    assert "Pronto! O MFA foi removido com sucesso." in response.message
    assert authentication_methods.deleted_phone_ids == ["phone-1"]
    assert authentication_methods.deleted_mfa_ids == ["mfa-1"]


@pytest.mark.asyncio
async def test_reset_mfa_rejects_revoke_sessions_before_delete_step():
    authentication_methods = FakeAuthenticationMethodService()
    workflow, _ = make_workflow(authentication_methods)
    start = await workflow.start("alice@example.com")

    response = await workflow.execute_step(start.reset_request_id, STEP_REVOKE_SESSIONS, True)

    assert response.success is False
    assert response.next_step == STEP_DELETE_AUTHENTICATION_METHODS
    assert authentication_methods.sessions_revoked is False


@pytest.mark.asyncio
async def test_reset_mfa_delete_step_continues_after_individual_failure():
    authentication_methods = FakeAuthenticationMethodService()
    authentication_methods.fail_mfa_delete = True
    workflow, _ = make_workflow(authentication_methods)
    start = await workflow.start("alice@example.com")

    response = await workflow.execute_step(
        start.reset_request_id,
        STEP_DELETE_AUTHENTICATION_METHODS,
        True,
    )

    assert response.success is False
    assert response.next_step is None
    assert response.deleted_phone_methods[0].id == "phone-1"
    assert response.failed_methods[0].id == "mfa-1"
    assert response.sessions_revoked is True
    assert response.confirmation_required is False
    assert authentication_methods.sessions_revoked is True


@pytest.mark.asyncio
async def test_reset_mfa_delete_step_revokes_sessions_and_completes_workflow():
    authentication_methods = FakeAuthenticationMethodService()
    workflow, _ = make_workflow(authentication_methods)
    start = await workflow.start("alice@example.com")
    response = await workflow.execute_step(start.reset_request_id, STEP_DELETE_AUTHENTICATION_METHODS, True)
    status = await workflow.status(start.reset_request_id)
    response_payload = response.model_dump(mode="json")
    status_payload = status.model_dump(mode="json")

    assert response.success is True
    assert response.user_upn == "alice@example.com"
    assert status.user_upn == "alice@example.com"
    assert "user_id" not in response_payload
    assert "user_principal_name" not in response_payload
    assert "user_id" not in status_payload
    assert "user_principal_name" not in status_payload
    assert "suas aplicações Microsoft pedirão que você cadastre novamente" in response.message
    assert response.sessions_revoked is True
    assert status.status == "completed"
    assert status.sessions_revoked is True
