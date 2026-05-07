from __future__ import annotations

from pydantic import BaseModel


class RequiredGroup(BaseModel):
    group_id: str
    display_name: str
    description: str | None = None


class GroupComplianceItem(BaseModel):
    group_id: str
    display_name: str
    description: str | None = None
    present: bool
    membership_type: str


class RequiredGroupsByPlatformResponse(BaseModel):
    success: bool
    user_id: str
    user_display_name: str | None = None
    user_principal_name: str
    platform: str
    compliant: bool
    required_groups_count: int
    direct_groups_count: int
    inherited_groups_count: int
    missing_groups_count: int
    direct_groups: list[RequiredGroup]
    inherited_groups: list[RequiredGroup]
    missing_groups: list[RequiredGroup]
    all_groups_checked: list[GroupComplianceItem]
    message: str
    request_id: str | None = None


class EntraGroupSummary(BaseModel):
    id: str
    display_name: str | None = None
    mail_enabled: bool | None = None
    security_enabled: bool | None = None
    group_types: list[str]


class EntraGroupMemberSummary(BaseModel):
    id: str
    display_name: str | None = None
    user_principal_name: str | None = None
    mail: str | None = None
    object_type: str | None = None


class ListUserGroupsResponse(BaseModel):
    success: bool
    user_id: str
    user_principal_name: str
    user_display_name: str | None = None
    transitive: bool
    groups_count: int
    groups: list[EntraGroupSummary]
    message: str
    request_id: str | None = None


class ListGroupMembersResponse(BaseModel):
    success: bool
    group_id: str
    transitive: bool
    members_count: int
    members: list[EntraGroupMemberSummary]
    message: str
    request_id: str | None = None


class GroupMembershipMutationResponse(BaseModel):
    success: bool
    group_id: str
    user_id: str
    user_principal_name: str
    user_display_name: str | None = None
    action: str
    message: str
    request_id: str | None = None


class FindGroupsResponse(BaseModel):
    success: bool
    query: str
    exact_match: bool
    groups_count: int
    groups: list[EntraGroupSummary]
    message: str
    request_id: str | None = None
