from __future__ import annotations

from fastmcp import FastMCP

from mcp_entraid.dependencies import (
    get_audit_logger,
    get_application_service,
    get_authorizer,
    get_authentication_method_service,
    get_group_service,
    get_runbook_service,
    get_reset_mfa_workflow,
    get_reset_password_workflow,
    get_user_service,
)
from mcp_entraid.tools.applications import register_application_tools
from mcp_entraid.tools.authentication_methods import register_authentication_method_tools
from mcp_entraid.tools.groups import register_group_tools
from mcp_entraid.tools.passwords import register_password_tools
from mcp_entraid.tools.runbooks import register_azure_unlock_user_tool
from mcp_entraid.tools.users import register_user_tools

mcp = FastMCP(
    name="mcp-entraid",
    instructions="MCP corporativo para Microsoft Entra ID usando Microsoft Graph.",
)

register_user_tools(
    mcp=mcp,
    user_service=get_user_service(),
    authorizer=get_authorizer(),
    audit_logger=get_audit_logger(),
)

register_authentication_method_tools(
    mcp=mcp,
    user_service=get_user_service(),
    authentication_method_service=get_authentication_method_service(),
    reset_mfa_workflow=get_reset_mfa_workflow(),
    authorizer=get_authorizer(),
    audit_logger=get_audit_logger(),
)

register_password_tools(
    mcp=mcp,
    reset_password_workflow=get_reset_password_workflow(),
)

register_group_tools(
    mcp=mcp,
    group_service=get_group_service(),
    authorizer=get_authorizer(),
    audit_logger=get_audit_logger(),
)

register_application_tools(
    mcp=mcp,
    application_service=get_application_service(),
    authorizer=get_authorizer(),
    audit_logger=get_audit_logger(),
)

register_azure_unlock_user_tool(
    mcp=mcp,
    runbook_service=get_runbook_service(),
)


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
