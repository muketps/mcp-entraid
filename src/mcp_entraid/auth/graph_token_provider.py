from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from mcp_entraid.settings import Settings


class GraphTokenError(RuntimeError):
    """Erro ao obter token para o Microsoft Graph."""


@dataclass
class CachedToken:
    access_token: str
    expires_at: float


class GraphTokenProvider:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http_client = http_client
        self._cached_token: CachedToken | None = None

    async def get_access_token(self) -> str:
        if self._cached_token and self._cached_token.expires_at > time.time():
            return self._cached_token.access_token

        token = await self._request_token()
        self._cached_token = token
        return token.access_token

    async def _request_token(self) -> CachedToken:
        url = (
            f"https://login.microsoftonline.com/"
            f"{self._settings.tenant_id}/oauth2/v2.0/token"
        )
        data = {
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "scope": self._settings.graph_scope,
            "grant_type": "client_credentials",
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, data=data)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, data=data)
        except httpx.HTTPError as exc:
            raise GraphTokenError("Falha ao conectar ao endpoint de token do Microsoft Entra ID.") from exc

        if response.status_code >= 400:
            raise GraphTokenError("Falha ao autenticar no Microsoft Entra ID usando client credentials.")

        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not access_token:
            raise GraphTokenError("Resposta de token sem access_token.")

        safety_window_seconds = 60
        return CachedToken(
            access_token=access_token,
            expires_at=time.time() + max(expires_in - safety_window_seconds, 0),
        )
