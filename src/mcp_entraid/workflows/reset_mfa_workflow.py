from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.graph.errors import GraphAPIError
from mcp_entraid.schemas.authentication_methods import (
    AuthenticationMethodOperationResult,
    ResetMfaStartResponse,
    ResetMfaStatusResponse,
    ResetMfaStepResponse,
    ResetMfaWorkflowState,
)
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.authentication_method_service import AuthenticationMethodService
from mcp_entraid.services.user_service import UserService
from mcp_entraid.workflows.workflow_store import WorkflowStore

STEP_DELETE_AUTHENTICATION_METHODS = "delete_authentication_methods"
STEP_REVOKE_SESSIONS = "revoke_sessions"
STEP_CANCEL = "cancel"

STATUS_PENDING_CONFIRMATION = "pending_confirmation"
STATUS_CANCELLED = "cancelled"
STATUS_COMPLETED = "completed"
STATUS_EXPIRED = "expired"

VALID_STEPS = {
    STEP_DELETE_AUTHENTICATION_METHODS,
    STEP_REVOKE_SESSIONS,
    STEP_CANCEL,
}


class ResetMfaWorkflow:
    def __init__(
        self,
        user_service: UserService,
        authentication_method_service: AuthenticationMethodService,
        workflow_store: WorkflowStore,
        authorizer: Authorizer,
        audit_logger: AuditLogger,
    ) -> None:
        self._user_service = user_service
        self._authentication_method_service = authentication_method_service
        self._workflow_store = workflow_store
        self._authorizer = authorizer
        self._audit_logger = audit_logger

    async def start(self, user_upn: str) -> ResetMfaStartResponse:
        tool_name = "entra_reset_user_mfa_start"
        await self._authorizer.require_reset_mfa_permission()
        self._audit_logger.log_workflow_event(tool_name, target_user=user_upn, status="start_requested")

        active_state = self._workflow_store.find_active_reset_mfa_state_by_upn(user_upn)
        if active_state is not None:
            return self._start_from_state(
                active_state,
                confirmation_message=(
                    "Workflow de reset MFA ja iniciado para este usuario. "
                    f"Para confirmar a proxima etapa, chame entra_reset_mfa com action='confirm' e user_upn='{active_state.user_principal_name}'."
                ),
            )

        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            self._audit_logger.log_workflow_event(
                tool_name,
                target_user=user_upn,
                status="failed",
                request_id=user_response.request_id,
            )
            return ResetMfaStartResponse(
                success=False,
                reset_request_id="",
                user_upn="",
                user_display_name=None,
                phone_methods=[],
                mfa_methods=[],
                phone_methods_found=0,
                mfa_methods_found=0,
                current_step="",
                confirmation_required=False,
                confirmation_message=f"Falha ao validar usuario: {user_response.error}",
                expires_at="",
                request_id=user_response.request_id,
            )

        user = user_response.data
        user_display_name = user.display_name
        user_principal_name = user.user_principal_name or ""
        user_id = user.user_id

        try:
            phone_methods = await self._authentication_method_service.list_phone_methods(user_id)
            mfa_methods = await self._authentication_method_service.list_microsoft_authenticator_methods(user_id)
        except GraphAPIError as exc:
            self._audit_logger.log_workflow_event(
                tool_name,
                target_user=user_id,
                status="failed",
                request_id=exc.request_id,
            )
            return ResetMfaStartResponse(
                success=False,
                reset_request_id="",
                user_upn=user_principal_name,
                user_display_name=user_display_name,
                phone_methods=[],
                mfa_methods=[],
                phone_methods_found=0,
                mfa_methods_found=0,
                current_step="",
                confirmation_required=False,
                confirmation_message=str(exc),
                expires_at="",
                request_id=exc.request_id,
            )

        created_at = self._now_iso()
        expires_at = self._datetime_iso(datetime.now(timezone.utc) + timedelta(minutes=15))
        reset_request_id = str(uuid4())
        state = ResetMfaWorkflowState(
            reset_request_id=reset_request_id,
            user_id=user_id,
            user_principal_name=user_principal_name,
            user_display_name=user_display_name,
            phone_methods=phone_methods,
            mfa_methods=mfa_methods,
            status=STATUS_PENDING_CONFIRMATION,
            current_step=STEP_DELETE_AUTHENTICATION_METHODS,
            completed_steps=[],
            deleted_phone_methods=[],
            deleted_mfa_methods=[],
            failed_methods=[],
            sessions_revoked=False,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._workflow_store.save_reset_mfa_state(state)

        self._audit_logger.log_workflow_event(
            tool_name,
            reset_request_id=reset_request_id,
            target_user=user_id,
            step=STEP_DELETE_AUTHENTICATION_METHODS,
            phone_methods_found=len(phone_methods),
            mfa_methods_found=len(mfa_methods),
            status=state.status,
        )

        return ResetMfaStartResponse(
            success=True,
            reset_request_id=reset_request_id,
            user_upn=user_principal_name,
            user_display_name=user_display_name,
            phone_methods=phone_methods,
            mfa_methods=mfa_methods,
            phone_methods_found=len(phone_methods),
            mfa_methods_found=len(mfa_methods),
            current_step=state.current_step or "",
            confirmation_required=True,
            confirmation_message=self._start_confirmation_message(
                user_label=user_display_name or user_principal_name or user_upn,
                phone_methods=phone_methods,
                mfa_methods=mfa_methods,
            ),
            expires_at=expires_at,
            request_id=None,
        )

    async def confirm_next_step(self, user_upn: str) -> ResetMfaStepResponse:
        tool_name = "entra_reset_mfa"
        await self._authorizer.require_reset_mfa_permission()

        state = self._workflow_store.find_active_reset_mfa_state_by_upn(user_upn)
        if state is None:
            return self._step_error("", "Workflow nao encontrado para este user_upn. Inicie novamente o reset de MFA.")

        if self._workflow_store.is_expired(state):
            state = self._workflow_store.mark_expired(state)
            self._audit_logger.log_workflow_event(
                tool_name,
                reset_request_id=state.reset_request_id,
                target_user=state.user_id,
                status=STATUS_EXPIRED,
            )
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=None,
                confirmation_required=False,
                confirmation_message=None,
                message="Workflow expirado. Inicie novamente o reset de MFA.",
            )

        if not state.current_step:
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=None,
                confirmation_required=False,
                confirmation_message=None,
                message=f"Workflow esta com status {state.status} e nao possui etapa pendente.",
            )

        return await self.execute_step(
            reset_request_id=state.reset_request_id,
            step=state.current_step,
            confirmed=True,
        )

    async def execute_step(
        self,
        reset_request_id: str,
        step: str,
        confirmed: bool,
    ) -> ResetMfaStepResponse:
        tool_name = "entra_reset_user_mfa_execute_step"
        await self._authorizer.require_reset_mfa_permission()

        if step not in VALID_STEPS:
            return self._step_error(reset_request_id, "Etapa invalida.")

        state = self._workflow_store.get_reset_mfa_state(reset_request_id)
        if state is None:
            return self._step_error(reset_request_id, "Workflow nao encontrado. Inicie novamente o reset de MFA.")

        if self._workflow_store.is_expired(state):
            state = self._workflow_store.mark_expired(state)
            self._audit_logger.log_workflow_event(
                tool_name,
                reset_request_id=reset_request_id,
                target_user=state.user_id,
                step=step,
                confirmed=confirmed,
                status=STATUS_EXPIRED,
            )
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=None,
                confirmation_required=False,
                confirmation_message=None,
                message="Workflow expirado. Inicie novamente o reset de MFA.",
            )

        if step == STEP_CANCEL or not confirmed:
            state.status = STATUS_CANCELLED
            state.current_step = None
            self._workflow_store.save_reset_mfa_state(state)
            self._audit_logger.log_workflow_event(
                tool_name,
                reset_request_id=reset_request_id,
                target_user=state.user_id,
                step=step,
                confirmed=confirmed,
                status=STATUS_CANCELLED,
            )
            return self._step_from_state(
                state,
                success=True,
                step_completed=STEP_CANCEL,
                next_step=None,
                confirmation_required=False,
                confirmation_message=None,
                message="Workflow de reset MFA cancelado.",
            )

        if state.status in {STATUS_COMPLETED, STATUS_CANCELLED, STATUS_EXPIRED}:
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=state.current_step,
                confirmation_required=False,
                confirmation_message=None,
                message=f"Workflow esta com status {state.status} e nao aceita novas etapas.",
            )

        if state.current_step != step:
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=state.current_step,
                confirmation_required=True,
                confirmation_message=self._confirmation_for_step(state.current_step),
                message=f"Etapa fora de ordem. Proxima etapa esperada: {state.current_step}.",
            )

        self._audit_logger.log_workflow_event(
            tool_name,
            reset_request_id=reset_request_id,
            target_user=state.user_id,
            step=step,
            confirmed=confirmed,
            status="confirmed",
        )

        if step == STEP_DELETE_AUTHENTICATION_METHODS:
            return await self._execute_delete_authentication_methods(state)
        if step == STEP_REVOKE_SESSIONS:
            return await self._execute_revoke_sessions(state)

        return self._step_error(reset_request_id, "Etapa nao suportada.")

    async def status(self, reset_request_id: str) -> ResetMfaStatusResponse:
        tool_name = "entra_reset_user_mfa_status"
        await self._authorizer.require_reset_mfa_permission()
        state = self._workflow_store.get_reset_mfa_state(reset_request_id)
        if state is None:
            return ResetMfaStatusResponse(
                success=False,
                reset_request_id=reset_request_id,
                user_upn="",
                user_display_name=None,
                status="not_found",
                current_step=None,
                completed_steps=[],
                failed_methods=[],
                deleted_phone_methods=[],
                deleted_mfa_methods=[],
                sessions_revoked=False,
                expires_at="",
                message="Workflow nao encontrado. Inicie novamente o reset de MFA.",
                request_id=None,
            )

        if self._workflow_store.is_expired(state):
            state = self._workflow_store.mark_expired(state)
            self._audit_logger.log_workflow_event(
                tool_name,
                reset_request_id=reset_request_id,
                target_user=state.user_id,
                status=STATUS_EXPIRED,
            )

        return self._status_from_state(
            state,
            success=state.status != STATUS_EXPIRED,
            message=(
                "Workflow expirado. Inicie novamente o reset de MFA."
                if state.status == STATUS_EXPIRED
                else "Status do workflow de reset MFA retornado."
            ),
        )

    async def _execute_delete_authentication_methods(
        self,
        state: ResetMfaWorkflowState,
    ) -> ResetMfaStepResponse:
        deleted_phone_methods: list[AuthenticationMethodOperationResult] = []
        deleted_mfa_methods: list[AuthenticationMethodOperationResult] = []
        failed_methods: list[AuthenticationMethodOperationResult] = []

        for method in state.phone_methods:
            result = await self._authentication_method_service.delete_phone_method(state.user_id, method)
            if result.status == "deleted":
                deleted_phone_methods.append(result)
            else:
                failed_methods.append(result)

        for method in state.mfa_methods:
            result = await self._authentication_method_service.delete_microsoft_authenticator_method(
                state.user_id,
                method,
            )
            if result.status == "deleted":
                deleted_mfa_methods.append(result)
            else:
                failed_methods.append(result)

        state.deleted_phone_methods.extend(deleted_phone_methods)
        state.deleted_mfa_methods.extend(deleted_mfa_methods)
        state.failed_methods.extend(failed_methods)
        self._audit_logger.log_workflow_event(
            "entra_reset_user_mfa_execute_step",
            reset_request_id=state.reset_request_id,
            target_user=state.user_id,
            step=STEP_DELETE_AUTHENTICATION_METHODS,
            confirmed=True,
            deleted_phone_count=len(deleted_phone_methods),
            deleted_mfa_count=len(deleted_mfa_methods),
            failed_count=len(failed_methods),
            status=state.status,
        )

        sessions_revoke_failed = False
        request_id = None
        revoke_error_message = None
        try:
            state.sessions_revoked = await self._authentication_method_service.revoke_sign_in_sessions(
                state.user_id
            )
        except GraphAPIError as exc:
            sessions_revoke_failed = True
            request_id = exc.request_id
            revoke_error_message = str(exc)
            self._audit_logger.log_workflow_event(
                "entra_reset_user_mfa_execute_step",
                reset_request_id=state.reset_request_id,
                target_user=state.user_id,
                step=STEP_REVOKE_SESSIONS,
                confirmed=True,
                failed_count=1,
                sessions_revoked=False,
                status="failed",
                request_id=exc.request_id,
            )

        state.completed_steps.append(STEP_DELETE_AUTHENTICATION_METHODS)
        if state.sessions_revoked:
            state.completed_steps.append(STEP_REVOKE_SESSIONS)

        state.current_step = None
        state.status = STATUS_COMPLETED if not sessions_revoke_failed else STATUS_PENDING_CONFIRMATION
        self._workflow_store.save_reset_mfa_state(state)

        success = len(failed_methods) == 0 and not sessions_revoke_failed
        message = self._completion_message(state.sessions_revoked)
        if failed_methods:
            message = "Metodos de telefone e MFA processados com falhas parciais. " + message
        if sessions_revoke_failed:
            message = f"Metodos de telefone e MFA processados, mas nao foi possivel revogar sessoes: {revoke_error_message}"

        return ResetMfaStepResponse(
            success=success,
            reset_request_id=state.reset_request_id,
            user_upn=state.user_principal_name,
            user_display_name=state.user_display_name,
            step_completed=STEP_DELETE_AUTHENTICATION_METHODS,
            next_step=None,
            deleted_phone_methods=deleted_phone_methods,
            deleted_mfa_methods=deleted_mfa_methods,
            failed_methods=failed_methods,
            sessions_revoked=state.sessions_revoked,
            confirmation_required=False,
            confirmation_message=None,
            status=state.status,
            message=message,
            request_id=request_id,
        )

    async def _execute_revoke_sessions(self, state: ResetMfaWorkflowState) -> ResetMfaStepResponse:
        try:
            state.sessions_revoked = await self._authentication_method_service.revoke_sign_in_sessions(
                state.user_id
            )
        except GraphAPIError as exc:
            self._audit_logger.log_workflow_event(
                "entra_reset_user_mfa_execute_step",
                reset_request_id=state.reset_request_id,
                target_user=state.user_id,
                step=STEP_REVOKE_SESSIONS,
                confirmed=True,
                failed_count=1,
                sessions_revoked=False,
                status="failed",
                request_id=exc.request_id,
            )
            return self._step_from_state(
                state,
                success=False,
                step_completed=None,
                next_step=STEP_REVOKE_SESSIONS,
                confirmation_required=True,
                confirmation_message=self._confirmation_for_step(STEP_REVOKE_SESSIONS),
                message=str(exc),
                request_id=exc.request_id,
            )

        state.completed_steps.append(STEP_REVOKE_SESSIONS)
        state.current_step = None
        state.status = STATUS_COMPLETED
        self._workflow_store.save_reset_mfa_state(state)

        self._audit_logger.log_workflow_event(
            "entra_reset_user_mfa_execute_step",
            reset_request_id=state.reset_request_id,
            target_user=state.user_id,
            step=STEP_REVOKE_SESSIONS,
            confirmed=True,
            sessions_revoked=state.sessions_revoked,
            status=state.status,
        )

        return self._step_from_state(
            state,
            success=True,
            step_completed=STEP_REVOKE_SESSIONS,
            next_step=None,
            confirmation_required=False,
            confirmation_message=None,
            message="Reset MFA concluido.",
        )

    def _step_error(self, reset_request_id: str, message: str) -> ResetMfaStepResponse:
        return ResetMfaStepResponse(
            success=False,
            reset_request_id=reset_request_id,
            user_upn="",
            user_display_name=None,
            step_completed=None,
            next_step=None,
            deleted_phone_methods=[],
            deleted_mfa_methods=[],
            failed_methods=[],
            sessions_revoked=False,
            confirmation_required=False,
            confirmation_message=None,
            status="invalid_step",
            message=message,
            request_id=None,
        )

    def _start_from_state(
        self,
        state: ResetMfaWorkflowState,
        confirmation_message: str,
    ) -> ResetMfaStartResponse:
        return ResetMfaStartResponse(
            success=True,
            reset_request_id=state.reset_request_id,
            user_upn=state.user_principal_name,
            user_display_name=state.user_display_name,
            phone_methods=state.phone_methods,
            mfa_methods=state.mfa_methods,
            phone_methods_found=len(state.phone_methods),
            mfa_methods_found=len(state.mfa_methods),
            current_step=state.current_step or "",
            confirmation_required=state.current_step is not None,
            confirmation_message=confirmation_message,
            expires_at=state.expires_at,
            request_id=None,
        )

    def _step_from_state(
        self,
        state: ResetMfaWorkflowState,
        success: bool,
        step_completed: str | None,
        next_step: str | None,
        confirmation_required: bool,
        confirmation_message: str | None,
        message: str,
        request_id: str | None = None,
    ) -> ResetMfaStepResponse:
        return ResetMfaStepResponse(
            success=success,
            reset_request_id=state.reset_request_id,
            user_upn=state.user_principal_name,
            user_display_name=state.user_display_name,
            step_completed=step_completed,
            next_step=next_step,
            deleted_phone_methods=state.deleted_phone_methods,
            deleted_mfa_methods=state.deleted_mfa_methods,
            failed_methods=state.failed_methods,
            sessions_revoked=state.sessions_revoked,
            confirmation_required=confirmation_required,
            confirmation_message=confirmation_message,
            status=state.status,
            message=message,
            request_id=request_id,
        )

    def _status_from_state(
        self,
        state: ResetMfaWorkflowState,
        success: bool,
        message: str,
        request_id: str | None = None,
    ) -> ResetMfaStatusResponse:
        return ResetMfaStatusResponse(
            success=success,
            reset_request_id=state.reset_request_id,
            user_upn=state.user_principal_name,
            user_display_name=state.user_display_name,
            status=state.status,
            current_step=state.current_step,
            completed_steps=state.completed_steps,
            failed_methods=state.failed_methods,
            deleted_phone_methods=state.deleted_phone_methods,
            deleted_mfa_methods=state.deleted_mfa_methods,
            sessions_revoked=state.sessions_revoked,
            expires_at=state.expires_at,
            message=message,
            request_id=request_id,
        )

    def _confirmation_for_step(self, step: str | None) -> str | None:
        if step == STEP_DELETE_AUTHENTICATION_METHODS:
            return "Deseja continuar e remover os metodos de telefone e MFA?"
        if step == STEP_REVOKE_SESSIONS:
            return "Metodos de telefone e MFA processados. Deseja revogar as sessoes do usuario agora para exigir novo login?"
        return None

    def _start_confirmation_message(
        self,
        user_label: str,
        phone_methods,
        mfa_methods,
    ) -> str:
        phone_summary = ", ".join(
            f"{method.display_name or method.phone_type or method.type}"
            f" ({method.phone_number_masked})" if method.phone_number_masked else method.display_name or method.phone_type or method.type
            for method in phone_methods
        ) or "nenhum telefone cadastrado"
        mfa_summary = ", ".join(
            method.display_name or method.type
            for method in mfa_methods
        ) or "nenhum Microsoft Authenticator/MFA cadastrado"
        return (
            f"O usuario {user_label} possui telefone(s): {phone_summary}. "
            f"MFA cadastrado(s): {mfa_summary}. "
            "Deseja continuar e remover esses metodos?"
        )

    def _completion_message(self, sessions_revoked: bool) -> str:
        if sessions_revoked:
            return (
                "Pronto! O MFA foi removido com sucesso. Nos próximos minutos, suas aplicações Microsoft "
                "pedirão que você cadastre novamente a autenticação multifator. Siga as orientações exibidas "
                "na tela para concluir o processo."
            )
        return (
            "Pronto! O MFA foi removido com sucesso. Siga as orientações exibidas na tela para cadastrar "
            "novamente a autenticação multifator."
        )

    def _now_iso(self) -> str:
        return self._datetime_iso(datetime.now(timezone.utc))

    def _datetime_iso(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
