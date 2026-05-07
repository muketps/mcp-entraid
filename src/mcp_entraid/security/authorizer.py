from __future__ import annotations


class Authorizer:
    async def authorize(self, permission: str) -> None:
        """Ponto de extensao para autorizacao corporativa futura."""
        _ = permission
        return None

    async def require_reset_mfa_permission(self) -> None:
        """Ponto de extensao para regras sensiveis de reset MFA."""
        from mcp_entraid.security.permissions import ENTRA_RESET_MFA

        await self.authorize(ENTRA_RESET_MFA)

    async def require_reset_password_permission(self, user_upn: str) -> None:
        """Ponto de extensao para regras sensiveis de reset de senha."""
        from mcp_entraid.security.permissions import ENTRA_RESET_PASSWORD

        _ = user_upn
        await self.authorize(ENTRA_RESET_PASSWORD)

    async def require_execute_runbook_permission(self, runbook_name: str) -> None:
        """Ponto de extensao para permissao de execucao de runbooks."""
        from mcp_entraid.security.permissions import AZURE_EXECUTE_RUNBOOK

        _ = runbook_name
        await self.authorize(AZURE_EXECUTE_RUNBOOK)

    async def require_group_read_permission(self) -> None:
        """Ponto de extensao para leitura de grupos."""
        from mcp_entraid.security.permissions import ENTRA_GROUP_READ

        await self.authorize(ENTRA_GROUP_READ)

    async def require_group_write_permission(self) -> None:
        """Ponto de extensao para alteracao de membros de grupos."""
        from mcp_entraid.security.permissions import ENTRA_GROUP_WRITE

        await self.authorize(ENTRA_GROUP_WRITE)

    async def require_application_read_permission(self) -> None:
        """Ponto de extensao para leitura de application registrations."""
        from mcp_entraid.security.permissions import ENTRA_APPLICATION_READ

        await self.authorize(ENTRA_APPLICATION_READ)
