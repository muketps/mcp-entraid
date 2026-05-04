from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.workflows.reset_mfa_workflow import ResetMfaWorkflow


def register_authentication_method_tools(
    mcp: FastMCP,
    reset_mfa_workflow: ResetMfaWorkflow,
) -> None:
    @mcp.tool
    async def entra_reset_user_mfa_start(user_upn: str) -> dict[str, Any]:
        """Inicia workflow guiado de reset MFA sem executar acoes destrutivas."""
        response = await reset_mfa_workflow.start(user_upn)
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_reset_user_mfa_execute_step(
        reset_request_id: str,
        step: str,
        confirmed: bool,
    ) -> dict[str, Any]:
        """Executa uma unica etapa confirmada do workflow de reset MFA."""
        response = await reset_mfa_workflow.execute_step(reset_request_id, step, confirmed)
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_reset_user_mfa_status(reset_request_id: str) -> dict[str, Any]:
        """Retorna o status atual do workflow de reset MFA."""
        response = await reset_mfa_workflow.status(reset_request_id)
        return response.model_dump(mode="json")
