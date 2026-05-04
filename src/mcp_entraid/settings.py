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
    azure_tenant_id: str | None = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: str | None = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: str | None = Field(default=None, alias="AZURE_CLIENT_SECRET")
    azure_subscription_id: str | None = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")
    azure_resource_group_name: str | None = Field(default=None, alias="AZURE_RESOURCE_GROUP_NAME")
    azure_automation_account_name: str | None = Field(default=None, alias="AZURE_AUTOMATION_ACCOUNT_NAME")
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def graph_base_url_str(self) -> str:
        return str(self.graph_base_url).rstrip("/")

    @cached_property
    def azure_allowed_runbooks_list(self) -> list[str]:
        return [item.strip() for item in self.azure_allowed_runbooks.split(",") if item.strip()]

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
            self.azure_tenant_id,
            self.azure_client_id,
            self.azure_client_secret,
            self.azure_subscription_id,
            self.azure_resource_group_name,
            self.azure_automation_account_name,
        ]
        return all(required)
