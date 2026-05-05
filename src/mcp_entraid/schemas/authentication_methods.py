from __future__ import annotations

from pydantic import BaseModel


class AuthenticationMethodSummary(BaseModel):
    id: str
    type: str
    display_name: str | None = None
    phone_type: str | None = None
    phone_number_masked: str | None = None
    status: str | None = None
    reason: str | None = None


class AuthenticationMethodOperationResult(BaseModel):
    id: str
    type: str
    display_name: str | None = None
    status: str
    reason: str | None = None


class ResetMfaStartResponse(BaseModel):
    success: bool
    reset_request_id: str
    user_upn: str
    user_display_name: str | None = None
    phone_methods: list[AuthenticationMethodSummary]
    mfa_methods: list[AuthenticationMethodSummary]
    phone_methods_found: int
    mfa_methods_found: int
    current_step: str
    confirmation_required: bool
    confirmation_message: str
    expires_at: str
    request_id: str | None = None


class ResetMfaStepResponse(BaseModel):
    success: bool
    reset_request_id: str
    user_upn: str
    user_display_name: str | None = None
    step_completed: str | None = None
    next_step: str | None = None
    deleted_phone_methods: list[AuthenticationMethodOperationResult]
    deleted_mfa_methods: list[AuthenticationMethodOperationResult]
    failed_methods: list[AuthenticationMethodOperationResult]
    sessions_revoked: bool
    confirmation_required: bool
    confirmation_message: str | None = None
    status: str
    message: str
    request_id: str | None = None


class ResetMfaStatusResponse(BaseModel):
    success: bool
    reset_request_id: str
    user_upn: str
    user_display_name: str | None = None
    status: str
    current_step: str | None = None
    completed_steps: list[str]
    failed_methods: list[AuthenticationMethodOperationResult]
    deleted_phone_methods: list[AuthenticationMethodOperationResult]
    deleted_mfa_methods: list[AuthenticationMethodOperationResult]
    sessions_revoked: bool
    expires_at: str
    message: str
    request_id: str | None = None


class ResetMfaWorkflowState(BaseModel):
    reset_request_id: str
    user_id: str
    user_principal_name: str
    user_display_name: str | None = None
    phone_methods: list[AuthenticationMethodSummary]
    mfa_methods: list[AuthenticationMethodSummary]
    status: str
    current_step: str | None = None
    completed_steps: list[str]
    deleted_phone_methods: list[AuthenticationMethodOperationResult]
    deleted_mfa_methods: list[AuthenticationMethodOperationResult]
    failed_methods: list[AuthenticationMethodOperationResult]
    sessions_revoked: bool
    created_at: str
    expires_at: str
