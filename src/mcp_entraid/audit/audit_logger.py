from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("mcp_entraid.audit")

SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "client_secret",
    "clientsecret",
    "secret",
    "token",
}


class AuditLogger:
    def log_tool_call(self, tool_name: str, metadata: dict[str, Any] | None = None) -> None:
        safe_metadata = self._sanitize(metadata or {})
        logger.info("tool_call", extra={"tool_name": tool_name, "metadata": safe_metadata})

    def log_tool_result(
        self,
        tool_name: str,
        success: bool,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_metadata = self._sanitize(metadata or {})
        logger.info(
            "tool_result",
            extra={
                "tool_name": tool_name,
                "success": success,
                "request_id": request_id,
                "metadata": safe_metadata,
            },
        )

    def log_workflow_event(
        self,
        tool_name: str,
        reset_request_id: str | None = None,
        target_user: str | None = None,
        step: str | None = None,
        confirmed: bool | None = None,
        phone_methods_found: int | None = None,
        mfa_methods_found: int | None = None,
        deleted_phone_count: int | None = None,
        deleted_mfa_count: int | None = None,
        failed_count: int | None = None,
        sessions_revoked: bool | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> None:
        metadata = {
            "reset_request_id": reset_request_id,
            "target_user": target_user,
            "step": step,
            "confirmed": confirmed,
            "phone_methods_found": phone_methods_found,
            "mfa_methods_found": mfa_methods_found,
            "deleted_phone_count": deleted_phone_count,
            "deleted_mfa_count": deleted_mfa_count,
            "failed_count": failed_count,
            "sessions_revoked": sessions_revoked,
            "status": status,
        }
        safe_metadata = self._sanitize(
            {key: value for key, value in metadata.items() if value is not None}
        )
        logger.info(
            "reset_mfa_workflow",
            extra={
                "tool_name": tool_name,
                "request_id": request_id,
                "metadata": safe_metadata,
            },
        )

    def log_runbook_event(
        self,
        tool_name: str,
        runbook_name: str,
        job_name: str,
        parameters_masked: dict[str, Any],
        wait_for_completion: bool,
        timeout_seconds: int,
        status: str,
        success: bool,
        timed_out: bool,
    ) -> None:
        safe_metadata = self._sanitize(
            {
                "runbook_name": runbook_name,
                "job_name": job_name,
                "parameters_masked": parameters_masked,
                "wait_for_completion": wait_for_completion,
                "timeout_seconds": timeout_seconds,
                "status": status,
                "success": success,
                "timed_out": timed_out,
            }
        )

    def log_group_query(
        self,
        tool_name: str,
        user_id: str | None = None,
        group_id: str | None = None,
        platform: str | None = None,
        transitive: bool | None = None,
        status: str | None = None,
        count: int | None = None,
        request_id: str | None = None,
    ) -> None:
        metadata = {
            "user_id": user_id,
            "group_id": group_id,
            "platform": platform,
            "transitive": transitive,
            "status": status,
            "count": count,
        }
        safe_metadata = self._sanitize({key: value for key, value in metadata.items() if value is not None})
        logger.info(
            "group_query",
            extra={
                "tool_name": tool_name,
                "request_id": request_id,
                "metadata": safe_metadata,
            },
        )
        logger.info(
            "runbook_event",
            extra={
                "tool_name": tool_name,
                "metadata": safe_metadata,
            },
        )

    def log_application_query(
        self,
        tool_name: str,
        user_upn: str | None = None,
        days_threshold: int | None = None,
        include_expired: bool | None = None,
        search_display_name: bool | None = None,
        search_owned_apps: bool | None = None,
        status: str | None = None,
        result_count: int | None = None,
        request_id: str | None = None,
    ) -> None:
        metadata = {
            "user_upn": user_upn,
            "days_threshold": days_threshold,
            "include_expired": include_expired,
            "search_display_name": search_display_name,
            "search_owned_apps": search_owned_apps,
            "status": status,
            "result_count": result_count,
        }
        safe_metadata = self._sanitize(
            {key: value for key, value in metadata.items() if value is not None}
        )
        logger.info(
            "application_query",
            extra={
                "tool_name": tool_name,
                "request_id": request_id,
                "metadata": safe_metadata,
            },
        )

    def _sanitize(self, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized
