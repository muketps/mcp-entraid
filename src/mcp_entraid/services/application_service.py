from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mcp_entraid.graph.client import GraphClient
from mcp_entraid.graph.endpoints import APPLICATION_SELECT_FIELDS
from mcp_entraid.graph.errors import GraphAPIError
from mcp_entraid.schemas.applications import (
    AppCredentialSummary,
    AppRegistrationUserMatch,
    ExpiringAppCredentialItem,
    ExpiringAppCredentialsResponse,
    FindAppRegistrationsByUserResponse,
)
from mcp_entraid.services.user_service import UserService
from mcp_entraid.utils.odata import encode_path_segment, select_params

BLOCKED_COLLECTION_VALUES = {"all", "*", "todos", "everyone", "tenant"}


@dataclass(slots=True)
class _ApplicationRecord:
    id: str
    app_id: str
    display_name: str | None
    created_date_time: str | None
    password_credentials: list[dict[str, Any]]
    key_credentials: list[dict[str, Any]]


class ApplicationService:
    def __init__(self, graph_client: GraphClient, user_service: UserService) -> None:
        self._graph_client = graph_client
        self._user_service = user_service

    async def list_expiring_app_credentials(
        self,
        days_threshold: int = 30,
        include_expired: bool = True,
        include_certificates: bool = True,
        include_secrets: bool = True,
    ) -> ExpiringAppCredentialsResponse:
        self._validate_days_threshold(days_threshold)
        try:
            applications = await self._load_all_applications()
        except GraphAPIError as exc:
            return self._error_expiring_credentials(
                days_threshold=days_threshold,
                include_expired=include_expired,
                message=str(exc),
                request_id=exc.request_id,
            )

        now = datetime.now(timezone.utc)
        items: list[ExpiringAppCredentialItem] = []
        for app in applications:
            if include_secrets:
                items.extend(
                    self._collect_expiring_credentials_for_app(
                        app,
                        app.password_credentials,
                        credential_type="secret",
                        days_threshold=days_threshold,
                        include_expired=include_expired,
                        now=now,
                    )
                )
            if include_certificates:
                items.extend(
                    self._collect_expiring_credentials_for_app(
                        app,
                        app.key_credentials,
                        credential_type="certificate",
                        days_threshold=days_threshold,
                        include_expired=include_expired,
                        now=now,
                    )
                )

        items.sort(
            key=lambda item: (
                self._sort_key_for_expiration(item.credential.end_date_time),
                item.display_name.lower(),
            )
        )

        applications_count = len({item.application_object_id for item in items})
        message = (
            "Nenhuma credencial de application registration expirando foi encontrada."
            if not items
            else "Credenciais de application registration expirando retornadas com sucesso."
        )
        return ExpiringAppCredentialsResponse(
            success=True,
            days_threshold=days_threshold,
            include_expired=include_expired,
            expiring_credentials_count=len(items),
            applications_count=applications_count,
            items=items,
            message=message,
            request_id=None,
        )

    async def find_app_registrations_by_user(
        self,
        user_upn: str,
        search_display_name: bool = True,
        search_owned_apps: bool = True,
    ) -> FindAppRegistrationsByUserResponse:
        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            return FindAppRegistrationsByUserResponse(
                success=False,
                user_id="",
                user_principal_name="",
                user_display_name=None,
                matches_count=0,
                matches=[],
                message=f"Falha ao validar usuario: {user_response.error}",
                request_id=user_response.request_id,
            )

        user = user_response.data
        if not search_display_name and not search_owned_apps:
            return FindAppRegistrationsByUserResponse(
                success=True,
                user_id=user.user_id,
                user_principal_name=user.user_principal_name or user_upn,
                user_display_name=user.display_name,
                matches_count=0,
                matches=[],
                message="Nenhum criterio de busca habilitado.",
                request_id=None,
            )

        try:
            applications = await self._load_all_applications()
            application_by_id = {app.id: app for app in applications}
            owned_application_ids = (
                await self._load_owned_application_ids(user.user_id)
                if search_owned_apps
                else set()
            )
        except GraphAPIError as exc:
            return FindAppRegistrationsByUserResponse(
                success=False,
                user_id=user.user_id,
                user_principal_name=user.user_principal_name or user_upn,
                user_display_name=user.display_name,
                matches_count=0,
                matches=[],
                message=str(exc),
                request_id=exc.request_id,
            )

        matches: dict[str, dict[str, Any]] = {}
        if search_owned_apps:
            for application_id in owned_application_ids:
                application = application_by_id.get(application_id)
                if application is None:
                    continue
                self._upsert_match(matches, application, "owner", "Usuario e owner do application registration.")

        if search_display_name:
            search_terms = self._build_search_terms(user.user_principal_name or user_upn, user.display_name)
            for application in applications:
                if self._matches_display_name(application, search_terms):
                    self._upsert_match(
                        matches,
                        application,
                        "display_name",
                        "Nome do application registration corresponde ao usuario.",
                    )

        match_models = self._build_match_models(matches)
        match_models.sort(key=lambda item: item.display_name.lower())
        message = (
            "Nenhum application registration relacionado ao usuario foi encontrado."
            if not match_models
            else "Application registrations relacionados ao usuario retornados com sucesso."
        )
        return FindAppRegistrationsByUserResponse(
            success=True,
            user_id=user.user_id,
            user_principal_name=user.user_principal_name or user_upn,
            user_display_name=user.display_name,
            matches_count=len(match_models),
            matches=match_models,
            message=message,
            request_id=None,
        )

    async def _load_all_applications(self) -> list[_ApplicationRecord]:
        path = "/applications"
        params = select_params(APPLICATION_SELECT_FIELDS)
        records: list[_ApplicationRecord] = []
        payload = await self._graph_client.get(path, params=params)
        while True:
            records.extend(self._map_applications(payload.get("value", [])))
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                break
            payload = await self._graph_client.get_absolute(next_link)
        return records

    async def _load_owned_application_ids(self, user_id: str) -> set[str]:
        path = f"/users/{encode_path_segment(user_id)}/ownedObjects"
        payload = await self._graph_client.get(path)
        application_ids: set[str] = set()
        while True:
            for item in payload.get("value", []):
                if self._is_application_object(item):
                    item_id = item.get("id")
                    if isinstance(item_id, str) and item_id:
                        application_ids.add(item_id)
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                break
            payload = await self._graph_client.get_absolute(next_link)
        return application_ids

    def _map_applications(self, payload: list[dict[str, Any]]) -> list[_ApplicationRecord]:
        records: list[_ApplicationRecord] = []
        for item in payload:
            app_id = item.get("id")
            app_app_id = item.get("appId")
            if not isinstance(app_id, str) or not app_id:
                continue
            if not isinstance(app_app_id, str) or not app_app_id:
                continue
            records.append(
                _ApplicationRecord(
                    id=app_id,
                    app_id=app_app_id,
                    display_name=item.get("displayName"),
                    created_date_time=item.get("createdDateTime"),
                    password_credentials=self._ensure_list(item.get("passwordCredentials")),
                    key_credentials=self._ensure_list(item.get("keyCredentials")),
                )
            )
        return records

    def _collect_expiring_credentials_for_app(
        self,
        app: _ApplicationRecord,
        credentials: list[dict[str, Any]],
        credential_type: str,
        days_threshold: int,
        include_expired: bool,
        now: datetime,
    ) -> list[ExpiringAppCredentialItem]:
        items: list[ExpiringAppCredentialItem] = []
        for credential in credentials:
            summary = self._build_credential_summary(credential, credential_type, days_threshold, now)
            if summary.status == "expired" and not include_expired:
                continue
            if summary.status not in {"expired", "expiring_soon"}:
                continue
            items.append(
                ExpiringAppCredentialItem(
                    application_object_id=app.id,
                    app_id=app.app_id,
                    display_name=app.display_name or app.app_id,
                    credential=summary,
                )
            )
        return items

    def _build_credential_summary(
        self,
        credential: dict[str, Any],
        credential_type: str,
        days_threshold: int,
        now: datetime,
    ) -> AppCredentialSummary:
        end_date_time = self._normalize_datetime_string(credential.get("endDateTime"))
        start_date_time = self._normalize_datetime_string(credential.get("startDateTime"))
        days_until_expiration = self._days_until_expiration(end_date_time, now)
        status = "valid"
        if days_until_expiration is not None:
            if days_until_expiration < 0:
                status = "expired"
            elif days_until_expiration <= days_threshold:
                status = "expiring_soon"

        return AppCredentialSummary(
            credential_id=self._credential_id(credential),
            credential_type=credential_type,
            display_name=credential.get("displayName"),
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            days_until_expiration=days_until_expiration,
            status=status,
        )

    def _build_match_models(self, matches: dict[str, dict[str, Any]]) -> list[AppRegistrationUserMatch]:
        models: list[AppRegistrationUserMatch] = []
        for match in matches.values():
            application = match["application"]
            reasons = [reason for reason in match["reasons"] if reason]
            models.append(
                AppRegistrationUserMatch(
                    application_object_id=application.id,
                    app_id=application.app_id,
                    display_name=application.display_name or application.app_id,
                    created_date_time=application.created_date_time,
                    match_type=self._match_type_from_sources(match["sources"]),
                    matched_reason="; ".join(dict.fromkeys(reasons)),
                    secret_credentials_count=len(application.password_credentials),
                    certificate_credentials_count=len(application.key_credentials),
                    nearest_credential_expiration=self._nearest_credential_expiration(application),
                )
            )
        return models

    def _upsert_match(
        self,
        matches: dict[str, dict[str, Any]],
        application: _ApplicationRecord,
        source: str,
        reason: str,
    ) -> None:
        entry = matches.setdefault(
            application.id,
            {
                "application": application,
                "sources": set(),
                "reasons": [],
            },
        )
        entry["sources"].add(source)
        entry["reasons"].append(reason)

    def _match_type_from_sources(self, sources: set[str]) -> str:
        if sources == {"owner", "display_name"}:
            return "owner_and_display_name"
        if "owner" in sources:
            return "owner"
        return "display_name"

    def _matches_display_name(self, application: _ApplicationRecord, search_terms: list[str]) -> bool:
        display_name = (application.display_name or "").lower()
        if not display_name:
            return False
        return any(term in display_name for term in search_terms if term)

    def _build_search_terms(self, user_principal_name: str, user_display_name: str | None) -> list[str]:
        local_part = user_principal_name.split("@", 1)[0] if "@" in user_principal_name else user_principal_name
        terms = [user_principal_name, local_part, user_display_name or ""]
        return [term.strip().lower() for term in terms if term and term.strip()]

    def _nearest_credential_expiration(self, application: _ApplicationRecord) -> str | None:
        expiration_dates: list[datetime] = []
        for credential in application.password_credentials + application.key_credentials:
            end_date_time = self._parse_datetime(credential.get("endDateTime"))
            if end_date_time is not None:
                expiration_dates.append(end_date_time)
        if not expiration_dates:
            return None
        return min(expiration_dates).isoformat().replace("+00:00", "Z")

    def _credential_id(self, credential: dict[str, Any]) -> str | None:
        for key in ("keyId", "id"):
            value = credential.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _days_until_expiration(self, end_date_time: str | None, now: datetime) -> int | None:
        parsed = self._parse_datetime(end_date_time)
        if parsed is None:
            return None
        delta = parsed - now
        return int(delta.total_seconds() // 86400)

    def _sort_key_for_expiration(self, end_date_time: str | None) -> datetime:
        parsed = self._parse_datetime(end_date_time)
        if parsed is None:
            return datetime.max.replace(tzinfo=timezone.utc)
        return parsed

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _normalize_datetime_string(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        parsed = self._parse_datetime(value)
        if parsed is None:
            return value
        return parsed.isoformat().replace("+00:00", "Z")

    def _is_application_object(self, item: dict[str, Any]) -> bool:
        object_type = item.get("@odata.type")
        if isinstance(object_type, str) and object_type.lower() == "#microsoft.graph.application":
            return True
        if item.get("appId") and item.get("displayName"):
            return True
        return False

    def _ensure_list(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _validate_days_threshold(self, days_threshold: int) -> None:
        if not isinstance(days_threshold, int):
            raise ValueError("days_threshold deve ser um inteiro.")
        if days_threshold < 1 or days_threshold > 365:
            raise ValueError("days_threshold deve estar entre 1 e 365.")

    def _error_expiring_credentials(
        self,
        days_threshold: int,
        include_expired: bool,
        message: str,
        request_id: str | None,
    ) -> ExpiringAppCredentialsResponse:
        return ExpiringAppCredentialsResponse(
            success=False,
            days_threshold=days_threshold,
            include_expired=include_expired,
            expiring_credentials_count=0,
            applications_count=0,
            items=[],
            message=message,
            request_id=request_id,
        )
