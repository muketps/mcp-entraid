from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.security.permissions import ENTRA_APPLICATION_READ, ENTRA_USER_READ
from mcp_entraid.services.application_service import ApplicationService


def register_application_tools(
    mcp: FastMCP,
    application_service: ApplicationService,
    authorizer: Authorizer,
    audit_logger: AuditLogger,
) -> None:
    @mcp.tool
    async def entra_list_expiring_app_credentials(
        days_threshold: int = 30,
        include_expired: bool = True,
        include_certificates: bool = True,
        include_secrets: bool = True,
    ) -> dict[str, Any]:
        audit_logger.log_application_query(
            tool_name="entra_list_expiring_app_credentials",
            days_threshold=days_threshold,
            include_expired=include_expired,
            status="requested",
        )
        await authorizer.require_application_read_permission()
        try:
            response = await application_service.list_expiring_app_credentials(
                days_threshold=days_threshold,
                include_expired=include_expired,
                include_certificates=include_certificates,
                include_secrets=include_secrets,
            )
        except ValueError as exc:
            audit_logger.log_application_query(
                tool_name="entra_list_expiring_app_credentials",
                days_threshold=days_threshold,
                include_expired=include_expired,
                status="invalid_request",
                result_count=0,
            )
            return {
                "success": False,
                "days_threshold": days_threshold,
                "include_expired": include_expired,
                "expiring_credentials_count": 0,
                "applications_count": 0,
                "items": [],
                "message": str(exc),
                "request_id": None,
            }

        audit_logger.log_application_query(
            tool_name="entra_list_expiring_app_credentials",
            days_threshold=days_threshold,
            include_expired=include_expired,
            status="success" if response.success else "failed",
            result_count=response.expiring_credentials_count,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_find_app_registrations_by_user(
        user_upn: str,
        search_display_name: bool = True,
        search_owned_apps: bool = True,
    ) -> dict[str, Any]:
        audit_logger.log_application_query(
            tool_name="entra_find_app_registrations_by_user",
            user_upn=user_upn,
            search_display_name=search_display_name,
            search_owned_apps=search_owned_apps,
            status="requested",
        )
        await authorizer.authorize(ENTRA_USER_READ)
        await authorizer.require_application_read_permission()
        response = await application_service.find_app_registrations_by_user(
            user_upn=user_upn,
            search_display_name=search_display_name,
            search_owned_apps=search_owned_apps,
        )
        audit_logger.log_application_query(
            tool_name="entra_find_app_registrations_by_user",
            user_upn=response.user_principal_name or user_upn,
            search_display_name=search_display_name,
            search_owned_apps=search_owned_apps,
            status="success" if response.success else "failed",
            result_count=response.matches_count,
        )
        return response.model_dump(mode="json")
