# Internal Changelog

Internal draft for tracking changes between personal and corporate environments.

Each entry should include:
- Date
- Short summary
- Changed files
- Relevant notes

Usage rule:
- Always add a new entry when the project changes.
- Always list changed files explicitly.
- Keep entries in reverse chronological order, newest first.

## 2026-05-04 - Git ignore cleanup

Summary:
- Expanded `.gitignore` for Python, editor, cache, and OneDrive/Windows artifacts before publishing the repo.

Changed files:
- [.gitignore](.gitignore)
- [INTERNAL_CHANGELOG.md](INTERNAL_CHANGELOG.md)

Notes:
- Keeps local environment files and generated caches out of version control.

## 2026-05-04 - Runbook tools removed from public server

Summary:
- Removed Azure Automation runbook execution and output tools from the public MCP registration, keeping the implementation internal only.

Changed files:
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [README.md](README.md)
- [INTERNAL_CHANGELOG.md](INTERNAL_CHANGELOG.md)

Notes:
- Runbook support remains in the codebase, but it is no longer exposed through the public MCP server.

## 2026-05-04 - Required groups example expanded

Summary:
- Expanded the required groups example so one platform shows two group entries.

Changed files:
- [src/mcp_entraid/config/required_groups_by_platform.json](src/mcp_entraid/config/required_groups_by_platform.json)
- [INTERNAL_CHANGELOG.md](INTERNAL_CHANGELOG.md)

Notes:
- Windows now shows two required groups as a copyable example for other platforms.

## 2026-05-04 - App registration governance

Summary:
- Added read-only tools for app registration credential expiration and for finding app registrations related to a user by ownership or text match.

Changed files:
- [src/mcp_entraid/graph/endpoints.py](src/mcp_entraid/graph/endpoints.py)
- [src/mcp_entraid/security/permissions.py](src/mcp_entraid/security/permissions.py)
- [src/mcp_entraid/security/authorizer.py](src/mcp_entraid/security/authorizer.py)
- [src/mcp_entraid/audit/audit_logger.py](src/mcp_entraid/audit/audit_logger.py)
- [src/mcp_entraid/schemas/applications.py](src/mcp_entraid/schemas/applications.py)
- [src/mcp_entraid/services/application_service.py](src/mcp_entraid/services/application_service.py)
- [src/mcp_entraid/tools/applications.py](src/mcp_entraid/tools/applications.py)
- [src/mcp_entraid/dependencies.py](src/mcp_entraid/dependencies.py)
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [README.md](README.md)
- [tests/test_application_service.py](tests/test_application_service.py)
- [tests/test_applications_tools.py](tests/test_applications_tools.py)

Notes:
- No secrets are exposed.
- Ownership search uses `ownedObjects`.
- Display-name search uses the user's UPN, UPN prefix, and display name.
- Expiring credentials are ordered by the nearest expiration date.

## 2026-05-04 - Public user key migration to UPN

Summary:
- Migrated public tools to use `user_upn` as the primary key, keeping `user_id` only as the internal Entra ID identifier after Graph resolution.

Changed files:
- [src/mcp_entraid/services/user_service.py](src/mcp_entraid/services/user_service.py)
- [src/mcp_entraid/services/group_service.py](src/mcp_entraid/services/group_service.py)
- [src/mcp_entraid/workflows/reset_mfa_workflow.py](src/mcp_entraid/workflows/reset_mfa_workflow.py)
- [src/mcp_entraid/tools/users.py](src/mcp_entraid/tools/users.py)
- [src/mcp_entraid/tools/authentication_methods.py](src/mcp_entraid/tools/authentication_methods.py)
- [src/mcp_entraid/tools/groups.py](src/mcp_entraid/tools/groups.py)
- [src/mcp_entraid/schemas/users.py](src/mcp_entraid/schemas/users.py)
- [src/mcp_entraid/schemas/authentication_methods.py](src/mcp_entraid/schemas/authentication_methods.py)
- [src/mcp_entraid/schemas/groups.py](src/mcp_entraid/schemas/groups.py)
- [src/mcp_entraid/graph/client.py](src/mcp_entraid/graph/client.py)
- [src/mcp_entraid/graph/endpoints.py](src/mcp_entraid/graph/endpoints.py)
- [src/mcp_entraid/security/authorizer.py](src/mcp_entraid/security/authorizer.py)
- [src/mcp_entraid/security/permissions.py](src/mcp_entraid/security/permissions.py)
- [src/mcp_entraid/audit/audit_logger.py](src/mcp_entraid/audit/audit_logger.py)
- [src/mcp_entraid/config/required_groups_by_platform.json](src/mcp_entraid/config/required_groups_by_platform.json)
- [src/mcp_entraid/dependencies.py](src/mcp_entraid/dependencies.py)
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [README.md](README.md)
- [tests/test_entra_get_user.py](tests/test_entra_get_user.py)
- [tests/test_entra_get_direct_reports.py](tests/test_entra_get_direct_reports.py)
- [tests/test_group_service.py](tests/test_group_service.py)
- [tests/test_reset_mfa_workflow.py](tests/test_reset_mfa_workflow.py)
- [tests/test_user_service.py](tests/test_user_service.py)

Notes:
- Public tools now accept `user_upn` and reject broad values.
- Responses expose `user_id`, `user_principal_name`, and `user_display_name`.
- `user_id` remains the internal identifier used after Microsoft Graph lookup.

## 2026-05-04 - Guided MFA reset workflow

Summary:
- Added a guided, sensitive MFA reset workflow with step confirmation, in-memory state, auditing, and dedicated MCP tools.

Changed files:
- [src/mcp_entraid/graph/client.py](src/mcp_entraid/graph/client.py)
- [src/mcp_entraid/graph/errors.py](src/mcp_entraid/graph/errors.py)
- [src/mcp_entraid/graph/endpoints.py](src/mcp_entraid/graph/endpoints.py)
- [src/mcp_entraid/security/permissions.py](src/mcp_entraid/security/permissions.py)
- [src/mcp_entraid/security/authorizer.py](src/mcp_entraid/security/authorizer.py)
- [src/mcp_entraid/audit/audit_logger.py](src/mcp_entraid/audit/audit_logger.py)
- [src/mcp_entraid/schemas/authentication_methods.py](src/mcp_entraid/schemas/authentication_methods.py)
- [src/mcp_entraid/services/authentication_method_service.py](src/mcp_entraid/services/authentication_method_service.py)
- [src/mcp_entraid/workflows/__init__.py](src/mcp_entraid/workflows/__init__.py)
- [src/mcp_entraid/workflows/workflow_store.py](src/mcp_entraid/workflows/workflow_store.py)
- [src/mcp_entraid/workflows/reset_mfa_workflow.py](src/mcp_entraid/workflows/reset_mfa_workflow.py)
- [src/mcp_entraid/tools/authentication_methods.py](src/mcp_entraid/tools/authentication_methods.py)
- [src/mcp_entraid/dependencies.py](src/mcp_entraid/dependencies.py)
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [README.md](README.md)
- [tests/test_authentication_method_service.py](tests/test_authentication_method_service.py)
- [tests/test_reset_mfa_workflow.py](tests/test_reset_mfa_workflow.py)
- [INTERNAL_CHANGELOG.md](INTERNAL_CHANGELOG.md)

Notes:
- The workflow expires in 15 minutes.
- Start does not execute destructive actions.
- Deletion and sign-in session revocation require explicit confirmation.
- Phone numbers are masked in responses.

## 2026-05-04 - Azure Automation runbooks

Summary:
- Added generic support for executing allowed Azure Automation runbooks, waiting for completion, and reading job output.

Changed files:
- [src/mcp_entraid/azure/__init__.py](src/mcp_entraid/azure/__init__.py)
- [src/mcp_entraid/azure/arm_token_provider.py](src/mcp_entraid/azure/arm_token_provider.py)
- [src/mcp_entraid/azure/automation_client.py](src/mcp_entraid/azure/automation_client.py)
- [src/mcp_entraid/tools/runbooks.py](src/mcp_entraid/tools/runbooks.py)
- [src/mcp_entraid/services/runbook_service.py](src/mcp_entraid/services/runbook_service.py)
- [src/mcp_entraid/schemas/runbooks.py](src/mcp_entraid/schemas/runbooks.py)
- [src/mcp_entraid/settings.py](src/mcp_entraid/settings.py)
- [src/mcp_entraid/security/authorizer.py](src/mcp_entraid/security/authorizer.py)
- [src/mcp_entraid/security/permissions.py](src/mcp_entraid/security/permissions.py)
- [src/mcp_entraid/audit/audit_logger.py](src/mcp_entraid/audit/audit_logger.py)
- [src/mcp_entraid/dependencies.py](src/mcp_entraid/dependencies.py)
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [.env.example](.env.example)
- [README.md](README.md)

Notes:
- Execution is restricted to `AZURE_ALLOWED_RUNBOOKS`.
- Sensitive parameters are masked in audit logs.
- `timeout_seconds` is limited to 300 seconds.

## 2026-05-04 - Internal changelog helper

Summary:
- Created `INTERNAL_CHANGELOG.md` to record changes with an explicit file list.

Changed files:
- [INTERNAL_CHANGELOG.md](INTERNAL_CHANGELOG.md)

Notes:
- Kept for internal use between personal and corporate environments.

## 2026-05-04 - Base project scaffold

Summary:
- Created the `mcp-entraid` project with FastMCP, async Graph client, standardized schemas, services, and initial user tools.

Changed files:
- [fastmcp.json](fastmcp.json)
- [pyproject.toml](pyproject.toml)
- [README.md](README.md)
- [.env.example](.env.example)
- [.gitignore](.gitignore)
- [src/mcp_entraid/__init__.py](src/mcp_entraid/__init__.py)
- [src/mcp_entraid/settings.py](src/mcp_entraid/settings.py)
- [src/mcp_entraid/dependencies.py](src/mcp_entraid/dependencies.py)
- [src/mcp_entraid/server.py](src/mcp_entraid/server.py)
- [src/mcp_entraid/auth/__init__.py](src/mcp_entraid/auth/__init__.py)
- [src/mcp_entraid/auth/graph_token_provider.py](src/mcp_entraid/auth/graph_token_provider.py)
- [src/mcp_entraid/graph/__init__.py](src/mcp_entraid/graph/__init__.py)
- [src/mcp_entraid/graph/client.py](src/mcp_entraid/graph/client.py)
- [src/mcp_entraid/graph/endpoints.py](src/mcp_entraid/graph/endpoints.py)
- [src/mcp_entraid/graph/errors.py](src/mcp_entraid/graph/errors.py)
- [src/mcp_entraid/services/__init__.py](src/mcp_entraid/services/__init__.py)
- [src/mcp_entraid/services/user_service.py](src/mcp_entraid/services/user_service.py)
- [src/mcp_entraid/tools/__init__.py](src/mcp_entraid/tools/__init__.py)
- [src/mcp_entraid/tools/users.py](src/mcp_entraid/tools/users.py)
- [src/mcp_entraid/schemas/__init__.py](src/mcp_entraid/schemas/__init__.py)
- [src/mcp_entraid/schemas/common.py](src/mcp_entraid/schemas/common.py)
- [src/mcp_entraid/schemas/users.py](src/mcp_entraid/schemas/users.py)
- [src/mcp_entraid/security/__init__.py](src/mcp_entraid/security/__init__.py)
- [src/mcp_entraid/security/authorizer.py](src/mcp_entraid/security/authorizer.py)
- [src/mcp_entraid/security/permissions.py](src/mcp_entraid/security/permissions.py)
- [src/mcp_entraid/audit/__init__.py](src/mcp_entraid/audit/__init__.py)
- [src/mcp_entraid/audit/audit_logger.py](src/mcp_entraid/audit/audit_logger.py)
- [src/mcp_entraid/utils/__init__.py](src/mcp_entraid/utils/__init__.py)
- [src/mcp_entraid/utils/odata.py](src/mcp_entraid/utils/odata.py)
- [tests/test_entra_get_user.py](tests/test_entra_get_user.py)
- [tests/test_entra_get_direct_reports.py](tests/test_entra_get_direct_reports.py)
- [tests/test_user_service.py](tests/test_user_service.py)

Notes:
- Structure is designed to grow without mixing business logic into `server.py`.
- Tool responses always go through a standardized schema.
