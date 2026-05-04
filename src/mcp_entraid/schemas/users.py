from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EntraUser(BaseModel):
    user_id: str = Field(alias="id")
    user_display_name: str | None = Field(default=None, alias="displayName")
    user_principal_name: str | None = Field(default=None, alias="userPrincipalName")
    mail: str | None = None
    job_title: str | None = Field(default=None, alias="jobTitle")
    department: str | None = None
    account_enabled: bool | None = Field(default=None, alias="accountEnabled")
    office_location: str | None = Field(default=None, alias="officeLocation")
    mobile_phone: str | None = Field(default=None, alias="mobilePhone")

    model_config = ConfigDict(populate_by_name=True)

    @property
    def id(self) -> str:
        return self.user_id

    @property
    def display_name(self) -> str | None:
        return self.user_display_name
