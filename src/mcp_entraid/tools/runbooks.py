from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_entraid.services.runbook_service import RunbookService


def register_runbook_tools(mcp: FastMCP, runbook_service: RunbookService) -> None:
    @mcp.tool
    async def azure_execute_automation_runbook(
        runbook_name: str,
        parameters: dict[str, str] | None = None,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        response = await runbook_service.execute_runbook(
            runbook_name=runbook_name,
            parameters=parameters,
            wait_for_completion=wait_for_completion,
            timeout_seconds=timeout_seconds,
        )
        return response.model_dump(mode="json")

    @mcp.tool
    async def azure_get_automation_runbook_output(
        job_name: str,
        include_streams: bool = True,
    ) -> dict[str, Any]:
        response = await runbook_service.get_runbook_output(
            job_name=job_name,
            include_streams=include_streams,
        )
        return response.model_dump(mode="json")
