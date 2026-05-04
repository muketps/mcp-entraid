from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.security.permissions import ENTRA_DIRECT_REPORTS_READ, ENTRA_USER_READ
from mcp_entraid.services.user_service import UserService


def register_user_tools(
    mcp: FastMCP,
    user_service: UserService,
    authorizer: Authorizer,
    audit_logger: AuditLogger,
) -> None:
    @mcp.tool
    async def entra_get_user(user_upn: str) -> dict[str, Any]:
        """Retorna dados padronizados de um usuario do Microsoft Entra ID."""
        audit_logger.log_tool_call("entra_get_user", {"user_upn": user_upn})
        await authorizer.authorize(ENTRA_USER_READ)
        response = await user_service.get_user(user_upn)
        audit_logger.log_tool_result(
            "entra_get_user",
            success=response.success,
            request_id=response.request_id,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_get_direct_reports(user_upn: str) -> dict[str, Any]:
        """Retorna os subordinados diretos de um usuario do Microsoft Entra ID."""
        audit_logger.log_tool_call("entra_get_direct_reports", {"user_upn": user_upn})
        await authorizer.authorize(ENTRA_DIRECT_REPORTS_READ)
        response = await user_service.get_direct_reports(user_upn)
        audit_logger.log_tool_result(
            "entra_get_direct_reports",
            success=response.success,
            request_id=response.request_id,
        )
        return response.model_dump(mode="json")
