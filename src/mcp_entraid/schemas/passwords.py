from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GeneratedPasswordMetadata(BaseModel):
    length: int
    letters_count: int
    numbers_count: int
    symbols_count: int
    has_lowercase: bool
    has_uppercase: bool
    has_number: bool
    has_symbol: bool


class ResetPasswordResponse(BaseModel):
    success: bool
    status: str
    reset_password_request_id: str | None
    user_id: str | None
    user_principal_name: str | None
    user_display_name: str | None
    confirmation_required: bool
    confirmation_phrase: str | None
    temporary_password: str | None
    password_generated: bool
    runbook_name: str | None
    automation_job_name: str | None
    automation_job_id: str | None
    runbook_status: str | None
    decoded_runbook_output: str | dict[str, Any] | None
    message: str
    request_id: str | None


class ResetPasswordWorkflowState(BaseModel):
    reset_password_request_id: str
    user_id: str
    user_principal_name: str
    user_display_name: str | None = None
    expected_confirmation_phrase: str
    status: str
    current_step: str | None = None
    created_at: str
    expires_at: str
    runbook_name: str | None = None
    automation_job_name: str | None = None
    automation_job_id: str | None = None
