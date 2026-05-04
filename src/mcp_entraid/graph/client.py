from __future__ import annotations

from typing import Any

import httpx

from mcp_entraid.auth.graph_token_provider import GraphTokenError, GraphTokenProvider
from mcp_entraid.graph.errors import (
    GraphAPIError,
    GraphAuthenticationError,
    GraphNotFoundError,
    GraphPermissionError,
    GraphServerError,
    GraphThrottlingError,
)
from mcp_entraid.settings import Settings


class GraphClient:
    def __init__(
        self,
        settings: Settings,
        token_provider: GraphTokenProvider,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._token_provider = token_provider
        self._http_client = http_client

    async def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return await self.request("GET", path, params=params)

    async def get_absolute(self, url: str) -> dict[str, Any]:
        return await self.request_absolute("GET", url)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("POST", path, json=json)

    async def delete(self, path: str) -> None:
        await self.request("DELETE", path, expect_json=False)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        return await self.request_absolute(method, url, params=params, json=json, expect_json=expect_json)

    async def request_absolute(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        try:
            token = await self._token_provider.get_access_token()
        except GraphTokenError as exc:
            raise GraphAuthenticationError(
                status_code=401,
                message="Erro de autenticação ao obter token do Microsoft Graph.",
            ) from exc

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                )
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                        headers=headers,
                    )
        except httpx.HTTPError as exc:
            raise GraphAPIError(
                status_code=0,
                message="Falha de comunicação com o Microsoft Graph.",
            ) from exc

        if response.status_code >= 400:
            self._raise_for_error(response)

        if response.status_code == 204 or not expect_json:
            return {}

        return response.json()

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._settings.graph_base_url_str}{normalized_path}"

    def _raise_for_error(self, response: httpx.Response) -> None:
        request_id = response.headers.get("request-id") or response.headers.get("client-request-id")
        retry_after_header = response.headers.get("Retry-After")
        retry_after = int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None
        message = self._extract_graph_error_message(response)

        if response.status_code == 401:
            raise GraphAuthenticationError(401, "Erro de autenticação no Microsoft Graph.", request_id)
        if response.status_code == 403:
            raise GraphPermissionError(403, "Permissão insuficiente para consultar o Microsoft Graph.", request_id)
        if response.status_code == 404:
            raise GraphNotFoundError(404, "Recurso não encontrado no Microsoft Graph.", request_id)
        if response.status_code == 429:
            throttling_message = "Microsoft Graph aplicou throttling. Tente novamente mais tarde."
            if retry_after is not None:
                throttling_message = f"{throttling_message} Retry-After: {retry_after} segundo(s)."
            raise GraphThrottlingError(429, throttling_message, request_id, retry_after)
        if response.status_code >= 500:
            raise GraphServerError(response.status_code, "Erro interno do Microsoft Graph.", request_id)

        raise GraphAPIError(response.status_code, message, request_id)

    def _extract_graph_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Erro inesperado do Microsoft Graph."

        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message

        return "Erro inesperado do Microsoft Graph."
