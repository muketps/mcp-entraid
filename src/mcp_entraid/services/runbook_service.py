from __future__ import annotations

import re

from mcp_entraid.azure.automation_client import AzureAutomationClient, AzureAutomationError
from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.schemas.runbooks import RunbookExecutionResponse
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.settings import Settings

BLOCKED_USER_VALUES = {"*", "all", "todos", "everyone", "tenant"}
UPN_PATTERN = re.compile(r"^[^@\s,;|]+@[^@\s,;|]+\.[^@\s,;|]+$")


class RunbookService:
    def __init__(
        self,
        settings: Settings,
        automation_client: AzureAutomationClient,
        authorizer: Authorizer,
        audit_logger: AuditLogger,
    ) -> None:
        self._settings = settings
        self._automation_client = automation_client
        self._authorizer = authorizer
        self._audit_logger = audit_logger

    async def execute_runbook(
        self,
        runbook_name: str,
        parameters: dict[str, str] | None = None,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> RunbookExecutionResponse:
        self._validate_azure_config()
        await self._authorizer.require_execute_runbook_permission(runbook_name)
        self._validate_runbook_name(runbook_name)
        self._validate_parameters(runbook_name, parameters or {})

        masked_parameters = self._mask_parameters(parameters or {})

        try:
            job = await self._automation_client.create_job(
                runbook_name=runbook_name,
                parameters=parameters,
            )
        except AzureAutomationError as exc:
            self._audit_logger.log_runbook_event(
                tool_name="azure_execute_automation_runbook",
                runbook_name=runbook_name,
                job_name="",
                parameters_masked=masked_parameters,
                wait_for_completion=wait_for_completion,
                timeout_seconds=timeout_seconds,
                status="Failed",
                success=False,
                timed_out=False,
            )
            return RunbookExecutionResponse(
                success=False,
                runbook_name=runbook_name,
                job_name="",
                job_id=None,
                status="Failed",
                output=None,
                streams=[],
                timed_out=False,
                message=str(exc),
                request_id=None,
            )

        if not wait_for_completion:
            self._audit_logger.log_runbook_event(
                tool_name="azure_execute_automation_runbook",
                runbook_name=runbook_name,
                job_name=job.job_name,
                parameters_masked=masked_parameters,
                wait_for_completion=False,
                timeout_seconds=timeout_seconds,
                status=job.status,
                success=True,
                timed_out=False,
            )
            return RunbookExecutionResponse(
                success=True,
                runbook_name=runbook_name,
                job_name=job.job_name,
                job_id=job.job_id,
                status=job.status,
                output=None,
                streams=[],
                timed_out=False,
                message="Job criado com sucesso.",
                request_id=None,
            )

        timeout_seconds = min(timeout_seconds, 300)
        final_job = await self._automation_client.wait_for_job_completion(job.job_name, timeout_seconds)
        timed_out = final_job.status not in {"Completed", "Failed", "Stopped", "Suspended"}
        output = None
        streams = []
        if not timed_out:
            output = await self._automation_client.get_job_output(job.job_name)
            streams = await self._automation_client.list_job_streams(job.job_name)

        success = final_job.status == "Completed" and not timed_out
        message = (
            "Runbook concluído."
            if success
            else (
                "Timeout aguardando conclusão do job."
                if timed_out
                else f"Runbook finalizado com status {final_job.status}."
            )
        )
        if final_job.status == "Failed" and final_job.exception:
            message = f"{message} Exception: {final_job.exception}"

        self._audit_logger.log_runbook_event(
            tool_name="azure_execute_automation_runbook",
            runbook_name=runbook_name,
            job_name=job.job_name,
            parameters_masked=masked_parameters,
            wait_for_completion=True,
            timeout_seconds=timeout_seconds,
            status=final_job.status,
            success=success,
            timed_out=timed_out,
        )
        return RunbookExecutionResponse(
            success=success,
            runbook_name=runbook_name,
            job_name=job.job_name,
            job_id=final_job.job_id,
            status=final_job.status,
            output=output,
            streams=streams,
            timed_out=timed_out,
            message=message,
            request_id=None,
        )

    async def unlock_user(
        self,
        user_upn: str,
        wait_for_completion: bool = True,
        timeout_seconds: int = 60,
    ) -> RunbookExecutionResponse:
        runbook_name = self._settings.azure_unlock_user_runbook_name or ""
        try:
            normalized_user_upn = self._validate_user_upn(user_upn)
            if not runbook_name:
                raise AzureAutomationError("Runbook de desbloqueio nao configurado.")
            return await self.execute_runbook(
                runbook_name=runbook_name,
                parameters={"UPN": normalized_user_upn},
                wait_for_completion=wait_for_completion,
                timeout_seconds=timeout_seconds,
            )
        except (AzureAutomationError, ValueError) as exc:
            return RunbookExecutionResponse(
                success=False,
                runbook_name=runbook_name,
                job_name="",
                job_id=None,
                status="Failed",
                output=None,
                streams=[],
                timed_out=False,
                message=str(exc),
                request_id=None,
            )

    async def get_runbook_output(self, job_name: str, include_streams: bool = True) -> RunbookExecutionResponse:
        self._validate_azure_config()
        await self._authorizer.require_execute_runbook_permission("")
        job = await self._automation_client.get_job(job_name)
        output = await self._automation_client.get_job_output(job_name)
        streams = await self._automation_client.list_job_streams(job_name) if include_streams else []
        success = job.status == "Completed"
        message = "Saída do job retornada."
        if job.status == "Failed" and job.exception:
            message = f"{message} Exception: {job.exception}"

        self._audit_logger.log_runbook_event(
            tool_name="azure_get_automation_runbook_output",
            runbook_name=job.runbook_name,
            job_name=job_name,
            parameters_masked={},
            wait_for_completion=True,
            timeout_seconds=0,
            status=job.status,
            success=success,
            timed_out=False,
        )
        return RunbookExecutionResponse(
            success=success,
            runbook_name=job.runbook_name,
            job_name=job.job_name,
            job_id=job.job_id,
            status=job.status,
            output=output,
            streams=streams,
            timed_out=False,
            message=message,
            request_id=None,
        )

    def _validate_runbook_name(self, runbook_name: str) -> None:
        allowed = {item.lower() for item in self._settings.azure_allowed_runbooks_list}
        if not allowed or runbook_name.lower() not in allowed:
            raise AzureAutomationError(f"Runbook não permitido: {runbook_name}.")

    def _validate_parameters(self, runbook_name: str, parameters: dict[str, str]) -> None:
        allowed_map = self._settings.azure_runbook_parameter_allowlist_map
        if not allowed_map:
            return

        allowed_parameters = allowed_map.get(runbook_name.lower())
        if allowed_parameters is None:
            return

        invalid = sorted(set(parameters) - set(allowed_parameters))
        if invalid:
            raise AzureAutomationError(
                "Parâmetros não permitidos para este runbook: " + ", ".join(invalid)
            )

    def _validate_azure_config(self) -> None:
        if not self._settings.has_azure_runbook_config():
            raise AzureAutomationError("Configuração Azure Automation incompleta.")

    def _mask_parameters(self, parameters: dict[str, str]) -> dict[str, str]:
        masked: dict[str, str] = {}
        for key, value in parameters.items():
            if any(token in key.lower() for token in ("password", "secret", "token", "key", "credential")):
                masked[key] = "[REDACTED]"
            else:
                masked[key] = value
        return masked

    def _validate_user_upn(self, user_upn: str) -> str:
        if not isinstance(user_upn, str):
            raise ValueError("user_upn deve ser uma string.")

        normalized = user_upn.strip()
        if not normalized:
            raise ValueError("user_upn e obrigatorio.")
        if normalized.lower() in BLOCKED_USER_VALUES:
            raise ValueError("Informe apenas um UPN de usuario. Valores amplos nao sao permitidos.")
        if any(sep in normalized for sep in (",", ";", " ")):
            raise ValueError("Informe apenas um UPN. Multiplos UPNs nao sao permitidos.")
        if not UPN_PATTERN.match(normalized):
            raise ValueError("user_upn deve parecer um UPN valido, como usuario@dominio.com.")
        return normalized
