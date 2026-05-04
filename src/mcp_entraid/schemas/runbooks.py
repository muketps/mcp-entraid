from __future__ import annotations

from pydantic import BaseModel


class RunbookJobStream(BaseModel):
    id: str | None = None
    stream_type: str | None = None
    summary: str | None = None
    time: str | None = None
    value: str | None = None


class RunbookJobSummary(BaseModel):
    job_name: str
    job_id: str | None
    runbook_name: str
    status: str
    provisioning_state: str | None = None
    creation_time: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    exception: str | None = None


class RunbookExecutionResponse(BaseModel):
    success: bool
    runbook_name: str
    job_name: str
    job_id: str | None
    status: str
    output: str | dict | None
    streams: list["RunbookJobStream"]
    timed_out: bool
    message: str
    request_id: str | None = None


RunbookExecutionResponse.model_rebuild()
