from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.group_service import GroupService


def register_group_tools(
    mcp: FastMCP,
    group_service: GroupService,
    authorizer: Authorizer,
    audit_logger: AuditLogger,
) -> None:
    @mcp.tool
    async def entra_find_groups(query: str, exact_match: bool = True, max_results: int = 10) -> dict[str, Any]:
        await authorizer.require_group_read_permission()
        audit_logger.log_group_query(
            tool_name="entra_find_groups",
            status="requested",
            count=None,
        )
        try:
            response = await group_service.find_groups(
                query=query,
                exact_match=exact_match,
                max_results=max_results,
            )
        except ValueError as exc:
            audit_logger.log_group_query(
                tool_name="entra_find_groups",
                status="invalid_request",
                count=0,
            )
            return {
                "success": False,
                "query": (query or "").strip(),
                "exact_match": exact_match,
                "groups_count": 0,
                "groups": [],
                "message": str(exc),
                "request_id": None,
            }
        audit_logger.log_group_query(
            tool_name="entra_find_groups",
            status="success" if response.success else "failed",
            count=response.groups_count,
            request_id=response.request_id,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_check_required_groups_by_platform(user_upn: str, platform: str) -> dict[str, Any]:
        await authorizer.require_group_read_permission()
        audit_logger.log_group_query(
            tool_name="entra_check_required_groups_by_platform",
            user_id=user_upn,
            platform=platform,
            transitive=True,
            status="requested",
            count=None,
        )
        try:
            response = await group_service.check_required_groups_by_platform(user_upn, platform)
        except ValueError as exc:
            audit_logger.log_group_query(
                tool_name="entra_check_required_groups_by_platform",
                user_id=user_upn,
                platform=platform,
                transitive=True,
                status="invalid_request",
                count=0,
            )
            return {
                "success": False,
                "user_id": "",
                "user_principal_name": "",
                "user_display_name": None,
                "platform": (platform or "").strip().lower(),
                "compliant": False,
                "required_groups_count": 0,
                "direct_groups_count": 0,
                "inherited_groups_count": 0,
                "missing_groups_count": 0,
                "direct_groups": [],
                "inherited_groups": [],
                "missing_groups": [],
                "all_groups_checked": [],
                "message": str(exc),
                "request_id": None,
            }
        audit_logger.log_group_query(
            tool_name="entra_check_required_groups_by_platform",
            user_id=response.user_id,
            platform=response.platform,
            transitive=True,
            status="success" if response.success else "failed",
            count=response.required_groups_count,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_list_user_groups(user_upn: str, transitive: bool = True) -> dict[str, Any]:
        await authorizer.require_group_read_permission()
        audit_logger.log_group_query(
            tool_name="entra_list_user_groups",
            user_id=user_upn,
            transitive=transitive,
            status="requested",
            count=None,
        )
        response = await group_service.list_user_groups(user_upn, transitive=transitive)
        audit_logger.log_group_query(
            tool_name="entra_list_user_groups",
            user_id=response.user_id,
            transitive=transitive,
            status="success" if response.success else "failed",
            count=response.groups_count,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_list_group_members(group_id: str, transitive: bool = True) -> dict[str, Any]:
        await authorizer.require_group_read_permission()
        audit_logger.log_group_query(
            tool_name="entra_list_group_members",
            group_id=group_id,
            transitive=transitive,
            status="requested",
            count=None,
        )
        try:
            response = await group_service.list_group_members(group_id, transitive=transitive)
        except ValueError as exc:
            audit_logger.log_group_query(
                tool_name="entra_list_group_members",
                group_id=group_id,
                transitive=transitive,
                status="invalid_request",
                count=0,
            )
            return {
                "success": False,
                "group_id": "",
                "transitive": transitive,
                "members_count": 0,
                "members": [],
                "message": str(exc),
                "request_id": None,
            }
        audit_logger.log_group_query(
            tool_name="entra_list_group_members",
            group_id=response.group_id,
            transitive=transitive,
            status="success" if response.success else "failed",
            count=response.members_count,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_add_user_to_group(user_upn: str, group_id: str) -> dict[str, Any]:
        await authorizer.require_group_write_permission()
        audit_logger.log_group_query(
            tool_name="entra_add_user_to_group",
            user_id=user_upn,
            group_id=group_id,
            status="requested",
            count=None,
        )
        try:
            response = await group_service.add_user_to_group(user_upn=user_upn, group_id=group_id)
        except ValueError as exc:
            audit_logger.log_group_query(
                tool_name="entra_add_user_to_group",
                user_id=user_upn,
                group_id=group_id,
                status="invalid_request",
                count=0,
            )
            return {
                "success": False,
                "group_id": "",
                "user_id": "",
                "user_principal_name": "",
                "user_display_name": None,
                "action": "add",
                "message": str(exc),
                "request_id": None,
            }
        audit_logger.log_group_query(
            tool_name="entra_add_user_to_group",
            user_id=response.user_id or user_upn,
            group_id=response.group_id,
            status="success" if response.success else "failed",
            count=1 if response.success else 0,
            request_id=response.request_id,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def entra_remove_user_from_group(user_upn: str, group_id: str) -> dict[str, Any]:
        await authorizer.require_group_write_permission()
        audit_logger.log_group_query(
            tool_name="entra_remove_user_from_group",
            user_id=user_upn,
            group_id=group_id,
            status="requested",
            count=None,
        )
        try:
            response = await group_service.remove_user_from_group(user_upn=user_upn, group_id=group_id)
        except ValueError as exc:
            audit_logger.log_group_query(
                tool_name="entra_remove_user_from_group",
                user_id=user_upn,
                group_id=group_id,
                status="invalid_request",
                count=0,
            )
            return {
                "success": False,
                "group_id": "",
                "user_id": "",
                "user_principal_name": "",
                "user_display_name": None,
                "action": "remove",
                "message": str(exc),
                "request_id": None,
            }
        audit_logger.log_group_query(
            tool_name="entra_remove_user_from_group",
            user_id=response.user_id or user_upn,
            group_id=response.group_id,
            status="success" if response.success else "failed",
            count=1 if response.success else 0,
            request_id=response.request_id,
        )
        return response.model_dump(mode="json")
