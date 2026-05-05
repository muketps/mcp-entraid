import httpx
import pytest

from mcp_entraid.audit.audit_logger import AuditLogger
from mcp_entraid.azure.arm_token_provider import ArmTokenProvider
from mcp_entraid.azure.automation_client import AzureAutomationClient, AzureAutomationError
from mcp_entraid.schemas.runbooks import RunbookJobStream, RunbookJobSummary
from mcp_entraid.security.authorizer import Authorizer
from mcp_entraid.services.runbook_service import RunbookService
from mcp_entraid.settings import Settings


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        TENANT_ID="tenant",
        CLIENT_ID="client",
        CLIENT_SECRET="secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
        AZURE_SUBSCRIPTION_ID="sub-id",
        AZURE_RESOURCE_GROUP_NAME="rg",
        AZURE_AUTOMATION_ACCOUNT_NAME="aa",
        AZURE_UNLOCK_USER_RUNBOOK_NAME="Unlock-User",
        AZURE_AUTOMATION_API_VERSION="2024-10-23",
        AZURE_ALLOWED_RUNBOOKS="Allowed-Runbook",
        AZURE_AUTOMATION_RUN_ON="",
    )


class FakeAuthorizer(Authorizer):
    def __init__(self) -> None:
        self.permissions: list[str] = []

    async def authorize(self, permission: str) -> None:
        self.permissions.append(permission)


class FakeAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.events: list[dict] = []

    def log_runbook_event(self, tool_name: str, **kwargs) -> None:
        self.events.append({"tool_name": tool_name, **kwargs})


class FakeAutomationClient:
    def __init__(self) -> None:
        self.created_jobs: list[dict] = []
        self.output_calls: list[str] = []
        self.stream_calls: list[str] = []
        self.wait_calls: list[tuple[str, int, int]] = []
        self.next_status = "Completed"

    async def create_job(
        self,
        runbook_name: str,
        parameters: dict[str, str] | None,
        run_on: str | None = None,
    ) -> RunbookJobSummary:
        job_name = "mcp-allowed-runbook-20260101010101-abcd1234"
        self.created_jobs.append(
            {
                "runbook_name": runbook_name,
                "parameters": parameters,
                "run_on": run_on,
                "job_name": job_name,
            }
        )
        return RunbookJobSummary(
            job_name=job_name,
            job_id="job-id-1",
            runbook_name=runbook_name,
            status="New",
        )

    async def wait_for_job_completion(
        self,
        job_name: str,
        timeout_seconds: int,
        poll_interval_seconds: int = 5,
    ) -> RunbookJobSummary:
        self.wait_calls.append((job_name, timeout_seconds, poll_interval_seconds))
        return RunbookJobSummary(
            job_name=job_name,
            job_id="job-id-1",
            runbook_name="Allowed-Runbook",
            status=self.next_status,
            exception="boom" if self.next_status == "Failed" else None,
        )

    async def get_job_output(self, job_name: str):
        self.output_calls.append(job_name)
        return {"result": "ok"}

    async def list_job_streams(self, job_name: str):
        self.stream_calls.append(job_name)
        return [
            RunbookJobStream(
                id="1",
                stream_type="Output",
                summary="done",
                time="2026-01-01T01:01:01Z",
                value="ok",
            )
        ]

    async def get_job(self, job_name: str) -> RunbookJobSummary:
        return RunbookJobSummary(
            job_name=job_name,
            job_id="job-id-1",
            runbook_name="Allowed-Runbook",
            status=self.next_status,
            exception="boom" if self.next_status == "Failed" else None,
        )


@pytest.mark.asyncio
async def test_execute_runbook_requires_allowlist_and_masks_parameters():
    settings = make_settings()
    automation_client = FakeAutomationClient()
    audit_logger = FakeAuditLogger()
    service = RunbookService(
        settings=settings,
        automation_client=automation_client,
        authorizer=FakeAuthorizer(),
        audit_logger=audit_logger,
    )

    response = await service.execute_runbook(
        runbook_name="Allowed-Runbook",
        parameters={"Password": "secret-value", "mode": "fast"},
        wait_for_completion=False,
    )

    assert response.success is True
    assert response.job_name.startswith("mcp-allowed-runbook-")
    assert response.output is None
    assert response.streams == []
    assert audit_logger.events[0]["parameters_masked"]["Password"] == "[REDACTED]"
    assert automation_client.output_calls == []


@pytest.mark.asyncio
async def test_execute_runbook_blocks_non_allowlisted_runbook():
    settings = make_settings()
    service = RunbookService(
        settings=settings,
        automation_client=FakeAutomationClient(),
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    with pytest.raises(AzureAutomationError, match="Runbook não permitido"):
        await service.execute_runbook(runbook_name="Forbidden-Runbook")


@pytest.mark.asyncio
async def test_get_runbook_output_returns_output_and_streams():
    settings = make_settings()
    automation_client = FakeAutomationClient()
    service = RunbookService(
        settings=settings,
        automation_client=automation_client,
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    response = await service.get_runbook_output("job-123", include_streams=True)

    assert response.success is True
    assert response.output == {"result": "ok"}
    assert len(response.streams) == 1


@pytest.mark.asyncio
async def test_get_runbook_output_can_skip_streams():
    settings = make_settings()
    automation_client = FakeAutomationClient()
    service = RunbookService(
        settings=settings,
        automation_client=automation_client,
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    response = await service.get_runbook_output("job-123", include_streams=False)

    assert response.success is True
    assert response.streams == []
    assert automation_client.stream_calls == []


@pytest.mark.asyncio
async def test_unlock_user_uses_configured_runbook_and_upn_parameter():
    settings = make_settings()
    settings.azure_allowed_runbooks = "Unlock-User"
    automation_client = FakeAutomationClient()
    service = RunbookService(
        settings=settings,
        automation_client=automation_client,
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    response = await service.unlock_user("alice@example.com", wait_for_completion=False)

    assert response.success is True
    assert response.runbook_name == "Unlock-User"
    assert automation_client.created_jobs[0]["runbook_name"] == "Unlock-User"
    assert automation_client.created_jobs[0]["parameters"] == {"UPN": "alice@example.com"}


@pytest.mark.asyncio
async def test_unlock_user_uses_graph_credentials_for_azure():
    settings = Settings(
        _env_file=None,
        TENANT_ID="graph-tenant",
        CLIENT_ID="graph-client",
        CLIENT_SECRET="graph-secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
        AZURE_SUBSCRIPTION_ID="sub-id",
        AZURE_RESOURCE_GROUP_NAME="rg",
        AZURE_AUTOMATION_ACCOUNT_NAME="aa",
        AZURE_UNLOCK_USER_RUNBOOK_NAME="Unlock-User",
        AZURE_AUTOMATION_API_VERSION="2024-10-23",
        AZURE_ALLOWED_RUNBOOKS="Unlock-User",
        AZURE_AUTOMATION_RUN_ON="",
    )
    automation_client = FakeAutomationClient()
    service = RunbookService(
        settings=settings,
        automation_client=automation_client,
        authorizer=FakeAuthorizer(),
        audit_logger=FakeAuditLogger(),
    )

    response = await service.unlock_user("alice@example.com", wait_for_completion=False)

    assert response.success is True
    assert settings.azure_tenant_id_effective == "graph-tenant"
    assert settings.azure_client_id_effective == "graph-client"
    assert settings.azure_client_secret_effective == "graph-secret"


@pytest.mark.asyncio
async def test_arm_token_provider_uses_graph_credentials_for_azure():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})

    settings = Settings(
        _env_file=None,
        TENANT_ID="graph-tenant",
        CLIENT_ID="graph-client",
        CLIENT_SECRET="graph-secret",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        GRAPH_SCOPE="https://graph.microsoft.com/.default",
        AZURE_SUBSCRIPTION_ID="sub-id",
        AZURE_RESOURCE_GROUP_NAME="rg",
        AZURE_AUTOMATION_ACCOUNT_NAME="aa",
        AZURE_UNLOCK_USER_RUNBOOK_NAME="Unlock-User",
        AZURE_AUTOMATION_API_VERSION="2024-10-23",
        AZURE_ALLOWED_RUNBOOKS="Unlock-User",
        AZURE_AUTOMATION_RUN_ON="",
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    token_provider = ArmTokenProvider(settings, http_client=http_client)

    token = await token_provider.get_access_token()
    await http_client.aclose()

    assert token == "token"
    assert "graph-tenant/oauth2/v2.0/token" in captured["url"]
    assert "client_id=graph-client" in captured["body"]
    assert "client_secret=graph-secret" in captured["body"]


@pytest.mark.asyncio
async def test_automation_client_parses_plain_text_and_json_output():
    settings = make_settings()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            text='{"message":"hello"}',
        )
        if request.url.path.endswith("/output")
        else httpx.Response(
            200,
            json={
                "id": "/jobs/job-1",
                "properties": {
                    "status": "Completed",
                    "runbook": {"name": "Allowed-Runbook"},
                },
            },
        )
    )
    http_client = httpx.AsyncClient(transport=transport)
    token_provider = ArmTokenProvider(settings, http_client=http_client)
    token_provider._cached_token = type(  # noqa: SLF001
        "Token",
        (),
        {"access_token": "token", "expires_at": 9_999_999_999},
    )()
    client = AzureAutomationClient(settings, token_provider, http_client=http_client)

    job = await client.get_job("job-1")
    output = await client.get_job_output("job-1")

    assert job.status == "Completed"
    assert output == {"message": "hello"}
