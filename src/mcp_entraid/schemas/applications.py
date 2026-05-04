from __future__ import annotations

from pydantic import BaseModel


class AppCredentialSummary(BaseModel):
    credential_id: str | None = None
    credential_type: str
    display_name: str | None = None
    start_date_time: str | None = None
    end_date_time: str | None = None
    days_until_expiration: int | None = None
    status: str


class ExpiringAppCredentialItem(BaseModel):
    application_object_id: str
    app_id: str
    display_name: str
    credential: AppCredentialSummary


class ExpiringAppCredentialsResponse(BaseModel):
    success: bool
    days_threshold: int
    include_expired: bool
    expiring_credentials_count: int
    applications_count: int
    items: list[ExpiringAppCredentialItem]
    message: str
    request_id: str | None = None


class AppRegistrationUserMatch(BaseModel):
    application_object_id: str
    app_id: str
    display_name: str
    created_date_time: str | None = None
    match_type: str
    matched_reason: str
    secret_credentials_count: int
    certificate_credentials_count: int
    nearest_credential_expiration: str | None = None


class FindAppRegistrationsByUserResponse(BaseModel):
    success: bool
    user_id: str
    user_principal_name: str
    user_display_name: str | None = None
    matches_count: int
    matches: list[AppRegistrationUserMatch]
    message: str
    request_id: str | None = None
