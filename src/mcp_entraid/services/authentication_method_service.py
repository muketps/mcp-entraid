from __future__ import annotations

from mcp_entraid.graph.client import GraphClient
from mcp_entraid.graph.endpoints import PHONE_METHOD_DELETE_ORDER
from mcp_entraid.graph.errors import GraphAPIError
from mcp_entraid.schemas.authentication_methods import (
    AuthenticationMethodOperationResult,
    AuthenticationMethodSummary,
)
from mcp_entraid.utils.odata import encode_path_segment


class AuthenticationMethodService:
    def __init__(self, graph_client: GraphClient) -> None:
        self._graph_client = graph_client

    async def list_phone_methods(self, user_id: str) -> list[AuthenticationMethodSummary]:
        payload = await self._graph_client.get(
            f"/users/{encode_path_segment(user_id)}/authentication/phoneMethods"
        )
        methods = [self._map_phone_method(item) for item in payload.get("value", [])]
        return sorted(
            methods,
            key=lambda method: PHONE_METHOD_DELETE_ORDER.get(method.id, 99),
        )

    async def list_microsoft_authenticator_methods(
        self,
        user_id: str,
    ) -> list[AuthenticationMethodSummary]:
        payload = await self._graph_client.get(
            f"/users/{encode_path_segment(user_id)}/authentication/microsoftAuthenticatorMethods"
        )
        return [self._map_microsoft_authenticator_method(item) for item in payload.get("value", [])]

    async def delete_phone_method(
        self,
        user_id: str,
        method: AuthenticationMethodSummary,
    ) -> AuthenticationMethodOperationResult:
        path = (
            f"/users/{encode_path_segment(user_id)}/authentication/"
            f"phoneMethods/{encode_path_segment(method.id)}"
        )
        return await self._delete_method(path, method)

    async def delete_microsoft_authenticator_method(
        self,
        user_id: str,
        method: AuthenticationMethodSummary,
    ) -> AuthenticationMethodOperationResult:
        path = (
            f"/users/{encode_path_segment(user_id)}/authentication/"
            f"microsoftAuthenticatorMethods/{encode_path_segment(method.id)}"
        )
        return await self._delete_method(path, method)

    async def revoke_sign_in_sessions(self, user_id: str) -> bool:
        payload = await self._graph_client.post(
            f"/users/{encode_path_segment(user_id)}/revokeSignInSessions"
        )
        value = payload.get("value")
        return bool(value) if value is not None else True

    async def _delete_method(
        self,
        path: str,
        method: AuthenticationMethodSummary,
    ) -> AuthenticationMethodOperationResult:
        try:
            await self._graph_client.delete(path)
        except GraphAPIError as exc:
            return AuthenticationMethodOperationResult(
                id=method.id,
                type=method.type,
                display_name=method.display_name,
                status="failed",
                reason=str(exc),
            )

        return AuthenticationMethodOperationResult(
            id=method.id,
            type=method.type,
            display_name=method.display_name,
            status="deleted",
            reason=None,
        )

    def _map_phone_method(self, payload: dict) -> AuthenticationMethodSummary:
        phone_type = payload.get("phoneType")
        display_name = phone_type or "Phone method"
        return AuthenticationMethodSummary(
            id=payload["id"],
            type="phoneMethod",
            display_name=display_name,
            phone_type=phone_type,
            phone_number_masked=self._mask_phone_number(payload.get("phoneNumber")),
            status=payload.get("smsSignInState"),
            reason=None,
        )

    def _map_microsoft_authenticator_method(self, payload: dict) -> AuthenticationMethodSummary:
        display_name = payload.get("displayName") or payload.get("deviceTag") or "Microsoft Authenticator"
        return AuthenticationMethodSummary(
            id=payload["id"],
            type="microsoftAuthenticatorMethod",
            display_name=display_name,
            phone_type=None,
            phone_number_masked=None,
            status=None,
            reason=None,
        )

    def _mask_phone_number(self, phone_number: str | None) -> str | None:
        if not phone_number:
            return None

        digits = "".join(character for character in phone_number if character.isdigit())
        if len(digits) <= 4:
            return "***"

        return f"***-{digits[-4:]}"
