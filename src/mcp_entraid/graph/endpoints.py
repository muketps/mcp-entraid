USER_SELECT_FIELDS = [
    "id",
    "displayName",
    "userPrincipalName",
    "mail",
    "jobTitle",
    "department",
    "accountEnabled",
    "officeLocation",
    "mobilePhone",
]

DIRECT_REPORT_SELECT_FIELDS = [
    "id",
    "displayName",
    "userPrincipalName",
    "mail",
    "jobTitle",
    "department",
]

GROUP_SELECT_FIELDS = [
    "id",
    "displayName",
    "mailEnabled",
    "securityEnabled",
    "groupTypes",
]

GROUP_MEMBER_SELECT_FIELDS = [
    "id",
    "displayName",
    "userPrincipalName",
    "mail",
]

APPLICATION_SELECT_FIELDS = [
    "id",
    "appId",
    "displayName",
    "createdDateTime",
    "passwordCredentials",
    "keyCredentials",
]

PHONE_METHOD_DELETE_ORDER = {
    "b6332ec1-7057-4abe-9331-3d72feddfe41": 1,
    "e37fc753-ff3b-4958-9484-eaa9425c82bc": 2,
    "3179e48a-750b-4051-897c-87b9720928f7": 3,
}
