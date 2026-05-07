from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.azure.automation_client import AzureAutomationError
from mcp_entraid.schemas.passwords import ResetPasswordResponse, ResetPasswordWorkflowState
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.password_reset_service import PasswordResetService
from mcp_entraid.services.runbook_service import RunbookService
from mcp_entraid.services.user_service import UserService
from mcp_entraid.settings import Settings
from mcp_entraid.utils.base64_utils import Base64OutputDecodeError, decode_base64_output
from mcp_entraid.workflows.workflow_store import WorkflowStore

STATUS_PENDING_CONFIRMATION = "pending_confirmation"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"

STEP_CONFIRMATION = "confirmation"
STEP_EXECUTE_RUNBOOK = "execute_runbook"


class ResetPasswordWorkflow:
    def __init__(
        self,
        settings: Settings,
        user_service: UserService,
        password_reset_service: PasswordResetService,
        runbook_service: RunbookService,
        workflow_store: WorkflowStore,
        authorizer: Authorizer,
        audit_logger: AuditLogger,
    ) -> None:
        self._settings = settings
        self._user_service = user_service
        self._password_reset_service = password_reset_service
        self._runbook_service = runbook_service
        self._workflow_store = workflow_store
        self._authorizer = authorizer
        self._audit_logger = audit_logger

    async def start(self, user_upn: str) -> ResetPasswordResponse:
        tool_name = "entra_reset_user_password"
        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            self._audit_logger.log_password_reset_event(
                tool_name=tool_name,
                user_upn=user_upn,
                status=STATUS_FAILED,
                confirmation_required=False,
                success=False,
                request_id=user_response.request_id,
            )
            return self._response(
                success=False,
                status=STATUS_FAILED,
                message=f"Falha ao validar usuario: {user_response.error}",
                request_id=user_response.request_id,
            )

        user = user_response.data
        user_principal_name = user.user_principal_name or user_upn.strip()
        await self._authorizer.require_reset_password_permission(user_principal_name)

        active_state = self._workflow_store.find_active_reset_password_state_by_upn(user_principal_name)
        if active_state is not None:
            return self._response_from_state(
                active_state,
                success=True,
                confirmation_required=True,
                confirmation_phrase=active_state.expected_confirmation_phrase,
                message=(
                    "Workflow de reset de senha ja iniciado para este usuario. "
                    f"Para continuar, confirme exatamente: {active_state.expected_confirmation_phrase}"
                ),
            )

        created_at = self._now_iso()
        expires_at = self._datetime_iso(
            datetime.now(timezone.utc) + timedelta(minutes=self._settings.password_reset_workflow_expiration_minutes)
        )
        reset_password_request_id = str(uuid4())
        confirmation_phrase = f"CONFIRMO RESET SENHA {user_principal_name}"
        state = ResetPasswordWorkflowState(
            reset_password_request_id=reset_password_request_id,
            user_id=user.user_id,
            user_principal_name=user_principal_name,
            user_display_name=user.display_name,
            expected_confirmation_phrase=confirmation_phrase,
            status=STATUS_PENDING_CONFIRMATION,
            current_step=STEP_CONFIRMATION,
            created_at=created_at,
            expires_at=expires_at,
            runbook_name=self._settings.password_reset_runbook_name,
            automation_job_name=None,
            automation_job_id=None,
        )
        self._workflow_store.save_reset_password_state(state)
        self._audit_logger.log_password_reset_event(
            tool_name=tool_name,
            reset_password_request_id=reset_password_request_id,
            user_upn=user_principal_name,
            status=STATUS_PENDING_CONFIRMATION,
            confirmation_required=True,
            success=True,
        )
        return self._response_from_state(
            state,
            success=True,
            confirmation_required=True,
            confirmation_phrase=confirmation_phrase,
            message=(
                f"O usuario {user_principal_name} foi localizado. Para continuar, confirme exatamente: "
                f"{confirmation_phrase}"
            ),
        )

    async def execute_by_user_upn(self, user_upn: str, confirmation: str) -> ResetPasswordResponse:
        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            return self._response(
                success=False,
                status=STATUS_FAILED,
                message=f"Falha ao validar usuario: {user_response.error}",
                request_id=user_response.request_id,
            )

        user_principal_name = user_response.data.user_principal_name or user_upn.strip()
        state = self._workflow_store.find_active_reset_password_state_by_upn(user_principal_name)
        if state is None:
            return self._response(
                success=False,
                status="not_found",
                user_id=user_response.data.user_id,
                user_principal_name=user_principal_name,
                user_display_name=user_response.data.display_name,
                message=(
                    "Nao encontrei um workflow pendente para este user_upn. "
                    "Inicie novamente o reset de senha informando apenas user_upn."
                ),
                request_id=user_response.request_id,
            )

        return await self.execute(
            reset_password_request_id=state.reset_password_request_id,
            confirmation=confirmation,
        )

    async def execute(self, reset_password_request_id: str, confirmation: str) -> ResetPasswordResponse:
        tool_name = "entra_reset_user_password"
        state = self._workflow_store.get_reset_password_state(reset_password_request_id)
        if state is None:
            return self._response(
                success=False,
                status="not_found",
                reset_password_request_id=reset_password_request_id,
                message="Workflow nao encontrado. Inicie novamente o reset de senha com user_upn.",
            )

        if self._workflow_store.is_reset_password_expired(state):
            state = self._workflow_store.mark_reset_password_expired(state)
            self._audit_logger.log_password_reset_event(
                tool_name=tool_name,
                reset_password_request_id=state.reset_password_request_id,
                user_upn=state.user_principal_name,
                status=STATUS_EXPIRED,
                confirmation_required=False,
                success=False,
            )
            return self._response_from_state(
                state,
                success=False,
                confirmation_required=False,
                message="Workflow expirado. Inicie novamente o reset de senha.",
            )

        if state.status != STATUS_PENDING_CONFIRMATION:
            return self._response_from_state(
                state,
                success=False,
                confirmation_required=False,
                message=f"Workflow esta com status {state.status} e nao aceita confirmacao.",
            )

        confirmation_matched = confirmation == state.expected_confirmation_phrase
        self._audit_logger.log_password_reset_event(
            tool_name=tool_name,
            reset_password_request_id=state.reset_password_request_id,
            user_upn=state.user_principal_name,
            status="confirmation_received",
            confirmation_required=True,
            confirmation_matched=confirmation_matched,
            success=confirmation_matched,
        )
        if not confirmation_matched:
            return self._response_from_state(
                state,
                success=False,
                confirmation_required=True,
                confirmation_phrase=state.expected_confirmation_phrase,
                message=f"Confirmacao invalida. Confirme exatamente: {state.expected_confirmation_phrase}",
            )

        await self._authorizer.require_reset_password_permission(state.user_principal_name)

        state.status = STATUS_RUNNING
        state.current_step = STEP_EXECUTE_RUNBOOK
        self._workflow_store.save_reset_password_state(state)

        password, _metadata = self._password_reset_service.generate_temporary_password()

        try:
            runbook_response = await self._run_password_reset_runbook(state, password)
        except AzureAutomationError as exc:
            state.status = STATUS_FAILED
            state.current_step = None
            self._workflow_store.save_reset_password_state(state)
            self._audit_logger.log_password_reset_event(
                tool_name=tool_name,
                reset_password_request_id=state.reset_password_request_id,
                user_upn=state.user_principal_name,
                status=STATUS_FAILED,
                password_generated=True,
                runbook_name=state.runbook_name,
                success=False,
            )
            return self._response_from_state(
                state,
                success=False,
                temporary_password=None,
                password_generated=True,
                message=str(exc),
            )

        state.automation_job_name = runbook_response.job_name
        state.automation_job_id = runbook_response.job_id
        state.status = (
            STATUS_COMPLETED
            if runbook_response.success
            else STATUS_RUNNING
            if runbook_response.timed_out
            else STATUS_FAILED
        )
        state.current_step = None
        self._workflow_store.save_reset_password_state(state)

        decoded_output = None
        if runbook_response.success:
            try:
                decoded_output = decode_base64_output(runbook_response.output)  # type: ignore[arg-type]
            except Base64OutputDecodeError as exc:
                state.status = STATUS_FAILED
                self._workflow_store.save_reset_password_state(state)
                return self._response_from_state(
                    state,
                    success=False,
                    temporary_password=self._temporary_password_for_response(password),
                    password_generated=True,
                    runbook_status=runbook_response.status,
                    message=str(exc),
                    request_id=runbook_response.request_id,
                )

        self._audit_logger.log_password_reset_event(
            tool_name=tool_name,
            reset_password_request_id=state.reset_password_request_id,
            user_upn=state.user_principal_name,
            status=state.status,
            password_generated=True,
            runbook_name=runbook_response.runbook_name,
            automation_job_name=runbook_response.job_name,
            automation_job_id=runbook_response.job_id,
            runbook_status=runbook_response.status,
            success=runbook_response.success,
            request_id=runbook_response.request_id,
        )
        return self._response_from_state(
            state,
            success=runbook_response.success,
            temporary_password=(
                self._temporary_password_for_response(password)
                if runbook_response.success
                else None
            ),
            password_generated=True,
            runbook_status=runbook_response.status,
            decoded_runbook_output=decoded_output,
            message=runbook_response.message,
            request_id=runbook_response.request_id,
        )

    async def _run_password_reset_runbook(self, state: ResetPasswordWorkflowState, password: str):
        runbook_name = self._settings.password_reset_runbook_name or ""
        if not runbook_name:
            raise AzureAutomationError("Runbook de reset de senha nao configurado.")
        return await self._runbook_service.execute_runbook(
            runbook_name=runbook_name,
            parameters={
                self._settings.password_reset_runbook_user_param: state.user_principal_name,
                self._settings.password_reset_runbook_password_param: password,
            },
            wait_for_completion=self._settings.password_reset_runbook_wait_for_completion,
            timeout_seconds=self._settings.password_reset_runbook_timeout_seconds,
        )

    def _temporary_password_for_response(self, password: str) -> str | None:
        if self._settings.password_reset_return_temporary_password:
            return password
        return None

    def _response_from_state(
        self,
        state: ResetPasswordWorkflowState,
        success: bool,
        message: str,
        confirmation_required: bool = False,
        confirmation_phrase: str | None = None,
        temporary_password: str | None = None,
        password_generated: bool = False,
        runbook_status: str | None = None,
        decoded_runbook_output=None,
        request_id: str | None = None,
    ) -> ResetPasswordResponse:
        return self._response(
            success=success,
            status=state.status,
            reset_password_request_id=state.reset_password_request_id,
            user_id=state.user_id,
            user_principal_name=state.user_principal_name,
            user_display_name=state.user_display_name,
            confirmation_required=confirmation_required,
            confirmation_phrase=confirmation_phrase,
            temporary_password=temporary_password,
            password_generated=password_generated,
            runbook_name=state.runbook_name,
            automation_job_name=state.automation_job_name,
            automation_job_id=state.automation_job_id,
            runbook_status=runbook_status,
            decoded_runbook_output=decoded_runbook_output,
            message=message,
            request_id=request_id,
        )

    def _response(
        self,
        success: bool,
        status: str,
        message: str,
        reset_password_request_id: str | None = None,
        user_id: str | None = None,
        user_principal_name: str | None = None,
        user_display_name: str | None = None,
        confirmation_required: bool = False,
        confirmation_phrase: str | None = None,
        temporary_password: str | None = None,
        password_generated: bool = False,
        runbook_name: str | None = None,
        automation_job_name: str | None = None,
        automation_job_id: str | None = None,
        runbook_status: str | None = None,
        decoded_runbook_output=None,
        request_id: str | None = None,
    ) -> ResetPasswordResponse:
        return ResetPasswordResponse(
            success=success,
            status=status,
            reset_password_request_id=reset_password_request_id,
            user_id=user_id,
            user_principal_name=user_principal_name,
            user_display_name=user_display_name,
            confirmation_required=confirmation_required,
            confirmation_phrase=confirmation_phrase,
            temporary_password=temporary_password,
            password_generated=password_generated,
            runbook_name=runbook_name,
            automation_job_name=automation_job_name,
            automation_job_id=automation_job_id,
            runbook_status=runbook_status,
            decoded_runbook_output=decoded_runbook_output,
            message=message,
            request_id=request_id,
        )

    def _now_iso(self) -> str:
        return self._datetime_iso(datetime.now(timezone.utc))

    def _datetime_iso(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
