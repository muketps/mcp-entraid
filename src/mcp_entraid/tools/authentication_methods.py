from __future__ import annotations

from typing import Any
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.schemas.authentication_methods import ListAuthenticationMethodsResponse
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.authentication_method_service import AuthenticationMethodService
from mcp_entraid.services.user_service import UserService
from mcp_entraid.workflows.reset_mfa_workflow import ResetMfaWorkflow


def register_authentication_method_tools(
    mcp: FastMCP,
    user_service: UserService,
    authentication_method_service: AuthenticationMethodService,
    reset_mfa_workflow: ResetMfaWorkflow,
    authorizer: Authorizer,
    audit_logger: AuditLogger | None = None,
) -> None:
    async def _resolve_user(user_upn: str) -> tuple[str, str, str | None]:
        user_response = await user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            raise ValueError(f"Falha ao validar usuario: {user_response.error}")

        user = user_response.data
        return user.user_id, user.user_principal_name or "", user.display_name

    @mcp.tool
    async def entra_list_phone_methods(user_upn: str) -> dict[str, Any]:
        await authorizer.require_reset_mfa_permission()
        if audit_logger is not None:
            audit_logger.log_workflow_event(
                "entra_list_phone_methods",
                target_user=user_upn,
                status="requested",
            )
        try:
            user_id, normalized_user_upn, user_display_name = await _resolve_user(user_upn)
            methods = await authentication_method_service.list_phone_methods(user_id)
        except ValueError as exc:
            return {
                "success": False,
                "user_upn": "",
                "user_id": "",
                "user_display_name": None,
                "methods_kind": "phone",
                "methods_count": 0,
                "methods": [],
                "message": str(exc),
                "request_id": None,
            }

        if audit_logger is not None:
            audit_logger.log_workflow_event(
                "entra_list_phone_methods",
                target_user=user_id,
                phone_methods_found=len(methods),
                status="success",
            )

        response = ListAuthenticationMethodsResponse(
            success=True,
            user_upn=normalized_user_upn,
            user_id=user_id,
            user_display_name=user_display_name,
            methods_kind="phone",
            methods_count=len(methods),
            methods=methods,
            message="Metodos de telefone retornados com sucesso.",
            request_id=None,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_list_microsoft_authenticator_methods(user_upn: str) -> dict[str, Any]:
        await authorizer.require_reset_mfa_permission()
        if audit_logger is not None:
            audit_logger.log_workflow_event(
                "entra_list_microsoft_authenticator_methods",
                target_user=user_upn,
                status="requested",
            )
        try:
            user_id, normalized_user_upn, user_display_name = await _resolve_user(user_upn)
            methods = await authentication_method_service.list_microsoft_authenticator_methods(user_id)
        except ValueError as exc:
            return {
                "success": False,
                "user_upn": "",
                "user_id": "",
                "user_display_name": None,
                "methods_kind": "microsoft_authenticator",
                "methods_count": 0,
                "methods": [],
                "message": str(exc),
                "request_id": None,
            }

        if audit_logger is not None:
            audit_logger.log_workflow_event(
                "entra_list_microsoft_authenticator_methods",
                target_user=user_id,
                mfa_methods_found=len(methods),
                status="success",
            )

        response = ListAuthenticationMethodsResponse(
            success=True,
            user_upn=normalized_user_upn,
            user_id=user_id,
            user_display_name=user_display_name,
            methods_kind="microsoft_authenticator",
            methods_count=len(methods),
            methods=methods,
            message="Metodos Microsoft Authenticator retornados com sucesso.",
            request_id=None,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_reset_mfa(
        action: Annotated[
            Literal["start", "confirm", "status"],
            Field(
                description=(
                    "Use start para iniciar. Quando o usuario confirmar depois do start, use confirm com user_upn. "
                    "Use status apenas se voce ja tiver reset_request_id."
                )
            ),
        ],
        user_upn: Annotated[
            str | None,
            Field(description="UPN do usuario. Obrigatorio para action=start e action=confirm."),
        ] = None,
        reset_request_id: Annotated[
            str | None,
            Field(description="ID do workflow. Necessario somente para action=status."),
        ] = None,
    ) -> dict[str, Any]:
        """Ponto unico do workflow guiado de reset MFA: start, confirm ou status."""
        if action == "start":
            if not user_upn:
                return {
                    "success": False,
                    "message": "Informe user_upn para iniciar o reset MFA.",
                }
            response = await reset_mfa_workflow.start(user_upn)
            return response.model_dump(mode="json")

        if action == "confirm":
            if not user_upn:
                return {
                    "success": False,
                    "message": "Informe user_upn para confirmar a proxima etapa do reset MFA.",
                }
            response = await reset_mfa_workflow.confirm_next_step(user_upn)
            return response.model_dump(mode="json")

        if action == "status":
            if not reset_request_id:
                return {
                    "success": False,
                    "message": "Informe reset_request_id para consultar o status do reset MFA.",
                }
            response = await reset_mfa_workflow.status(reset_request_id)
            return response.model_dump(mode="json")

        return {
            "success": False,
            "message": "Acao invalida para o reset MFA.",
        }
