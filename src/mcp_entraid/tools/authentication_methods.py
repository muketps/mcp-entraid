from __future__ import annotations

from typing import Any
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from mcp_entraid.workflows.reset_mfa_workflow import ResetMfaWorkflow


def register_authentication_method_tools(
    mcp: FastMCP,
    reset_mfa_workflow: ResetMfaWorkflow,
) -> None:
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
