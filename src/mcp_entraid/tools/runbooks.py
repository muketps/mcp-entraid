from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.services.runbook_service import RunbookService


def register_azure_unlock_user_tool(mcp: FastMCP, runbook_service: RunbookService) -> None:
    @mcp.tool
    async def azure_unlock_user(
        user_upn: str,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        response = await runbook_service.unlock_user(
            user_upn=user_upn,
            wait_for_completion=wait_for_completion,
            timeout_seconds=timeout_seconds,
        )
        return response.model_dump(mode="json")
