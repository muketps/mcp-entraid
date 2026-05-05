# Cobertura de Testes

Este documento descreve a suíte automatizada atual do `mcp-entraid` e o que cada arquivo de teste já validou.

No momento, a suíte passa com `34 passed`.

## O que a suíte cobre

Os testes atuais focam em:

- consulta de usuário no Graph e normalização da resposta
- segurança do fluxo guiado de reset de MFA e ordem das etapas
- verificação de grupos obrigatórios e conformidade por plataforma
- governança de app registrations e relatórios de credenciais expirando
- comportamento interno do serviço de runbooks do Azure Automation
- comportamento de throttling do cliente Graph
- endurecimento de entradas inválidas, UPN ambíguo e parâmetros abusivos
- verificação de exposição pública de tools sensíveis

## Mapa arquivo por arquivo

### `tests/test_user_service.py`

Valida o serviço base de consulta de usuário do Entra.

O que já cobre:

- a chamada ao Microsoft Graph usa o caminho esperado `GET /users/{user_upn}`
- a consulta usa os campos esperados no `$select`
- os dados retornados pelo Graph são mapeados para o schema interno `EntraUser`
- o serviço retorna `ToolResponse` padronizado
- um `403` do Graph vira um erro de permissão limpo com `request_id`

### `tests/test_entra_get_user.py`

Valida a tool pública `entra_get_user`.

O que já cobre:

- a tool está registrada no FastMCP
- a entrada pública usa `user_upn`
- a autorização é solicitada com `ENTRA_USER_READ`
- a tool devolve os campos normalizados:
  - `user_id`
  - `user_display_name`
  - `user_principal_name`
- a resposta é estruturada, não JSON cru do Graph

### `tests/test_entra_get_direct_reports.py`

Valida a tool pública `entra_get_direct_reports`.

O que já cobre:

- a tool está registrada no FastMCP
- a entrada pública usa `user_upn`
- a autorização é solicitada com `ENTRA_DIRECT_REPORTS_READ`
- os liderados são retornados no schema padronizado
- os itens retornados preservam os campos normalizados de identidade

### `tests/test_authentication_method_service.py`

Valida o serviço de base usado pelo fluxo de reset de MFA.

O que já cobre:

- os métodos de telefone são listados na ordem esperada de remoção:
  - `alternateMobile`
  - `office`
  - `mobile`
- os números de telefone são mascarados nos resumos retornados
- um `404` ao excluir um método de autenticação vira um resultado de falha, sem quebrar o fluxo

### `tests/test_reset_mfa_workflow.py`

Valida o workflow guiado e com estado do reset de MFA.

O que já cobre:

- `start()` apenas lista os métodos e inicializa o workflow
- `start()` não deleta métodos nem revoga sessões
- a etapa `delete_authentication_methods` precisa acontecer antes de `revoke_sign_in_sessions`
- o workflow continua mesmo se uma exclusão individual falhar
- a conclusão das exclusões ainda permite avançar para revogação de sessões
- revogar sessões marca o workflow como concluído
- o status do workflow reflete o estado final após a última etapa

### `tests/test_group_service.py`

Valida o serviço de governança de grupos.

O que já cobre:

- os grupos obrigatórios são resolvidos por plataforma
- a participação é classificada como:
  - `direct`
  - `inherited`
  - `missing`
- a resposta de conformidade conta corretamente grupos diretos, herdados e ausentes
- a listagem de grupos do usuário suporta paginação
- a busca de grupos por display name retorna IDs e metadados normalizados
- a busca de grupos também aceita GUID e usa consulta direta
- filtros OData gerados para display name escapam aspas simples
- limites inválidos de resultado são rejeitados
- a listagem de membros de grupo suporta paginação
- a listagem de membros filtra apenas usuários
- curingas e identificadores inválidos são rejeitados
- plataformas inválidas são rejeitadas
- valores parecidos com listas de usuários são rejeitados pelo caminho de consulta de usuário

### `tests/test_graph_client.py`

Valida o cliente HTTP genérico do Microsoft Graph.

O que já cobre:

- um `429` vira exceção de throttling
- o cabeçalho `Retry-After` é capturado
- o `request-id` é capturado para troubleshooting

### `tests/test_application_service.py`

Valida o serviço de governança de app registrations.

O que já cobre:

- credenciais expirando são coletadas a partir das aplicações
- o resultado é ordenado pela expiração mais próxima
- credenciais expiradas e prestes a expirar aparecem no retorno
- a contagem de aplicações no retorno está correta
- a busca por app registrations por usuário suporta:
  - correspondência por owner
  - correspondência por display name
  - retorno combinado de matches
- `user_upn` com curinga é rejeitado
- desabilitar os dois critérios de busca retorna uma resposta vazia, porém bem-sucedida
- valores inválidos de `days_threshold` são rejeitados
- throttling do Graph é tratado de forma controlada

### `tests/test_applications_tools.py`

Valida as tools públicas de app registrations registradas no FastMCP.

O que já cobre:

- `entra_find_app_registrations_by_user` usa `user_upn`
- a tool retorna os dados normalizados do usuário
- o hook de permissão de leitura de aplicação é acionado
- `entra_list_expiring_app_credentials` devolve o resumo estruturado de expiração

### `tests/test_runbook_service.py`

Valida o serviço interno de runbooks do Azure Automation.

O que já cobre:

- apenas runbooks da allowlist podem ser executados
- parâmetros marcados como sensíveis são mascarados nos metadados de auditoria
- o caminho de execução não busca saída quando `wait_for_completion=False`
- um runbook fora da allowlist é bloqueado
- a leitura de saída retorna o output e os streams do job
- a leitura de streams pode ser pulada com `include_streams=False`
- saída em texto puro pode ser convertida para JSON estruturado quando fizer sentido

### `tests/test_security_regressions.py`

Valida regressões ligadas a entradas abusivas e exposição sensível.

O que já cobre:

- `UserService` rejeita:
  - `*`
  - `all`
  - `everyone`
  - `tenant`
  - listas de UPN separadas por vírgula
  - listas separadas por ponto e vírgula
  - listas separadas por espaço
  - valores em formato de lista
- `ApplicationService` rejeita valores inválidos de threshold
- `ApplicationService` trata throttling do Graph de maneira previsível
- o workflow de reset de MFA rejeita workflows expirados
- o workflow de reset de MFA rejeita replays de etapas após expiração
- o servidor público MCP não expõe as tools de runbook

## Postura de segurança já coberta pelos testes

A suíte já oferece cobertura de regressão para:

- tools públicas usando `user_upn` em vez de um `user_id` amplo
- tentativas de abuso com wildcard e operação em massa
- ordem correta das etapas no reset de MFA
- expiração do workflow de MFA e resistência a replay
- enforcement da allowlist de runbooks
- tratamento de throttling vindo do Graph
- respostas estruturadas em vez de payload cru do Graph
- remoção da exposição pública das tools de runbook

## O que a suíte ainda não cobre completamente

Os testes são fortes para comportamento unitário, mas ainda não substituem:

- integração ponta a ponta com tenant real
- enforcement de autorização com identidade ou claims de grupo reais
- execução viva de Azure Automation em conta real
- um pentest completo do hub MCP e do cliente ao redor

## Observação de manutenção

Este arquivo deve ser atualizado sempre que:

- uma nova tool pública for adicionada
- uma regra de segurança mudar
- um workflow ganhar uma nova etapa
- a suíte começar a cobrir um novo padrão de abuso
