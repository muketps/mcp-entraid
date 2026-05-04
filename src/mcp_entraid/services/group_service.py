from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from mcp_entraid.graph.client import GraphClient
from mcp_entraid.graph.errors import GraphAPIError
from mcp_entraid.graph.endpoints import GROUP_MEMBER_SELECT_FIELDS, GROUP_SELECT_FIELDS
from mcp_entraid.schemas.groups import (
    EntraGroupMemberSummary,
    EntraGroupSummary,
    GroupComplianceItem,
    ListGroupMembersResponse,
    ListUserGroupsResponse,
    RequiredGroup,
    RequiredGroupsByPlatformResponse,
)
from mcp_entraid.utils.odata import encode_path_segment, select_params

ALLOWED_PLATFORMS = {"windows", "linux", "mac", "mobile"}
BLOCKED_COLLECTION_VALUES = {"all", "*", "todos", "everyone"}


class GroupService:
    def __init__(
        self,
        graph_client: GraphClient,
        user_service,
        required_groups_path: Path | None = None,
    ) -> None:
        self._graph_client = graph_client
        self._user_service = user_service
        self._required_groups_path = required_groups_path or Path(__file__).resolve().parents[1] / "config" / "required_groups_by_platform.json"

    async def check_required_groups_by_platform(self, user_upn: str, platform: str) -> RequiredGroupsByPlatformResponse:
        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            return self._error_required_groups(
                user_id="",
                platform="",
                user_display_name=None,
                user_principal_name="",
                message=f"Falha ao validar usuario: {user_response.error}",
                request_id=user_response.request_id,
            )

        normalized_user_id = user_response.data.user_id
        normalized_platform = self._validate_platform(platform)

        required_groups = self._load_required_groups(normalized_platform)
        try:
            direct_groups = await self._list_groups_for_user(normalized_user_id, transitive=False)
            transitive_groups = await self._list_groups_for_user(normalized_user_id, transitive=True)
        except GraphAPIError as exc:
            return self._error_required_groups(
                user_id=normalized_user_id,
                platform=normalized_platform,
                user_display_name=user_response.data.display_name,
                user_principal_name=user_response.data.user_principal_name or "",
                message=str(exc),
                request_id=exc.request_id,
            )

        direct_group_ids = {group.id for group in direct_groups}
        transitive_group_ids = {group.id for group in transitive_groups}

        all_groups_checked: list[GroupComplianceItem] = []
        direct_required: list[RequiredGroup] = []
        inherited_required: list[RequiredGroup] = []
        missing_required: list[RequiredGroup] = []

        for required_group in required_groups:
            if required_group.group_id in direct_group_ids:
                membership_type = "direct"
                direct_required.append(required_group)
            elif required_group.group_id in transitive_group_ids:
                membership_type = "inherited"
                inherited_required.append(required_group)
            else:
                membership_type = "missing"
                missing_required.append(required_group)

            all_groups_checked.append(
                GroupComplianceItem(
                    group_id=required_group.group_id,
                    display_name=required_group.display_name,
                    description=required_group.description,
                    present=membership_type != "missing",
                    membership_type=membership_type,
                )
            )

        compliant = len(missing_required) == 0
        return RequiredGroupsByPlatformResponse(
            success=True,
            user_id=normalized_user_id,
            user_display_name=user_response.data.display_name,
            user_principal_name=user_response.data.user_principal_name or "",
            platform=normalized_platform,
            compliant=compliant,
            required_groups_count=len(required_groups),
            direct_groups_count=len(direct_required),
            inherited_groups_count=len(inherited_required),
            missing_groups_count=len(missing_required),
            direct_groups=direct_required,
            inherited_groups=inherited_required,
            missing_groups=missing_required,
            all_groups_checked=all_groups_checked,
            message=(
                "Usuario em conformidade com os grupos obrigatorios."
                if compliant
                else "Usuario nao esta em conformidade com os grupos obrigatorios."
            ),
            request_id=None,
        )

    async def list_user_groups(self, user_upn: str, transitive: bool = True) -> ListUserGroupsResponse:
        user_response = await self._user_service.get_user(user_upn)
        if not user_response.success or user_response.data is None:
            return ListUserGroupsResponse(
                success=False,
                user_id="",
                user_principal_name="",
                user_display_name=None,
                transitive=transitive,
                groups_count=0,
                groups=[],
                message=f"Falha ao validar usuario: {user_response.error}",
                request_id=user_response.request_id,
            )

        normalized_user_id = user_response.data.user_id
        try:
            groups = await self._list_groups_for_user(normalized_user_id, transitive=transitive)
        except GraphAPIError as exc:
            return ListUserGroupsResponse(
                success=False,
                user_id=normalized_user_id,
                user_principal_name=user_response.data.user_principal_name or "",
                user_display_name=user_response.data.display_name,
                transitive=transitive,
                groups_count=0,
                groups=[],
                message=str(exc),
                request_id=exc.request_id,
            )

        return ListUserGroupsResponse(
            success=True,
            user_id=normalized_user_id,
            user_principal_name=user_response.data.user_principal_name or "",
            user_display_name=user_response.data.display_name,
            transitive=transitive,
            groups_count=len(groups),
            groups=groups,
            message="Grupos retornados com sucesso.",
            request_id=None,
        )

    async def list_group_members(self, group_id: str, transitive: bool = True) -> ListGroupMembersResponse:
        normalized_group_id = self._validate_group_id(group_id)
        try:
            members = await self._list_members_for_group(normalized_group_id, transitive=transitive)
        except GraphAPIError as exc:
            return ListGroupMembersResponse(
                success=False,
                group_id=normalized_group_id,
                transitive=transitive,
                members_count=0,
                members=[],
                message=str(exc),
                request_id=exc.request_id,
            )

        return ListGroupMembersResponse(
            success=True,
            group_id=normalized_group_id,
            transitive=transitive,
            members_count=len(members),
            members=members,
            message="Membros retornados com sucesso.",
            request_id=None,
        )

    async def _list_groups_for_user(self, user_id: str, transitive: bool) -> list[EntraGroupSummary]:
        path = (
            f"/users/{encode_path_segment(user_id)}/transitiveMemberOf/microsoft.graph.group"
            if transitive
            else f"/users/{encode_path_segment(user_id)}/memberOf/microsoft.graph.group"
        )
        params = select_params(GROUP_SELECT_FIELDS)
        return await self._collect_paged_groups(path, params)

    async def _list_members_for_group(self, group_id: str, transitive: bool) -> list[EntraGroupMemberSummary]:
        path = (
            f"/groups/{encode_path_segment(group_id)}/transitiveMembers/microsoft.graph.user"
            if transitive
            else f"/groups/{encode_path_segment(group_id)}/members"
        )
        params = select_params(GROUP_MEMBER_SELECT_FIELDS)
        return await self._collect_paged_members(path, params)

    async def _collect_paged_groups(
        self,
        path: str,
        params: dict[str, str],
    ) -> list[EntraGroupSummary]:
        items: list[EntraGroupSummary] = []
        payload = await self._graph_client.get(path, params=params)
        while True:
            items.extend(self._map_groups(payload.get("value", [])))
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                break
            payload = await self._graph_client.get_absolute(next_link)
        return items

    async def _collect_paged_members(
        self,
        path: str,
        params: dict[str, str],
    ) -> list[EntraGroupMemberSummary]:
        items: list[EntraGroupMemberSummary] = []
        payload = await self._graph_client.get(path, params=params)
        while True:
            items.extend(self._map_members(payload.get("value", [])))
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                break
            payload = await self._graph_client.get_absolute(next_link)
        return items

    def _map_groups(self, payload: list[dict]) -> list[EntraGroupSummary]:
        return [
            EntraGroupSummary(
                id=item["id"],
                display_name=item.get("displayName"),
                mail_enabled=item.get("mailEnabled"),
                security_enabled=item.get("securityEnabled"),
                group_types=list(item.get("groupTypes", [])),
            )
            for item in payload
            if "id" in item
        ]

    def _map_members(self, payload: list[dict]) -> list[EntraGroupMemberSummary]:
        members: list[EntraGroupMemberSummary] = []
        for item in payload:
            object_type = item.get("@odata.type")
            if object_type and "user" not in object_type.lower():
                continue
            if "userPrincipalName" not in item and object_type is None:
                continue
            members.append(
                EntraGroupMemberSummary(
                    id=item["id"],
                    display_name=item.get("displayName"),
                    user_principal_name=item.get("userPrincipalName"),
                    mail=item.get("mail"),
                    object_type=object_type,
                )
            )
        return members

    def _load_required_groups(self, platform: str) -> list[RequiredGroup]:
        return _load_required_groups_from_disk(str(self._required_groups_path), platform)

    def _validate_platform(self, platform: str) -> str:
        normalized = (platform or "").strip().lower()
        if normalized not in ALLOWED_PLATFORMS:
            raise ValueError("Informe uma plataforma valida: windows, linux, mac ou mobile.")
        return normalized

    def _validate_group_id(self, group_id: str) -> str:
        normalized = (group_id or "").strip()
        if not normalized:
            raise ValueError("Informe um group_id valido.")
        if normalized.lower() in BLOCKED_COLLECTION_VALUES:
            raise ValueError("Informe um group_id real. Valores amplos nao sao permitidos.")
        try:
            UUID(normalized)
        except ValueError as exc:
            raise ValueError("group_id deve ser um GUID valido.") from exc
        return normalized

    def _error_required_groups(
        self,
        user_id: str,
        platform: str,
        user_display_name: str | None,
        user_principal_name: str,
        message: str,
        request_id: str | None,
    ) -> RequiredGroupsByPlatformResponse:
        return RequiredGroupsByPlatformResponse(
            success=False,
            user_id=user_id,
            user_display_name=user_display_name,
            user_principal_name=user_principal_name,
            platform=platform,
            compliant=False,
            required_groups_count=0,
            direct_groups_count=0,
            inherited_groups_count=0,
            missing_groups_count=0,
            direct_groups=[],
            inherited_groups=[],
            missing_groups=[],
            all_groups_checked=[],
            message=message,
            request_id=request_id,
        )


@lru_cache
def _load_required_groups_from_disk(required_groups_path: str, platform: str) -> list[RequiredGroup]:
    with Path(required_groups_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    groups = payload.get(platform, [])
    return [
        RequiredGroup(
            group_id=item["group_id"],
            display_name=item["display_name"],
            description=item.get("description"),
        )
        for item in groups
        if isinstance(item, dict) and item.get("group_id") and item.get("display_name")
    ]
