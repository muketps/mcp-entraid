# mcp-entraid

MCP corporativo para Microsoft Entra ID usando FastMCP, Microsoft Graph e autenticação via client credentials.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Configuração

Crie um arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Configure:

```env
TENANT_ID=00000000-0000-0000-0000-000000000000
CLIENT_ID=00000000-0000-0000-0000-000000000000
CLIENT_SECRET=your-client-secret
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
GRAPH_SCOPE=https://graph.microsoft.com/.default
```

## Rodando localmente

Com o ambiente virtual ativado e o `.env` configurado:

```powershell
python server.py
```

O servidor sobe em:

```text
http://127.0.0.1:8000
```

## Permissões Microsoft Graph

A aplicação registrada no Microsoft Entra ID precisa da permissão de aplicação:

- `User.Read.All`
- `UserAuthenticationMethod.ReadWrite.All`
- `User.RevokeSessions.All`

Depois de adicionar a permissão, conceda admin consent no tenant.

## Azure Automation

Para execução interna de runbooks via Azure Automation Account, configure:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP_NAME`
- `AZURE_AUTOMATION_ACCOUNT_NAME`
- `AZURE_AUTOMATION_API_VERSION` com padrão `2024-10-23`
- `AZURE_AUTOMATION_RUN_ON` se você usar Hybrid Runbook Worker
- `AZURE_ALLOWED_RUNBOOKS` com a lista de runbooks permitidos

Opcionalmente, você pode definir `AZURE_RUNBOOK_PARAMETER_ALLOWLIST` como JSON para restringir parâmetros por runbook.

## Arquitetura

O fluxo principal é:

```text
tools -> services -> graph client -> Microsoft Graph
```

- `src/mcp_entraid/server.py` cria a instância `FastMCP` e registra as tools.
- `src/mcp_entraid/tools/` expõe as tools MCP.
- `src/mcp_entraid/services/` concentra regras de negócio e padronização de resposta.
- `src/mcp_entraid/graph/client.py` faz chamadas HTTP assíncronas genéricas para o Microsoft Graph.
- `src/mcp_entraid/auth/graph_token_provider.py` obtém e mantém cache do token via client credentials.
- `src/mcp_entraid/schemas/` define modelos Pydantic para evitar retorno de JSON bruto do Graph.
- `src/mcp_entraid/security/authorizer.py` está preparado para futuras regras de autorização.
- `src/mcp_entraid/audit/audit_logger.py` centraliza eventos de auditoria sem vazar segredos.

## Tools

### Usuário

- `entra_get_user(user_upn: str)`
- `entra_get_direct_reports(user_upn: str)`

### Reset MFA guiado

- `entra_reset_user_mfa_start(user_upn: str)`
- `entra_reset_user_mfa_execute_step(reset_request_id: str, step: str, confirmed: bool)`
- `entra_reset_user_mfa_status(reset_request_id: str)`

### Grupos

- `entra_find_groups(query: str, exact_match: bool = True, max_results: int = 10)`
- `entra_check_required_groups_by_platform(user_upn: str, platform: str)`
- `entra_list_user_groups(user_upn: str, transitive: bool = True)`
- `entra_list_group_members(group_id: str, transitive: bool = True)`

### Governança de app registrations

- `entra_list_expiring_app_credentials(days_threshold: int = 30, include_expired: bool = True, include_certificates: bool = True, include_secrets: bool = True)`
- `entra_find_app_registrations_by_user(user_upn: str, search_display_name: bool = True, search_owned_apps: bool = True)`

### Runbooks do Azure Automation

As rotinas de runbook existem no projeto como implementação interna, mas não ficam expostas como tools públicas no servidor MCP.

## Observações

- Todas as tools públicas usam `user_upn` como chave principal para usuários.
- Os retornos públicos usam `user_upn` e `user_display_name` quando aplicável; GUIDs do Entra ficam restritos ao uso interno quando necessários.
- O servidor local roda em `http://127.0.0.1:8000`.
