import json
from functools import cached_property

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    tenant_id: str = Field(alias="TENANT_ID")
    client_id: str = Field(alias="CLIENT_ID")
    client_secret: str = Field(alias="CLIENT_SECRET")
    graph_base_url: AnyHttpUrl = Field(
        default="https://graph.microsoft.com/v1.0",
        alias="GRAPH_BASE_URL",
    )
    graph_scope: str = Field(
        default="https://graph.microsoft.com/.default",
        alias="GRAPH_SCOPE",
    )
    graph_beta_base_url: AnyHttpUrl = Field(
        default="https://graph.microsoft.com/beta",
        alias="GRAPH_BETA_BASE_URL",
    )
    azure_tenant_id: str | None = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: str | None = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: str | None = Field(default=None, alias="AZURE_CLIENT_SECRET")
    azure_subscription_id: str | None = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")
    azure_resource_group_name: str | None = Field(default=None, alias="AZURE_RESOURCE_GROUP_NAME")
    azure_automation_account_name: str | None = Field(default=None, alias="AZURE_AUTOMATION_ACCOUNT_NAME")
    azure_unlock_user_runbook_name: str | None = Field(default=None, alias="AZURE_UNLOCK_USER_RUNBOOK_NAME")
    azure_automation_api_version: str = Field(
        default="2024-10-23",
        alias="AZURE_AUTOMATION_API_VERSION",
    )
    azure_automation_run_on: str | None = Field(default=None, alias="AZURE_AUTOMATION_RUN_ON")
    azure_allowed_runbooks: str = Field(default="", alias="AZURE_ALLOWED_RUNBOOKS")
    azure_runbook_parameter_allowlist: str | None = Field(
        default=None,
        alias="AZURE_RUNBOOK_PARAMETER_ALLOWLIST",
    )
    password_generation_max_attempts: int = Field(default=5, alias="PASSWORD_GENERATION_MAX_ATTEMPTS")
    password_reset_runbook_name: str | None = Field(default=None, alias="PASSWORD_RESET_RUNBOOK_NAME")
    password_reset_runbook_wait_for_completion: bool = Field(
        default=True,
        alias="PASSWORD_RESET_RUNBOOK_WAIT_FOR_COMPLETION",
    )
    password_reset_runbook_timeout_seconds: int = Field(
        default=120,
        alias="PASSWORD_RESET_RUNBOOK_TIMEOUT_SECONDS",
    )
    password_reset_return_temporary_password: bool = Field(
        default=True,
        alias="PASSWORD_RESET_RETURN_TEMPORARY_PASSWORD",
    )
    password_reset_workflow_expiration_minutes: int = Field(
        default=15,
        alias="PASSWORD_RESET_WORKFLOW_EXPIRATION_MINUTES",
    )
    password_reset_runbook_user_param: str = Field(
        default="UserPrincipalName",
        alias="PASSWORD_RESET_RUNBOOK_USER_PARAM",
    )
    password_reset_runbook_password_param: str = Field(
        default="TemporaryPassword",
        alias="PASSWORD_RESET_RUNBOOK_PASSWORD_PARAM",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def graph_base_url_str(self) -> str:
        return str(self.graph_base_url).rstrip("/")

    @property
    def graph_beta_base_url_str(self) -> str:
        return str(self.graph_beta_base_url).rstrip("/")

    @cached_property
    def azure_allowed_runbooks_list(self) -> list[str]:
        return [item.strip() for item in self.azure_allowed_runbooks.split(",") if item.strip()]

    @property
    def azure_tenant_id_effective(self) -> str | None:
        return self.tenant_id

    @property
    def azure_client_id_effective(self) -> str | None:
        return self.client_id

    @property
    def azure_client_secret_effective(self) -> str | None:
        return self.client_secret

    @cached_property
    def azure_runbook_parameter_allowlist_map(self) -> dict[str, list[str]]:
        if not self.azure_runbook_parameter_allowlist:
            return {}

        try:
            payload = json.loads(self.azure_runbook_parameter_allowlist)
        except json.JSONDecodeError:
            return {}

        if not isinstance(payload, dict):
            return {}

        normalized: dict[str, list[str]] = {}
        for runbook_name, allowed_parameters in payload.items():
            if not isinstance(runbook_name, str) or not isinstance(allowed_parameters, list):
                continue
            normalized[runbook_name.lower()] = [
                str(parameter).strip()
                for parameter in allowed_parameters
                if str(parameter).strip()
            ]
        return normalized

    def has_azure_runbook_config(self) -> bool:
        required = [
            self.azure_tenant_id_effective,
            self.azure_client_id_effective,
            self.azure_client_secret_effective,
            self.azure_subscription_id,
            self.azure_resource_group_name,
            self.azure_automation_account_name,
        ]
        return all(required)
