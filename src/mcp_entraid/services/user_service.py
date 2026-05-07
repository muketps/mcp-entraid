from __future__ import annotations

import re

from mcp_entraid.graph.client import GraphClient
from mcp_entraid.graph.endpoints import DIRECT_REPORT_SELECT_FIELDS, USER_SELECT_FIELDS
from mcp_entraid.graph.errors import GraphAPIError
from mcp_entraid.schemas.common import ToolResponse
from mcp_entraid.schemas.users import EntraUser
from mcp_entraid.utils.odata import encode_path_segment, select_params

BLOCKED_USER_VALUES = {"*", "all", "todos", "everyone", "tenant", "organization"}
UPN_PATTERN = re.compile(r"^[^@\s,;|]+@[^@\s,;|]+\.[^@\s,;|]+$")


class UserService:
    def __init__(self, graph_client: GraphClient) -> None:
        self._graph_client = graph_client

    async def get_user(self, user_upn: str) -> ToolResponse[EntraUser]:
        try:
            normalized_user_upn = self._validate_user_upn(user_upn)
        except ValueError as exc:
            return ToolResponse[EntraUser](success=False, error=str(exc), request_id=None)

        path = f"/users/{encode_path_segment(normalized_user_upn)}"
        try:
            payload = await self._graph_client.get(path, params=select_params(USER_SELECT_FIELDS))
            user = EntraUser.model_validate(payload)
            return ToolResponse[EntraUser](success=True, data=user)
        except GraphAPIError as exc:
            return ToolResponse[EntraUser](
                success=False,
                error=str(exc),
                request_id=exc.request_id,
            )

    async def get_direct_reports(self, user_upn: str) -> ToolResponse[list[EntraUser]]:
        user_response = await self.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            return ToolResponse[list[EntraUser]](
                success=False,
                error=user_response.error,
                request_id=user_response.request_id,
            )

        path = f"/users/{encode_path_segment(user_response.data.user_id)}/directReports"
        try:
            payload = await self._graph_client.get(path, params=select_params(DIRECT_REPORT_SELECT_FIELDS))
            users = [EntraUser.model_validate(item) for item in payload.get("value", [])]
            return ToolResponse[list[EntraUser]](success=True, data=users)
        except GraphAPIError as exc:
            return ToolResponse[list[EntraUser]](
                success=False,
                error=str(exc),
                request_id=exc.request_id,
            )

    def _validate_user_upn(self, user_upn: str) -> str:
        if not isinstance(user_upn, str):
            raise ValueError("user_upn deve ser uma string.")

        normalized = user_upn.strip()
        if not normalized:
            raise ValueError("user_upn e obrigatorio.")
        if normalized.lower() in BLOCKED_USER_VALUES:
            raise ValueError("Informe apenas um UPN de usuario. Valores amplos nao sao permitidos.")
        if any(sep in normalized for sep in (",", ";", "|", " ")):
            raise ValueError("Informe apenas um UPN. Multiplos UPNs nao sao permitidos.")
        if not UPN_PATTERN.match(normalized):
            raise ValueError("user_upn deve parecer um UPN valido, como usuario@dominio.com.")
        return normalized
