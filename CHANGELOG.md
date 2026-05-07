# Changelog

Todas as mudanças relevantes do projeto, em ordem cronológica reversa.

## 2026-05-07

### Reset de senha
- Removida a chamada à API `validatePassword` do Microsoft Graph beta — a API exige token delegado com role administrativa (Password Administrator ou superior), o que inviabiliza o uso com application permissions.
- Removido o `DelegatedGraphTokenProvider` e toda a infraestrutura de token delegado.
- O fluxo de reset agora gera a senha localmente e vai direto para o runbook de reset, sem etapa de validação remota.
- Campos removidos da resposta: `password_validated`, `password_is_valid`, `validation_attempts`, `validation_results`.

### Grupos
- Criadas as tools públicas de escrita em grupos:
  - `entra_add_user_to_group(user_upn, group_id)`
  - `entra_remove_user_from_group(user_upn, group_id)`
- As duas tools usam `user_upn` como chave pública do usuário e `group_id` apenas para o grupo alvo.
- O serviço resolve o usuário internamente via `UserService`, usa o `user_id` apenas dentro da aplicação e chama o Microsoft Graph em:
  - `POST /groups/{group_id}/members/$ref`
  - `DELETE /groups/{group_id}/members/{user_id}/$ref`
- Adicionado o schema `GroupMembershipMutationResponse` para padronizar respostas de add/remove.
- Adicionada permissão interna de escrita `ENTRA_GROUP_WRITE` e hook `Authorizer.require_group_write_permission()`.
- Documentada a necessidade de `GroupMember.ReadWrite.All` no Microsoft Graph.
- Adicionados testes cobrindo registro das tools, autorização de escrita, payload Graph de adição, endpoint Graph de remoção e regressão da lista pública de tools.

### Azure Automation
- Detalhada a configuração da tool pública `azure_unlock_user`.
- O desbloqueio continua exposto apenas pela tool específica `azure_unlock_user`; o executor genérico de runbooks permanece fora da superfície pública.
- O runbook de desbloqueio vem de `AZURE_UNLOCK_USER_RUNBOOK_NAME`.
- O runbook precisa estar permitido em `AZURE_ALLOWED_RUNBOOKS`.
- A allowlist de parâmetros do runbook é controlada por `AZURE_RUNBOOK_PARAMETER_ALLOWLIST`.
- O parâmetro enviado ao runbook de unlock é `UPN`, derivado do `user_upn` público.
- Mantido o uso das credenciais `TENANT_ID`, `CLIENT_ID` e `CLIENT_SECRET` do mesmo App Registration usado pelo Graph.
- A execução suporta `wait_for_completion` e `timeout_seconds`, retornando dados do job e output quando disponível.

## 2026-05-06

### Reset de senha
- Criado o fluxo guiado de reset de senha (`entra_reset_user_password`) com confirmação explícita antes de executar.
- Geração de senha temporária local com critérios de complexidade (maiúscula, minúscula, número, símbolo, sem padrões fracos).
- Integração com runbook de reset via Azure Automation.
- Configurações adicionadas: `PASSWORD_RESET_RUNBOOK_NAME`, `PASSWORD_RESET_RUNBOOK_USER_PARAM`, `PASSWORD_RESET_RUNBOOK_PASSWORD_PARAM`, `PASSWORD_RESET_RETURN_TEMPORARY_PASSWORD`, `PASSWORD_RESET_WORKFLOW_EXPIRATION_MINUTES`.

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
- Adicionadas as configurações `AZURE_ALLOWED_RUNBOOKS` e `AZURE_RUNBOOK_PARAMETER_ALLOWLIST` para travar runbooks e parâmetros permitidos.
- O parâmetro público da tool é `user_upn`; internamente ele é enviado ao runbook como `UPN`.

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
