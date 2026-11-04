# SIG QuIIN — Portal de Gestão e Prestação de Contas

**Descrição:** Aplicação Django para gestão e prestação de contas mensal do Programa QuIIN.

**Produção:** Render + Gunicorn + PostgreSQL + Cloudflare R2.

> Este documento usa português técnico simplificado. A estrutura segue os princípios do ASD-STE100: frases curtas, voz ativa, um comando por passo e termos consistentes.
>
> O `docs/sdd.md` registra o escopo original do protótipo local (SQLite, sem cloud). A versão de produção usa PostgreSQL, Render e Cloudflare R2. Este README descreve o estado atual. Consulte `docs/` para o histórico e as regras detalhadas.

## 1. Visão geral

O SIG QuIIN apoia o ciclo mensal de prestação de contas do Programa QuIIN. A aplicação oferece:

- Login local e permissões por perfil e pilar.
- Cadastro de pilares, indicadores, metas e períodos.
- Lançamentos com fluxo de rascunho, envio, aprovação e devolução.
- Dashboards geral, por pilar, mensal, semestral e anual.
- Importação financeira e conciliação de resultados.
- Relatório mensal imprimível.
- Auditoria das ações relevantes.
- Gestão da Associação Tecnológica, associados, solicitações e benefícios.
- Banco de Talentos e organograma.
- Entregáveis, produtos, materiais e biblioteca.
- Plano anual e painel plurianual.

### 1.1 Arquitetura

```text
Navegador
   |
   v
Render (HTTPS) -> Gunicorn -> Django
                               |-> PostgreSQL   (DATABASE_URL)
                               |-> Cloudflare R2 (mídia, API S3)
                               |-> WhiteNoise    (arquivos estáticos)
```

O projeto não usa Docker, PM2, Nginx, Redis, Celery ou filas. O processo web é o Gunicorn. O WhiteNoise serve os estáticos dentro do processo Django.

### 1.2 Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.13.7 no Render; Python 3.11 ou superior no desenvolvimento |
| Framework | Django 5.2.17 |
| Banco | PostgreSQL em produção; SQLite no desenvolvimento local |
| Servidor | Gunicorn 23.0.0 |
| Arquivos estáticos | WhiteNoise + `collectstatic` |
| Mídia | Cloudflare R2 com `django-storages` e API S3 |
| Front-end | Django Templates, Tailwind CSS v4, HTMX, Alpine.js e Chart.js |
| Deploy | Render, `build.sh` e `render.yaml` |
| Testes | Django TestCase; Playwright opcional para E2E |

### 1.3 Rotas principais

| Rota | Função |
|---|---|
| `/` | Visão geral e painel anual. |
| `/accounts/login/` | Login. |
| `/operacao/` | Início da operação de lançamentos. |
| `/operacao/base/` | Confirmação da base inicial. |
| `/lancamentos/<periodo_pk>/<pilar_pk>/` | Formulário de lançamento por período e pilar. |
| `/aprovacao/<periodo_pk>/` | Aprovação e devolução de propostas. |
| `/prestacao/mensal/` | Prestação mensal. |
| `/prestacao/semestral/` | Prestação semestral. |
| `/financeiro/` | Financeiro consolidado. |
| `/financeiro/importar/` | Importação CSV do financeiro. |
| `/financeiro/prestacao/importar/` | Importação REFAT em Excel. |
| `/plano-anual/dashboard.html` | Exportação HTML do painel anual. |
| `/plano-anual/dados.csv` | Exportação CSV do painel anual. |
| `/relatorio/mensal/<periodo_pk>/` | Relatório mensal imprimível. |
| `/gestao-at/associados/` | Associados e planos da AT. |
| `/gestao-at/solicitacoes/` | Solicitações da AT. |
| `/talentos/organograma/` | Banco de Talentos. |
| `/projetos/pilar/<pilar_pk>/gerenciar/` | Projetos e materiais. |
| `/entregaveis-at/gerenciar/` | Produtos e materiais da AT. |
| `/materiais/` | Biblioteca de materiais. |
| `/auditoria/` | Trilha de auditoria. |
| `/admin/` | Administração Django. |
| `/health/` | Rota de saúde. |

As rotas internas exigem autenticação. O acesso também depende do perfil e do pilar. Rotas de módulos em evolução podem exibir aviso de construção. Consulte o menu da aplicação e `docs/`.

### 1.4 Siglas

| Sigla | Significado |
|---|---|
| SIG | Sistema de Informações Gerenciais. |
| QuIIN | Quantum Industrial Innovation. |
| AT | Associação Tecnológica. |
| SDD | Software Design Document (documento de projeto de software). |
| RF | Requisito funcional. |
| RNF | Requisito não funcional. |
| RN | Regra de negócio. |
| E2E | Teste de ponta a ponta. |
| S3 | Protocolo de armazenamento de objetos. |
| R2 | Serviço de armazenamento de objetos da Cloudflare. |
| CSRF | Proteção contra requisições forjadas. |
| CORS | Compartilhamento de recursos entre origens. |
| SMTP | Protocolo de envio de e-mail. |
| TLS | Protocolo de segurança de transporte. |
| WSGI | Interface entre o servidor web e a aplicação Python. |
| CI | Integração contínua. |

## 2. Estrutura do projeto

```text
config/                 Configuração Django, URLs, WSGI e ASGI
apps/                   Aplicações por domínio
templates/              Templates globais e componentes
static/                 CSS, JavaScript, imagens e fontes
staticfiles/            Saída do collectstatic (gerada; não versionada)
media/                  Mídia local de desenvolvimento (não versionada)
docs/                   SDD, requisitos, manuais e decisões
scripts/                Utilitários de desenvolvimento e evidências
build.sh                Build do Render
render.yaml             Blueprint de referência do Render
requirements.txt        Dependências de produção
requirements-dev.txt    Ferramentas de desenvolvimento
.env.example            Modelo de variáveis de ambiente
```

### 2.1 Aplicações Django

| App | Responsabilidade |
|---|---|
| `accounts` | Login, cadastro, recuperação de senha e usuário customizado. |
| `core` | Dashboards, navegação, permissões, busca e rota de saúde. |
| `pillars` | Pilares e vínculos entre usuários e pilares. |
| `indicators` | Indicadores, metas e unidades. |
| `periods` | Períodos, fechamento, reabertura e snapshot. |
| `entries` | Lançamentos, propostas, aprovação e base operacional. |
| `finance` | Importação CSV do financeiro consolidado. |
| `accountability` | Prestação de contas e importação REFAT em Excel. |
| `planning` | Plano anual, painel plurianual e exportações. |
| `projects` | Projetos, entregáveis, materiais, produtos AT e biblioteca. |
| `reports` | Relatório mensal e apresentação. |
| `audit` | Trilha de auditoria e exportação CSV. |
| `highlights` | Destaques mensais. |
| `crm_at` | Funil e oportunidades da Associação Tecnológica. |
| `talentos` | Banco de Talentos, fotos, competências e alocações. |
| `gestao_at` | Associados, planos, benefícios e solicitações da AT. |
| `seed` | Dados de demonstração para o ambiente local. |

## 3. Regras de negócio essenciais

Leia `docs/sdd.md` e `docs/decisoes.md` antes de alterar regras.

- A competência é o primeiro dia do mês. Exemplo: `2026-06-01` representa `2026-06`.
- Apenas lançamentos **aprovados** alimentam os dashboards.
- O período fechado bloqueia edição. A reabertura exige justificativa.
- O fechamento grava um snapshot lógico do período.
- O backend valida as permissões por perfil e por pilar.
- A importação financeira usa uma transação atômica. Uma linha inválida rejeita o arquivo inteiro.
- Toda alteração relevante gera auditoria.
- Captação não é execução financeira.
- Renovações não contam para a meta de CNPJs novos.
- O plano anual é um snapshot. Ele não é derivado automaticamente do operacional.
- Os lançamentos operacionais usam valores acumulados desde o início do ciclo. Não some o acumulado mês a mês.
- O seed e os exemplos usam dados fictícios. Trate dados de produção conforme a política da organização.

## 4. Requisitos do ambiente

### 4.1 Desenvolvimento

- Python 3.11 ou superior.
- Git.
- Node.js apenas para testes E2E com Playwright.
- Acesso ao banco local SQLite ou a um PostgreSQL de teste.

### 4.2 Produção

- Conta no Render.
- PostgreSQL gerenciado (Render Postgres, Neon ou equivalente).
- Bucket privado no Cloudflare R2.
- Token R2 com permissão **Object Read & Write** limitada ao bucket.
- Domínio ou URL do Render com HTTPS.

## 5. Variáveis de ambiente

A aplicação lê variáveis de ambiente em `config/settings.py`. No desenvolvimento, o arquivo `.env` é carregado por `python-dotenv`. No Render, configure as variáveis no painel **Environment**.

> Não grave segredos no repositório. O arquivo `.env` está no `.gitignore`.

### 5.1 Variáveis da aplicação

| Variável | Obrigatória em produção | Exemplo fictício | Função |
|---|---|---|---|
| `SECRET_KEY` | Sim | `troque-por-uma-chave-aleatoria-longa` | Assina sessões, CSRF e tokens. |
| `DEBUG` | Sim | `False` | Desativa o modo de depuração. |
| `DATABASE_URL` | Sim | `postgresql://quiin:senha@db.exemplo.com:5432/quiin` | Conexão com o PostgreSQL. |
| `ALLOWED_HOSTS` | Não | `app.exemplo.com,www.exemplo.com` | Hosts HTTP adicionais. O host do Render entra automaticamente. |
| `CSRF_TRUSTED_ORIGINS` | Não | `https://app.exemplo.com` | Origens confiáveis para CSRF. O host do Render entra automaticamente. |
| `RENDER_EXTERNAL_HOSTNAME` | Automática | `app.onrender.com` | Injetada pelo Render. Não defina manualmente. |
| `AWS_STORAGE_BUCKET_NAME` | Sim, se usar R2 | `quiin-media` | Nome do bucket de mídia. |
| `AWS_S3_ENDPOINT_URL` | Sim, se usar R2 | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | Endpoint S3 do R2. |
| `AWS_ACCESS_KEY_ID` | Sim, se usar R2 | `access-key-de-exemplo` | Access Key do token R2. |
| `AWS_SECRET_ACCESS_KEY` | Sim, se usar R2 | `secret-key-de-exemplo` | Secret do token R2. |
| `AWS_S3_REGION_NAME` | Não | `auto` | Região S3 do R2. |
| `AWS_QUERYSTRING_AUTH` | Não | `True` | Gera URLs assinadas para bucket privado. |
| `AWS_QUERYSTRING_EXPIRE` | Não | `3600` | Validade da URL assinada, em segundos. |
| `EMAIL_BACKEND` | Não | `django.core.mail.backends.smtp.EmailBackend` | Backend de envio de e-mail. |
| `DEFAULT_FROM_EMAIL` | Não | `SIG QuIIN <nao-responda@exemplo.com>` | Remetente dos e-mails. |
| `EMAIL_HOST` | Não | `smtp.exemplo.com` | Servidor SMTP. |
| `EMAIL_PORT` | Não | `587` | Porta SMTP. |
| `EMAIL_HOST_USER` | Não | `usuario-smtp` | Usuário SMTP. |
| `EMAIL_HOST_PASSWORD` | Não | `senha-de-exemplo` | Senha SMTP. |
| `EMAIL_USE_TLS` | Não | `True` | Ativa STARTTLS. |
| `EMAIL_USE_SSL` | Não | `False` | Ativa SSL direto. |

Notas:

- `SECRET_KEY` não pode usar o valor padrão do código em produção.
- `DEBUG` deve ser `False` em produção.
- `DATABASE_URL` ausente faz o Django usar `db.sqlite3` local.
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` são opcionais quando o Render fornece `RENDER_EXTERNAL_HOSTNAME`. Use-as para domínio próprio.
- `EMAIL_USE_TLS` e `EMAIL_USE_SSL` não devem ser `True` ao mesmo tempo.
- Use `True` ou `False` com maiúscula inicial em `DEBUG`, `EMAIL_USE_TLS` e `EMAIL_USE_SSL`. O código compara a string exata.
- O backend de console imprime os e-mails no log. Não use esse backend em produção.

### 5.2 Variáveis do Render

| Variável | Exemplo | Função |
|---|---|---|
| `PYTHON_VERSION` | `3.13.7` | Versão do Python no build. |
| `PORT` | `10000` | Porta injetada pelo Render. O Gunicorn usa `$PORT`. |
| `WEB_CONCURRENCY` | `2` | Presente no blueprint. O comando atual fixa `--workers 2`. |

### 5.3 Exemplo de `.env` para produção

```dotenv
# Django
SECRET_KEY=troque-por-uma-chave-aleatoria-longa
DEBUG=False
DATABASE_URL=postgresql://quiin:senha@db.exemplo.com:5432/quiin
ALLOWED_HOSTS=app.exemplo.com
CSRF_TRUSTED_ORIGINS=https://app.exemplo.com

# Cloudflare R2
AWS_STORAGE_BUCKET_NAME=quiin-media
AWS_S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=access-key-de-exemplo
AWS_SECRET_ACCESS_KEY=secret-key-de-exemplo
AWS_S3_REGION_NAME=auto
AWS_QUERYSTRING_AUTH=True
AWS_QUERYSTRING_EXPIRE=3600

# E-mail
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=SIG QuIIN <nao-responda@exemplo.com>
EMAIL_HOST=smtp.exemplo.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario-smtp
EMAIL_HOST_PASSWORD=senha-de-exemplo
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
```

Gere a `SECRET_KEY` com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 5.4 Cloudflare R2

1. Crie um bucket privado. Exemplo: `quiin-media`.
2. No dashboard do R2, abra **Manage API Tokens**.
3. Crie um **Account API token**.
4. Use a permissão **Object Read & Write**.
5. Limite o token ao bucket.
6. Copie o **Access Key ID** e o **Secret Access Key**.
7. Configure as variáveis `AWS_*` no Render.

O bucket deve continuar privado. As imagens usam URLs assinadas com validade de `AWS_QUERYSTRING_EXPIRE` segundos.

Se as variáveis de R2 não estiverem definidas, o Django usa o disco local (`MEDIA_ROOT`). No Render, esse disco é efêmero. A mídia desaparece em redeploy, restart ou spin-down. Use R2 em produção.

## 6. Executar localmente

### 6.1 Preparar o ambiente

```bash
git clone <URL_DO_REPOSITORIO>
cd prototipo-prest-contas
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie o `.env` local:

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Edite o `.env` apenas com os valores locais. O `.env.example` já vem com o bloco de R2 comentado. Para usar SQLite e disco local, não defina `DATABASE_URL` nem `AWS_STORAGE_BUCKET_NAME`.

### 6.2 Preparar o banco e os dados demo

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py tailwind build --force
python manage.py runserver
```

Acesse: `http://127.0.0.1:8000/`.

Notas:

- `seed_demo` é idempotente. Ele cria dados de demonstração.
- Os usuários e as senhas demo estão em `docs/como-rodar.md`.
- **Não execute `seed_demo` em produção.** Ele atualiza registros que já podem ter sido editados.
- `tailwind build` gera `static/css/tailwind.css`. O arquivo é versionado. Execute o comando após alterar templates ou CSS.
- No Windows, se o CLI do Tailwind falhar com emojis, defina `PYTHONUTF8=1`.

### 6.3 Parar o servidor

Pressione `Ctrl+C` no terminal do `runserver`.

## 7. Qualidade e testes

### 7.1 Testes Django

O projeto usa o manifest do WhiteNoise. Execute `collectstatic` antes dos testes:

```bash
python manage.py collectstatic --no-input --clear
python manage.py test
```

Testes por app:

```bash
python manage.py test apps.talentos
python manage.py test apps.projects
python manage.py test apps.entries.tests_operational
```

Verificações de configuração:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py auditar_dashboards
```

`auditar_dashboards` é somente leitura. Ele retorna código 1 quando uma invariante falha.

> Alguns testes legados de telas desativadas ainda podem falhar por fixtures duplicadas. Registre o resultado no deploy. Use os testes por app e `auditar_dashboards` como verificação complementar.

### 7.2 Testes E2E com Playwright

Node.js é necessário apenas para os testes E2E.

```bash
npm ci
npx playwright install chromium
python manage.py migrate
python manage.py seed_demo
python manage.py tailwind build
python manage.py runserver
npx playwright test
```

Alguns cenários E2E usam `QUIIN_MATERIAL_LIBRARY_E2E=1` e `QUIIN_OPERATION_E2E=1` para criar bancos temporários. Não use essas variáveis em produção.

O workflow `.github/workflows/playwright.yml` executa o Playwright em push e pull request para `main` ou `master`. Ele não executa a suíte Django.

## 8. Deploy em produção

O deploy de referência usa o Render. O arquivo `render.yaml` define um serviço web com build, start e health check. Se o serviço foi criado manualmente, use os mesmos comandos.

### 8.1 Antes do deploy

1. Atualize o repositório local.

```bash
git pull
```

2. Verifique a configuração.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

3. Gere os estáticos e o CSS.

```bash
python manage.py tailwind build --force
python manage.py collectstatic --no-input --clear
```

4. Execute os testes.

```bash
python manage.py test
```

5. Revise as alterações.

```bash
git status
git diff
```

6. Faça commit e push.

```bash
git add <ARQUIVOS_REVISADOS>
git commit -m "preparar deploy de producao"
git push
```

Não use `git add .` sem revisar os arquivos não rastreados. Não faça commit de `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `node_modules/` ou relatórios de teste.

### 8.2 Configurar o Render

#### Opção A — Blueprint

1. Conecte o repositório ao Render.
2. Use o `render.yaml` como blueprint.
3. Ajuste o nome do serviço, se necessário. O blueprint usa `quiin-mockup`.
4. Preencha as variáveis de ambiente.
5. Aplique o blueprint.

O blueprint define:

```yaml
buildCommand: "bash build.sh"
startCommand: "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2"
healthCheckPath: /health/
```

O blueprint de referência usa `plan: free`. Para produção contínua, avalie um plano pago. O plano free hiberna e não oferece shell.

#### Opção B — Serviço manual

1. Crie um **Web Service** com runtime Python.
2. Defina o build command:

```bash
bash build.sh
```

3. Defina o start command:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
```

4. Defina o health check path:

```text
/health/
```

5. Adicione as variáveis de ambiente da seção 5.
6. Faça o deploy.

### 8.3 O que o build executa

O arquivo `build.sh` executa:

```bash
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

O build **não** executa `seed_demo`, `tailwind build` nem `createsuperuser`.

- `seed_demo` é proibido em produção.
- O CSS do Tailwind deve estar compilado e versionado antes do deploy.
- As migrações são aplicadas no build.

### 8.4 Criar o primeiro administrador

Crie um superusuário com acesso ao banco de produção:

```bash
python manage.py createsuperuser
```

O comando pede usuário, e-mail e senha. O campo `nome` é opcional.

O superusuário acessa `/admin/`. Para usar as permissões da aplicação, adicione o usuário ao grupo `Master`:

```bash
python manage.py shell -c "from apps.accounts.models import User; from apps.core.permissions import adicionar_grupo; adicionar_grupo(User.objects.get(username='SEU_USUARIO'), 'Master')"
```

Também é possível criar o grupo e o vínculo pelo `/admin/`.

Notas:

- No plano free do Render, não há shell. Execute o comando em uma máquina local com `DATABASE_URL` de produção ou use um plano pago.
- Não use os usuários demo em produção.
- Não use as senhas demo em produção.

### 8.5 Pós-deploy

1. Teste a rota de saúde.

```bash
curl -i https://<HOST>/health/
```

Resultado esperado: status `200` e corpo `ok`.

```text
content-type: text/plain

ok
```

2. Teste a tela de login.

```bash
curl -I https://<HOST>/accounts/login/
```

Resultado esperado: status `200`.

3. Faça login com o usuário Master.

4. Abra **Operação → Lançamentos** e confirme a base inicial. Informe a competência de corte e a primeira competência de lançamento. Sem essa confirmação, os dashboards usam apenas os dados importados e os pontos focais não podem propor resultados.

5. Abra **Talentos → Organograma** e envie uma foto. Verifique se a imagem abre. A URL deve apontar para o host do R2 e conter `X-Amz-Signature`.

6. Verifique os dashboards, o relatório mensal e a auditoria.

7. Se houver shell, execute a auditoria de números:

```bash
python manage.py auditar_dashboards
```

8. Verifique os logs do Render. Procure erros de migração, de conexão com o banco, de R2 e de estáticos.

### 8.6 Comandos de inicialização opcionais

Execute apenas quando o cenário se aplicar. Revise o efeito de cada comando antes de executar.

```bash
python manage.py sincronizar_produtos_at
python manage.py sincronizar_catalogo_projetos
python manage.py seed_prototipo_at
python manage.py auditar_dashboards
```

- `sincronizar_produtos_at`: completa o catálogo inicial de produtos da AT em centros existentes. Preserva nomes, ordem e situação.
- `sincronizar_catalogo_projetos`: preenche vínculos ausentes entre snapshots financeiros e o catálogo de projetos. Não altera valores.
- `seed_prototipo_at`: complementa os dados de AT. Preserva edições. Use somente se a migração não tiver carregado os dados esperados.
- `auditar_dashboards`: valida as invariantes dos dashboards. Não grava dados.

Não execute:

- `seed_demo` em produção.
- `flush` em produção.
- `limpar_lancamentos_legados` sem backup e sem revisão.
- Reversão de migração sem backup.

### 8.7 Rollback

1. Use o histórico de deploys do Render para voltar ao deploy anterior.
2. Se o problema estiver no código, faça `git revert` e novo push.
3. As migrações recentes são aditivas. Confirme a migração específica antes de reverter. Não reverta uma migração em produção sem backup e sem plano de restauração.
4. Verifique `/health/`, o login e os dashboards após o rollback.

## 9. Rotas de saúde e smoke tests

### 9.1 Rota de saúde

| Item | Valor |
|---|---|
| Rota | `/health/` |
| Método | `GET` |
| Resposta | `200 OK` |
| Corpo | `ok` |
| Autenticação | Não |
| Banco de dados | Não consulta |
| R2 | Não consulta |

A rota confirma apenas que o processo web responde. Ela não confirma o banco, o R2, as migrações ou os dashboards.

### 9.2 Smoke tests mínimos

```bash
curl -i https://<HOST>/health/
curl -I https://<HOST>/accounts/login/
curl -I https://<HOST>/
```

Resultados esperados:

- `/health/`: `200` com corpo `ok`.
- `/accounts/login/`: `200`.
- `/`: `302` para o login quando o usuário não está autenticado.

### 9.3 Verificar banco e migrações

```bash
python manage.py migrate --check
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('db ok')"
```

`migrate --check` retorna código 1 quando há migrações pendentes.

### 9.4 Verificar R2

Envie uma foto em **Talentos → Organograma**. Abra a imagem no navegador. A URL deve:

- apontar para `<ACCOUNT_ID>.r2.cloudflarestorage.com`;
- conter o caminho do bucket;
- conter `X-Amz-Signature` na query string;
- expirar após `AWS_QUERYSTRING_EXPIRE` segundos.

## 10. Operação e manutenção

### 10.1 Logs

Use o painel do Render para ver os logs do serviço. Verifique:

- erros de `gunicorn`;
- erros de migração;
- erros de conexão com o PostgreSQL;
- erros de acesso ao R2;
- avisos de arquivos estáticos ausentes.

### 10.2 Migrações

- O build executa `python manage.py migrate`.
- Antes de uma migração de risco, faça backup do banco.
- Verifique migrações pendentes com `python manage.py migrate --check`.
- Não edite migrações já aplicadas em produção.

### 10.3 Arquivos estáticos

- O build executa `python manage.py collectstatic --no-input`.
- O WhiteNoise serve os arquivos de `STATIC_ROOT`.
- `WHITENOISE_MANIFEST_STRICT = False` evita que um asset ausente derrube o deploy. Verifique os avisos no log.
- Após alterar templates ou CSS, execute `python manage.py tailwind build --force` e faça commit de `static/css/tailwind.css`.
- O build do Tailwind usa o CLI standalone. Node.js não é necessário em runtime.
- HTMX, Alpine.js e Chart.js são vendorizados em `static/`. A aplicação não depende de CDN.

### 10.4 Mídia

- Em produção, use o Cloudflare R2.
- O bucket é privado. As URLs são assinadas.
- Não habilite acesso público sem revisar a política de dados.
- Fotos antigas do disco efêmero do Render não podem ser recuperadas. Envie novamente.
- CORS não é necessário para o upload via servidor nem para a exibição com `<img>`.
- Configure versionamento ou backup do bucket se as fotos forem críticas.

### 10.5 Segurança

- Use `DEBUG=False` em produção.
- Use uma `SECRET_KEY` longa e aleatória.
- Mantenha `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` ativos. O código ativa os dois quando `DEBUG=False`.
- Restrinja o token R2 ao bucket e à permissão necessária.
- Rotacione o token R2 se houver suspeita de vazamento.
- Restrinja o acesso ao `/admin/`.
- Ative 2FA nas contas do Render e da Cloudflare.
- Não use as senhas demo em produção.
- Não grave segredos no repositório.
- Revise `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` ao usar domínio próprio.

### 10.6 Limitações conhecidas

- O plano free do Render hiberna após 15 minutos sem tráfego. O primeiro acesso após a hibernação pode demorar cerca de 1 minuto.
- O plano free do Render não oferece shell.
- O plano free do Render bloqueia SMTP nas portas 25, 465 e 587. Use um provedor de e-mail por API ou um plano pago.
- A rota `/health/` é de liveness. Ela não testa banco nem R2.
- Alguns testes legados de telas desativadas ainda falham por fixtures duplicadas.
- `relatorio.html` é apenas contexto de engenharia. Ele não é template e não é dependência de runtime.

## 11. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `502` ou `503` no navegador | Gunicorn não iniciou ou a porta está errada. | Verifique o start command e os logs do Render. |
| `DisallowedHost` | Host ausente em `ALLOWED_HOSTS`. | Adicione o domínio ou use `RENDER_EXTERNAL_HOSTNAME`. |
| `CSRF verification failed` | Origem ausente em `CSRF_TRUSTED_ORIGINS`. | Adicione `https://<HOST>` e use HTTPS. |
| `404` em `/media/...` | R2 não configurado ou arquivo antigo. | Configure as variáveis R2 e envie a foto novamente. |
| `ImproperlyConfigured: Cloudflare R2 configurado parcialmente` | Falta uma variável R2. | Defina `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY`. |
| Estáticos sem estilo | `collectstatic` ou build do Tailwind não executou. | Execute o build e verifique o log do Render. |
| Migrações pendentes | O build não aplicou `migrate`. | Execute `python manage.py migrate` e verifique o log. |
| Recuperação de senha não envia e-mail | Backend de console ou SMTP bloqueado. | Configure SMTP e verifique as portas do Render. |
| Primeiro acesso muito lento | Serviço free hibernado. | Aguarde a inicialização ou use um plano pago. |
| Erro de conexão com o banco | `DATABASE_URL` inválida ou banco indisponível. | Verifique a URL, a rede e o status do provedor. |

## 12. Documentação

| Documento | Conteúdo |
|---|---|
| `docs/sdd.md` | Software Design Document e escopo original. |
| `docs/requisitos.md` | RF, RNF, RN, user stories e critérios de aceite. |
| `docs/modelo-dados.md` | Entidades, relacionamentos e estados. |
| `docs/decisoes.md` | Premissas, decisões técnicas e histórico. |
| `docs/como-rodar.md` | Guia local, usuários demo e testes. |
| `docs/autenticacao.md` | Login, cadastro e recuperação de senha. |
| `docs/operacao-resultados.md` | Ativação e operação dos lançamentos. |
| `docs/manual-lancamentos.md` | Manual do usuário para lançamentos e aprovação. |
| `docs/financeiro-refat.md` | Contrato de importação financeira REFAT. |
| `docs/gestao_at.md` | Gestão da AT, associados e solicitações. |
| `docs/entregaveis-at.md` | Produtos e materiais da AT. |
| `docs/entregaveis-projetos.md` | Projetos, materiais e Book. |
| `docs/consulta-materiais.md` | Biblioteca, filtros e relatórios de materiais. |
| `docs/auditoria-numeros.md` | Invariantes e auditoria dos dashboards. |
| `docs/loops.md` | Histórico de implementação por loops. |
| `docs/retrofit/loops.md` | Histórico do retrofit visual. |
| `docs/sdd-dashboard-anual.md` | Regras do painel anual. |

## 13. Checklist de produção

- [ ] `DEBUG=False`.
- [ ] `SECRET_KEY` forte e exclusiva.
- [ ] `DATABASE_URL` de produção configurada.
- [ ] Migrações aplicadas.
- [ ] `collectstatic` executado no build.
- [ ] `static/css/tailwind.css` compilado e versionado.
- [ ] Bucket R2 criado e privado.
- [ ] Token R2 limitado ao bucket.
- [ ] Variáveis `AWS_*` configuradas no Render.
- [ ] Superusuário criado.
- [ ] Usuário Master vinculado ao grupo `Master`.
- [ ] Base inicial confirmada em **Operação → Lançamentos**.
- [ ] `/health/` retorna `200` e `ok`.
- [ ] Login funciona.
- [ ] Upload de foto em Talentos funciona.
- [ ] URL da foto contém `X-Amz-Signature`.
- [ ] Dashboards e relatório mensal abrem.
- [ ] Logs sem erros críticos.
- [ ] Backup do banco realizado antes de mudanças de schema.
- [ ] 2FA ativo no Render e na Cloudflare.
