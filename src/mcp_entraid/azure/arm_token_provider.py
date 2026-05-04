from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from mcp_entraid.settings import Settings


class ArmTokenError(RuntimeError):
    """Erro ao obter token para Azure Resource Manager."""


@dataclass
class CachedArmToken:
    access_token: str
    expires_at: float


class ArmTokenProvider:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http_client = http_client
        self._cached_token: CachedArmToken | None = None

    async def get_access_token(self) -> str:
        if self._cached_token and self._cached_token.expires_at > time.time():
            return self._cached_token.access_token

        token = await self._request_token()
        self._cached_token = token
        return token.access_token

    async def _request_token(self) -> CachedArmToken:
        if not self._settings.azure_tenant_id or not self._settings.azure_client_id or not self._settings.azure_client_secret:
            raise ArmTokenError("Configuração Azure incompleta para autenticação ARM.")

        url = f"https://login.microsoftonline.com/{self._settings.azure_tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self._settings.azure_client_id,
            "client_secret": self._settings.azure_client_secret,
            "scope": "https://management.azure.com/.default",
            "grant_type": "client_credentials",
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, data=data)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, data=data)
        except httpx.HTTPError as exc:
            raise ArmTokenError("Falha ao conectar ao endpoint de token do Azure.") from exc

        if response.status_code >= 400:
            raise ArmTokenError("Falha ao autenticar no Azure Resource Manager.")

        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not access_token:
            raise ArmTokenError("Resposta de token do Azure sem access_token.")

        safety_window_seconds = 60
        return CachedArmToken(
            access_token=access_token,
            expires_at=time.time() + max(expires_in - safety_window_seconds, 0),
        )
