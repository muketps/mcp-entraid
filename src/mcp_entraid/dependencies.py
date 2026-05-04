from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.azure.arm_token_provider import ArmTokenProvider
from mcp_entraid.azure.automation_client import AzureAutomationClient
from mcp_entraid.auth.graph_token_provider import GraphTokenProvider
from mcp_entraid.graph.client import GraphClient
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.application_service import ApplicationService
from mcp_entraid.services.group_service import GroupService
from mcp_entraid.services.authentication_method_service import AuthenticationMethodService
from mcp_entraid.services.user_service import UserService
from mcp_entraid.services.runbook_service import RunbookService
from mcp_entraid.settings import Settings
from mcp_entraid.workflows.reset_mfa_workflow import ResetMfaWorkflow
from mcp_entraid.workflows.workflow_store import WorkflowStore

load_dotenv()


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_token_provider() -> GraphTokenProvider:
    return GraphTokenProvider(get_settings())


@lru_cache
def get_graph_client() -> GraphClient:
    return GraphClient(get_settings(), get_token_provider())


@lru_cache
def get_user_service() -> UserService:
    return UserService(get_graph_client())


@lru_cache
def get_authentication_method_service() -> AuthenticationMethodService:
    return AuthenticationMethodService(get_graph_client())


@lru_cache
def get_authorizer() -> Authorizer:
    return Authorizer()


@lru_cache
def get_audit_logger() -> AuditLogger:
    return AuditLogger()


@lru_cache
def get_workflow_store() -> WorkflowStore:
    return WorkflowStore()


@lru_cache
def get_reset_mfa_workflow() -> ResetMfaWorkflow:
    return ResetMfaWorkflow(
        user_service=get_user_service(),
        authentication_method_service=get_authentication_method_service(),
        workflow_store=get_workflow_store(),
        authorizer=get_authorizer(),
        audit_logger=get_audit_logger(),
    )


@lru_cache
def get_arm_token_provider() -> ArmTokenProvider:
    return ArmTokenProvider(get_settings())


@lru_cache
def get_azure_automation_client() -> AzureAutomationClient:
    return AzureAutomationClient(
        settings=get_settings(),
        token_provider=get_arm_token_provider(),
    )


@lru_cache
def get_runbook_service() -> RunbookService:
    return RunbookService(
        settings=get_settings(),
        automation_client=get_azure_automation_client(),
        authorizer=get_authorizer(),
        audit_logger=get_audit_logger(),
    )


@lru_cache
def get_group_service() -> GroupService:
    return GroupService(
        graph_client=get_graph_client(),
        user_service=get_user_service(),
    )


@lru_cache
def get_application_service() -> ApplicationService:
    return ApplicationService(
        graph_client=get_graph_client(),
        user_service=get_user_service(),
    )
