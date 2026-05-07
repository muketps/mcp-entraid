from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.workflows.reset_password_workflow import ResetPasswordWorkflow


def register_password_tools(mcp: FastMCP, reset_password_workflow: ResetPasswordWorkflow) -> None:
    @mcp.tool
    async def entra_reset_user_password(
        user_upn: str | None = None,
        reset_password_request_id: str | None = None,
        confirmation: str | None = None,
    ) -> dict[str, Any]:
        if user_upn and reset_password_request_id:
            return _error("Use uma etapa por vez: inicie com user_upn ou confirme com reset_password_request_id.")
        if confirmation and user_upn:
            response = await reset_password_workflow.execute_by_user_upn(
                user_upn=user_upn,
                confirmation=confirmation,
            )
            return response.model_dump(mode="json")
        if confirmation and not reset_password_request_id:
            return _error("confirmation precisa vir com reset_password_request_id ou user_upn.")
        if reset_password_request_id and not confirmation:
            return _error("Informe a frase de confirmacao para executar o reset de senha.")
        if not user_upn and not reset_password_request_id:
            return _error("Inicie o reset de senha informando user_upn.")
        if user_upn:
            response = await reset_password_workflow.start(user_upn)
            return response.model_dump(mode="json")

        response = await reset_password_workflow.execute(
            reset_password_request_id=reset_password_request_id or "",
            confirmation=confirmation or "",
        )
        return response.model_dump(mode="json")


def _error(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "status": "invalid_request",
        "reset_password_request_id": None,
        "user_id": None,
        "user_principal_name": None,
        "user_display_name": None,
        "confirmation_required": False,
        "confirmation_phrase": None,
        "temporary_password": None,
        "password_generated": False,
        "runbook_name": None,
        "automation_job_name": None,
        "automation_job_id": None,
        "runbook_status": None,
        "decoded_runbook_output": None,
        "message": message,
        "request_id": None,
    }
