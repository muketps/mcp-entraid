# mcp-entraid

Servidor MCP para operações corporativas no Microsoft Entra ID, com Microsoft Graph e Azure Automation. O foco aqui é suporte, governança e tarefas sensíveis com controle explícito de confirmação.

## Estrutura de Pastas

```text
mcp-entraid/
├── src/
│   └── mcp_entraid/          # Pacote principal
│       ├── azure/            # Integração com Azure Automation
│       ├── auth/             # Token provider do Microsoft Graph
│       ├── graph/            # Cliente HTTP para Microsoft Graph
│       ├── schemas/          # Modelos Pydantic de entrada e saída
│       ├── security/         # Autorização e regras de acesso
│       ├── services/         # Lógica de negócio
│       ├── tools/            # Tools MCP públicas
│       ├── workflows/        # Fluxos guiados, como reset de MFA
│       └── server.py         # Registro do servidor MCP
├── tests/                    # Testes unitários e de regressão
├── .env.example              # Exemplo de configuração local
├── README.md                 # Este arquivo
├── pyproject.toml            # Dependências e metadados
└── server.py                 # Wrapper para executar localmente
```

## Arquitetura

O projeto segue uma estrutura em camadas para manter o código simples de operar e fácil de auditar:

1. **Ponto de entrada (`server.py`)**
   Inicializa o `FastMCP` e registra apenas as tools públicas.

2. **Camada de tools (`tools/`)**
   Expõe as ações que o Hub pode chamar. Aqui ficam as interfaces públicas por `user_upn` ou por identificadores explícitos, como `group_id` quando o alvo não é um usuário.

3. **Camada de serviços (`services/`)**
   Concentra validação, regras de negócio e composição das chamadas ao Graph ou ao Azure Automation.

4. **Camada de integração (`graph/`, `azure/`, `auth/`)**
   Faz a comunicação HTTP com Microsoft Graph, Azure Resource Manager e Azure Automation.

5. **Fluxos guiados (`workflows/`)**
   Implementa operações com mais de uma etapa, como o reset de MFA, com estado interno e confirmação explícita.

6. **Segurança e auditoria (`security/`, `audit/`)**
   Centraliza as regras de autorização e os eventos de auditoria.

## Referência de Tools

Total atual: **12 tools públicas**.

### Usuários

- `entra_get_user(user_upn: str)`: retorna dados básicos do usuário.
- `entra_get_direct_reports(user_upn: str)`: lista os reportes diretos.

### MFA

- `entra_list_phone_methods(user_upn: str)`: lista os métodos de telefone cadastrados.
- `entra_list_microsoft_authenticator_methods(user_upn: str)`: lista os métodos Microsoft Authenticator.
- `entra_reset_mfa(action: "start" | "confirm" | "status", user_upn: str | None = None, reset_request_id: str | None = None)`: fluxo guiado para remover métodos de autenticação e revogar sessões.

### Grupos

- `entra_find_groups(query: str, exact_match: bool = True, max_results: int = 10)`: busca grupos por display name ou GUID.
- `entra_check_required_groups_by_platform(user_upn: str, platform: str)`: verifica grupos obrigatórios por plataforma.
- `entra_list_user_groups(user_upn: str, transitive: bool = True)`: lista grupos do usuário.
- `entra_list_group_members(group_id: str, transitive: bool = True)`: lista membros de um grupo.

### Governança de aplicativos

- `entra_list_expiring_app_credentials(days_threshold: int = 30, include_expired: bool = True, include_certificates: bool = True, include_secrets: bool = True)`: lista credenciais próximas do vencimento.
- `entra_find_app_registrations_by_user(user_upn: str, search_display_name: bool = True, search_owned_apps: bool = True)`: encontra app registrations ligados ao usuário.

### Azure Automation

- `azure_unlock_user(user_upn: str, wait_for_completion: bool = True, timeout_seconds: int = 60)`: executa o runbook de desbloqueio de usuário.

## Configuração

Crie um arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Configuração principal:

```env
TENANT_ID=00000000-0000-0000-0000-000000000000
CLIENT_ID=00000000-0000-0000-0000-000000000000
CLIENT_SECRET=your-client-secret
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
GRAPH_SCOPE=https://graph.microsoft.com/.default
AZURE_SUBSCRIPTION_ID=00000000-0000-0000-0000-000000000000
AZURE_RESOURCE_GROUP_NAME=rg-automation
AZURE_AUTOMATION_ACCOUNT_NAME=automation-account
AZURE_UNLOCK_USER_RUNBOOK_NAME=Unlock-User
AZURE_AUTOMATION_API_VERSION=2024-10-23
AZURE_AUTOMATION_RUN_ON=
AZURE_ALLOWED_RUNBOOKS=Unlock-User
AZURE_RUNBOOK_PARAMETER_ALLOWLIST={"unlock-user":["UPN"]}
```

## Azure Automation

Para o `azure_unlock_user`, o projeto usa o mesmo App Registration do Microsoft Graph. Ou seja, `TENANT_ID`, `CLIENT_ID` e `CLIENT_SECRET` servem para Graph e Azure Automation.

O nome do runbook fica em `AZURE_UNLOCK_USER_RUNBOOK_NAME`. Isso é configuração de ambiente, não parâmetro público da tool.

Se você usar Hybrid Runbook Worker, preencha `AZURE_AUTOMATION_RUN_ON`.

## Permissões

### Microsoft Graph

Permissões de aplicação esperadas:

- `User.Read.All`
- `UserAuthenticationMethod.ReadWrite.All`
- `User.RevokeSessions.All`
- `Group.Read.All`
- `Application.Read.All`

### Azure

O App Registration também precisa de acesso no Azure, normalmente via RBAC no Resource Group ou na própria Automation Account.

## Fluxo de MFA

O reset de MFA é intencionalmente guiado:

1. `entra_reset_mfa(action="start", user_upn="...")` consulta os métodos cadastrados.
2. A tool mostra quais métodos de telefone e Microsoft Authenticator existem.
3. `entra_reset_mfa(action="confirm", user_upn="...")` executa a remoção.
4. As sessões são revogadas ao final do fluxo.

Mensagem padrão de conclusão:

```text
Pronto! O MFA foi removido com sucesso. Nos próximos minutos, suas aplicações Microsoft pedirão que você cadastre novamente a autenticação multifator. Siga as orientações exibidas na tela para concluir o processo.
```

## Limitações Conhecidas

- O reset de MFA é uma operação sensível e continua em etapas.
- O desbloqueio do usuário depende da configuração do runbook no Azure Automation.
- O servidor usa `user_upn` como chave principal nas tools públicas voltadas a usuário.
- GUIDs do Entra ficam internos quando o fluxo precisa resolver o usuário no Graph.

## Executando Localmente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python server.py
```

Endpoint local:

```text
http://127.0.0.1:8000
```

## Testes

```powershell
pytest
```

Última suíte validada:

```text
42 passed
```
