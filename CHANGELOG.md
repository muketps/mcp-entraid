# Changelog

Todas as mudanças relevantes do projeto, em ordem cronológica reversa.

## 2026-05-05

### Usuários
- Mantidas e documentadas as tools públicas `entra_get_user` e `entra_get_direct_reports`, ambas baseadas em `user_upn`.

### README e documentação
- README refeito no estilo do exemplo de Intune, com visão geral curta, estrutura, arquitetura, catálogo de tools, configuração, permissões, limitações e testes.
- `.env.example` alinhado ao comportamento atual do projeto.

### MFA e métodos de autenticação
- `entra_reset_mfa` consolidado como façade pública.
- Fluxo de reset de MFA ajustado para exigir confirmação só uma vez e revogar sessões ao final.
- Adicionadas tools públicas de leitura:
  - `entra_list_phone_methods`
  - `entra_list_microsoft_authenticator_methods`

### Azure Automation
- Criada a tool pública `azure_unlock_user`.
- O unlock usa `TENANT_ID`, `CLIENT_ID` e `CLIENT_SECRET` do mesmo app registration do Graph.
- O nome do runbook ficou configurado em `AZURE_UNLOCK_USER_RUNBOOK_NAME`.

### Grupos
- Criada a tool pública `entra_find_groups` para buscar grupos por display name ou GUID.
- Mantidas e documentadas as tools públicas de grupo:
  - `entra_check_required_groups_by_platform`
  - `entra_list_user_groups`
  - `entra_list_group_members`

### Governança de aplicativos
- Mantidas e documentadas as tools públicas:
  - `entra_list_expiring_app_credentials`
  - `entra_find_app_registrations_by_user`

### Regras públicas
- A superfície pública do servidor foi travada por teste de regressão para evitar registro acidental de tools extras.

## 2026-05-04

### Base do projeto
- Estrutura inicial do `mcp-entraid` criada com FastMCP, Graph client, schemas, services, segurança e auditoria.

### Azure Automation e runbooks
- Suporte interno para execução de runbooks adicionado.
- Depois, o executor genérico foi retirado da superfície pública e ficou só a tool específica de unlock.

### Fluxo guiado de MFA
- Fluxo inicial de reset de MFA criado com estado interno, confirmação e auditoria.

### User-first UPN
- Tools públicas migradas para `user_upn` como identificador principal.

### Logs e execução local
- O servidor passou a rodar em HTTP local para facilitar uso com o MCP Hub.
- O README foi ajustado para `python server.py`.
