import pytest

from mcp_entraid.schemas.groups import EntraGroupMemberSummary, EntraGroupSummary
from mcp_entraid.schemas.users import EntraUser
from mcp_entraid.services.group_service import GroupService


class FakeUserService:
    async def get_user(self, user_upn: str):
        if user_upn in {"all", "*", "todos", "everyone", "tenant"}:
            return type(
                "Response",
                (),
                {
                    "success": False,
                    "data": None,
                    "request_id": None,
                    "error": "Informe apenas um UPN de usuario. Valores amplos nao sao permitidos.",
                },
            )()
        return type(
            "Response",
            (),
            {
                "success": True,
                "data": EntraUser(
                    user_id="user-123",
                    user_display_name="Alice Silva",
                    user_principal_name="alice@example.com",
                ),
                "request_id": None,
                "error": None,
            },
        )()


class FakeGraphClient:
    def __init__(self) -> None:
        self.absolute_calls: list[str] = []

    async def get(self, path: str, params: dict[str, str] | None = None):
        if path.endswith("/memberOf/microsoft.graph.group"):
            return {
                "value": [
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "displayName": "GRP-Windows-Baseline",
                        "mailEnabled": False,
                        "securityEnabled": True,
                        "groupTypes": [],
                    }
                ]
            }
        if path.endswith("/transitiveMemberOf/microsoft.graph.group"):
            return {
                "value": [
                    {
                        "id": "00000000-0000-0000-0000-000000000002",
                        "displayName": "GRP-Linux-Baseline",
                        "mailEnabled": False,
                        "securityEnabled": True,
                        "groupTypes": [],
                    },
                    {
                        "id": "00000000-0000-0000-0000-000000000005",
                        "displayName": "GRP-Windows-Security-AddOn",
                        "mailEnabled": False,
                        "securityEnabled": True,
                        "groupTypes": [],
                    }
                ]
            }
        if path.endswith("/groups/00000000-0000-0000-0000-000000000010/members"):
            return {
                "value": [
                    {
                        "id": "user-1",
                        "displayName": "Bob",
                        "userPrincipalName": "bob@example.com",
                        "mail": "bob@example.com",
                        "@odata.type": "#microsoft.graph.user",
                    }
                ],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/groups/00000000-0000-0000-0000-000000000010/members?skiptoken=2",
            }
        if path.endswith("/groups/00000000-0000-0000-0000-000000000010/transitiveMembers/microsoft.graph.user"):
            return {
                "value": [
                    {
                        "id": "user-2",
                        "displayName": "Carol",
                        "userPrincipalName": "carol@example.com",
                        "mail": "carol@example.com",
                        "@odata.type": "#microsoft.graph.user",
                    }
                ]
            }
        if path.endswith("/users/user-123/memberOf/microsoft.graph.group") or path.endswith(
            "/users/user-123/transitiveMemberOf/microsoft.graph.group"
        ):
            return {
                "value": [
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "displayName": "GRP-Windows-Baseline",
                        "mailEnabled": False,
                        "securityEnabled": True,
                        "groupTypes": [],
                    }
                ]
            }
        return {"value": []}

    async def get_absolute(self, url: str):
        self.absolute_calls.append(url)
        return {
            "value": [
                {
                    "id": "user-2",
                    "displayName": "Carol",
                    "userPrincipalName": "carol@example.com",
                    "mail": "carol@example.com",
                    "@odata.type": "#microsoft.graph.user",
                }
            ]
        }


@pytest.mark.asyncio
async def test_check_required_groups_marks_direct_inherited_and_missing():
    service = GroupService(FakeGraphClient(), FakeUserService())

    windows = await service.check_required_groups_by_platform("alice@example.com", "windows")
    linux = await service.check_required_groups_by_platform("alice@example.com", "linux")
    mobile = await service.check_required_groups_by_platform("alice@example.com", "mobile")

    assert windows.compliant is True
    assert windows.direct_groups_count == 1
    assert windows.inherited_groups_count == 1
    assert windows.missing_groups_count == 0
    assert windows.all_groups_checked[0].membership_type == "direct"
    assert windows.all_groups_checked[1].membership_type == "inherited"

    assert linux.compliant is True
    assert linux.direct_groups_count == 0
    assert linux.inherited_groups_count == 1
    assert linux.all_groups_checked[0].membership_type == "inherited"

    assert mobile.compliant is False
    assert mobile.missing_groups_count == 1
    assert mobile.all_groups_checked[0].membership_type == "missing"


@pytest.mark.asyncio
async def test_list_user_groups_supports_pagination():
    service = GroupService(FakeGraphClient(), FakeUserService())

    response = await service.list_user_groups("alice@example.com", transitive=False)

    assert response.success is True
    assert response.groups_count == 1
    assert response.groups[0].id == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_list_group_members_supports_pagination_and_filters_to_users():
    service = GroupService(FakeGraphClient(), FakeUserService())

    response = await service.list_group_members("00000000-0000-0000-0000-000000000010", transitive=True)

    assert response.success is True
    assert response.members_count == 1
    assert response.members[0].user_principal_name == "carol@example.com"


@pytest.mark.asyncio
async def test_group_service_rejects_wildcards_and_invalid_ids():
    service = GroupService(FakeGraphClient(), FakeUserService())

    response = await service.list_user_groups("all")
    assert response.success is False

    with pytest.raises(ValueError):
        await service.list_group_members("everyone")

    with pytest.raises(ValueError):
        await service.list_group_members("not-a-guid")

    response = await service.check_required_groups_by_platform("*", "windows")
    assert response.success is False

    with pytest.raises(ValueError):
        await service.check_required_groups_by_platform("alice@example.com", "")
