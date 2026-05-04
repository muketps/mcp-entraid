from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from mcp_entraid.azure.arm_token_provider import ArmTokenProvider, ArmTokenError
from mcp_entraid.schemas.runbooks import RunbookJobStream, RunbookJobSummary
from mcp_entraid.settings import Settings


class AzureAutomationError(RuntimeError):
    """Erro ao operar Azure Automation."""


@dataclass
class AzureAutomationClient:
    settings: Settings
    token_provider: ArmTokenProvider
    http_client: httpx.AsyncClient | None = None

    async def create_job(
        self,
        runbook_name: str,
        parameters: dict[str, str] | None,
        run_on: str | None = None,
    ) -> RunbookJobSummary:
        job_name = self._generate_job_name(runbook_name)
        path = self._job_path(job_name)
        properties = {
            "parameters": parameters or {},
            "runbook": {"name": runbook_name},
        }
        effective_run_on = run_on or self.settings.azure_automation_run_on
        if effective_run_on:
            properties["runOn"] = effective_run_on
        body = {"properties": properties}
        payload = await self._request("PUT", path, json=body)
        return self._to_job_summary(job_name, runbook_name, payload)

    async def get_job(self, job_name: str) -> RunbookJobSummary:
        payload = await self._request("GET", self._job_path(job_name))
        return self._to_job_summary(job_name, payload.get("properties", {}).get("runbook", {}).get("name", ""), payload)

    async def get_job_output(self, job_name: str) -> str | dict | None:
        response = await self._request_raw("GET", f"{self._job_path(job_name)}/output")
        return self._parse_output_response(response)

    async def list_job_streams(self, job_name: str) -> list[RunbookJobStream]:
        payload = await self._request("GET", f"{self._job_path(job_name)}/streams")
        return [self._to_stream_summary(item) for item in payload.get("value", [])]

    async def wait_for_job_completion(
        self,
        job_name: str,
        timeout_seconds: int,
        poll_interval_seconds: int = 5,
    ) -> RunbookJobSummary:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            job = await self.get_job(job_name)
            if job.status in {"Completed", "Failed", "Stopped", "Suspended"}:
                return job
            if asyncio.get_running_loop().time() >= deadline:
                return job
            await asyncio.sleep(poll_interval_seconds)

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        response = await self._request_raw(method, path, json=json)
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    async def _request_raw(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        try:
            token = await self.token_provider.get_access_token()
        except ArmTokenError as exc:
            raise AzureAutomationError(str(exc)) from exc

        url = self._build_url(path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            if self.http_client is not None:
                response = await self.http_client.request(method, url, json=json, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(method, url, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise AzureAutomationError("Falha de comunicação com o Azure Automation.") from exc

        if response.status_code >= 400:
            raise AzureAutomationError(self._extract_error_message(response))

        return response

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        base_url = "https://management.azure.com"
        return (
            f"{base_url}/subscriptions/{self.settings.azure_subscription_id}"
            f"/resourceGroups/{self.settings.azure_resource_group_name}"
            f"/providers/Microsoft.Automation/automationAccounts/{self.settings.azure_automation_account_name}"
            f"{normalized_path}"
            f"?api-version={self.settings.azure_automation_api_version}"
        )

    def _job_path(self, job_name: str) -> str:
        return f"/jobs/{job_name}"

    def _generate_job_name(self, runbook_name: str) -> str:
        sanitized_runbook = "".join(
            character.lower() if character.isalnum() else "-"
            for character in runbook_name
        ).strip("-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        short_uuid = uuid4().hex[:8]
        return f"mcp-{sanitized_runbook}-{timestamp}-{short_uuid}"

    def _to_job_summary(self, job_name: str, runbook_name: str, payload: dict) -> RunbookJobSummary:
        properties = payload.get("properties", {})
        return RunbookJobSummary(
            job_name=job_name,
            job_id=payload.get("id"),
            runbook_name=runbook_name or properties.get("runbook", {}).get("name", ""),
            status=properties.get("status", "Unknown"),
            provisioning_state=properties.get("provisioningState"),
            creation_time=properties.get("creationTime"),
            start_time=properties.get("startTime"),
            end_time=properties.get("endTime"),
            exception=properties.get("exception"),
        )

    def _to_stream_summary(self, payload: dict) -> RunbookJobStream:
        properties = payload.get("properties", {})
        return RunbookJobStream(
            id=payload.get("id"),
            stream_type=properties.get("streamType"),
            summary=properties.get("summary"),
            time=properties.get("time"),
            value=properties.get("value"),
        )

    def _parse_output_response(self, response: httpx.Response) -> str | dict | None:
        content_type = response.headers.get("content-type", "").lower()
        text = response.text.strip()
        if not text:
            return None
        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                pass
        try:
            return json.loads(text)
        except ValueError:
            return text

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Azure Automation retornou HTTP {response.status_code}."

        message = payload.get("error", {}).get("message") if isinstance(payload.get("error"), dict) else None
        if isinstance(message, str) and message:
            return message
        return f"Azure Automation retornou HTTP {response.status_code}."
