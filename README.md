# LinkedIn Gmail Jobs Hub — Fase 1.5

API em Python para centralizar e processar vagas do LinkedIn recebidas por e-mail no Gmail.

## O que já está implementado
- FastAPI com Swagger em `/docs`
- Segurança simples via `X-API-Key`
- Integração com Gmail API usando OAuth2 e refresh de token
- **Script de bootstrap** para gerar `token.json`
- Sync assíncrono com `BackgroundTasks` e retorno `202 Accepted`
- Parser com suporte a **múltiplas vagas no mesmo e-mail**
- Parser HTML com BeautifulSoup usando `lxml`
- Normalização forte da URL do LinkedIn
- Extração de `linkedin_job_id`
- Deduplicação em camadas
- Persistência em SQLite com SQLAlchemy
- **Melhoria no banco** com novos campos (`email_subject`, `linkedin_template`, `parser_used`) e tabela `unknown_email_templates`
- Registro de templates desconhecidos para evolução futura
- **Script de seed** com dados de exemplo
- Registro de falhas por etapa
- Testes mínimos do parser, normalização, dedupe e API

## Endpoints
- `GET /api/v1/health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/sync`
- `GET /api/v1/sync/runs`
- `GET /api/v1/sync/runs/{run_id}`
- `GET /api/v1/sync/runs/{run_id}/events`
- `GET /api/v1/stats/summary`

## Como iniciar o projeto
### 0. Ajustar o .env
- copie `.env.example` para `.env`
- defina `API_KEY`
- confira `GOOGLE_CREDENTIALS_FILE` e `GOOGLE_TOKEN_FILE`
- ajuste `GMAIL_NEWER_THAN_DAYS` e `GMAIL_MAX_RESULTS` se necessário

### 1. Preparar o ambiente
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
```

No `.env`, mantenha este filtro inicial para garantir que só mensagens com remetente do ecossistema LinkedIn entrem no pipeline:

```env
ALLOWED_SENDER_CONTAINS=linkedin.com
```

No fluxo de busca do Gmail, a prioridade agora é:
1. aplicar `ALLOWED_SENDER_CONTAINS` na própria query (ex.: `from:linkedin.com newer_than:7d`)
2. tentar queries específicas de vagas
3. manter `linkedin newer_than:Xd` apenas como fallback amplo


### 2. Gerar o token do Gmail
```bash
python -m scripts.bootstrap_gmail_token
```

### 3. Iniciar a API
```bash
uvicorn app.main:app --reload
```

### 4. Abrir a documentação
- Swagger: `http://127.0.0.1:8000/docs`
- Healthcheck: `GET /api/v1/health`

## Bootstrap do token do Gmail
1. Crie um projeto no Google Cloud.
2. Habilite a Gmail API.
3. Crie credenciais OAuth para app desktop.
4. Salve o arquivo em `./secrets/credentials.json`.
5. Gere o token inicial com:

```bash
python -m scripts.bootstrap_gmail_token
```

Esse comando precisa estar no README porque é o fluxo padrão para gerar `./secrets/token.json`.

Depois disso, o `token.json` será salvo em `./secrets/token.json` e o refresh será feito automaticamente.

## Seed de dados para testar a API sem Gmail
Para subir a API e já ver vagas em `/docs` ou nos endpoints, rode:

```bash
python -m scripts.seed_demo_data
```

## Melhorias no parser
O parser agora trata melhor dois cenários:

### 1. E-mails de vaga única
- `email_job_alert_digest_01` agora tem parser dedicado (`linkedin_job_alert_digest_v1`) para melhorar extração de `title`, `company` e `location_raw`.
Continua suportando:
- links diretos `/jobs/view/...`
- links com query string e tracking
- links de redirecionamento que embutem a URL da vaga
- extração de título a partir do assunto
- extração de empresa pelo assunto e por padrões de texto
- variações simples de remoto, híbrido e presencial

### 2. E-mails com múltiplas vagas
Para templates conhecidos como `email_jobs_viewed_job_reminder_01`, o parser prefere `text/plain` e extrai blocos repetidos no formato:
- título
- empresa
- local
- `Visualizar vaga: URL`

Cada vaga vira um registro separado no banco, mantendo o mesmo `gmail_message_id` do e-mail original.


## Templates do LinkedIn suportados atualmente
O parser já reconhece e trata via `text/plain` estes templates reais do LinkedIn:

- `email_jobs_viewed_job_reminder_01`
  - e-mail de vagas semelhantes / vagas visualizadas
  - extrai múltiplas vagas do mesmo e-mail
- `email_jobs_saved_job_reminder_01`
  - e-mail de vaga salva ainda disponível + outras vagas salvas
  - extrai a vaga principal e as vagas salvas listadas no corpo
- `email_application_confirmation_with_nba_01`
  - e-mail de confirmação de candidatura + vagas semelhantes
  - extrai a vaga confirmada e as vagas recomendadas no corpo

Quando chega um template diferente, o sistema continua registrando em `unknown_email_templates` para evolução futura.

## Logs e observabilidade mínima
O projeto grava logs no console e também em `logs/app.log` com rotação simples.

O sync agora registra no log:
- query Gmail efetiva
- assunto do e-mail
- `X-LinkedIn-Template`
- quantidade de vagas extraídas por e-mail
- inserções, duplicatas e falhas

Também registra templates desconhecidos na tabela `unknown_email_templates`.

## Registro de templates desconhecidos
Quando chega um e-mail com `X-LinkedIn-Template` não mapeado, o sistema:
- escreve um warning no log
- salva um registro em `unknown_email_templates`
- tenta seguir com fallback genérico

Isso ajuda a evoluir o parser sem perder exemplos reais.

## Banco / migração local
Se você já tinha um banco SQLite antigo, a aplicação tenta adicionar automaticamente as colunas novas em `jobs` no startup.

Mesmo assim, se estiver em ambiente de desenvolvimento e quiser limpar qualquer resíduo, você pode apagar o banco local e recriar:

```bash
# Windows PowerShell
Remove-Item .\data\jobs_hub.db

# depois
python -m scripts.seed_demo_data
```

## Header obrigatório
```text
X-API-Key: <valor definido no .env>
```

## Exemplo de resposta do POST /sync
```json
{
  "run_id": 1,
  "status": "queued"
}
```

## GitHub
### Arquivo `.gitignore`
O projeto inclui `.gitignore` na raiz para evitar versionar `.env`, `secrets/credentials.json`, `token.json`, caches, bancos locais e ambientes virtuais.

### Como subir no GitHub
```bash
git init
git branch -M main
git add .
git commit -m "feat: fase 1.2 do linkedin gmail jobs hub"
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

## Checklist rápido
- copie `.env.example` para `.env`
- rode `python -m scripts.bootstrap_gmail_token`
- rode `python -m scripts.seed_demo_data` se quiser dados de teste
- suba a API
- abra `/docs`
- valide `POST /sync`, `GET /jobs` e `GET /stats/summary`


## Testes unitários com e-mails reais do LinkedIn
O projeto agora inclui fixtures `.eml` reais para validar parsing dos principais formatos já encontrados:

- `linkedin_multi_jobs.eml`
- `linkedin_saved_jobs_reminder.eml`
- `linkedin_application_confirmation.eml`

Esses testes validam:
- quantidade de vagas extraídas por template
- `linkedin_job_id` esperado
- `parser_used` aplicado
- `linkedin_template` correspondente

## Rodando os testes
```bash
pytest
```

## Arquivos que não devem subir para o GitHub
- `secrets/credentials.json`
- `secrets/token.json`
- `.env`
- `data/jobs_hub.db`

O `.gitignore` já está configurado para isso.


## Logs em disco
Além do terminal, a aplicação agora grava logs em `./logs/app.log` com rotação simples.

## Estratégia atual de sincronização
Nesta versão, o sync usa múltiplas queries em ordem de relaxamento, agrega os `gmail_message_id` encontrados, remove IDs já presentes em `processed_gmail_messages` e só então processa as mensagens novas. Isso evita reler sempre o mesmo e-mail em cada execução.

## Correção para e-mails com múltiplas vagas
A aplicação agora aceita várias vagas para o mesmo `gmail_message_id`. Para bancos SQLite antigos, o startup tenta migrar automaticamente a tabela `jobs` removendo a unicidade indevida em `gmail_message_id` e recriando os índices necessários.

## Comandos recomendados após atualizar
```bash
python -m scripts.bootstrap_gmail_token
uvicorn app.main:app --reload
```


## O que melhoramos nesta versão
- seção explícita de inicialização do projeto no README
- testes unitários com um e-mail real do LinkedIn em formato `.eml`
- correção do `SyncRunRepository.save()` para não perder contadores por rollback indevido
- paginação na listagem de mensagens do Gmail
- agregação de resultados de múltiplas queries do Gmail em vez de parar na primeira que retornar algo
- tabela `processed_gmail_messages` para evitar reprocessar o mesmo `gmail_message_id` em todos os runs
- filtro de mensagens já processadas antes do parsing e da deduplicação por vaga
- fallback automático para queries menos restritivas quando a busca original voltar vazia
- encerramento limpo do sync quando nenhuma mensagem nova corresponder à query
- configuração de retry via `.env`
- classificação padronizada de erros (`network_dns_error`, `network_timeout`, `gmail_auth_error`, `gmail_rate_limit`, `db_integrity_error`, etc.)
- retry com backoff exponencial e jitter para falhas transitórias de rede e Gmail
- tabela `sync_run_events` para trilha de execução do sync
- endpoint `GET /api/v1/sync/runs/{run_id}/events`
- tratamento melhor de falhas de DNS/rede sem deixar a execução em estado inconsistente
- fechamento consistente do run com `completed` ou `failed`
- logs no console e em disco com rotação em `logs/app.log`

## O que deixamos para depois
- fila dedicada com Redis/Arq ou Celery
- Postgres como banco principal para multiusuário e maior concorrência
- autenticação mais robusta para a API (JWT/OAuth2)
- alertas externos (Telegram/Discord/e-mail) para falhas de sync
- observabilidade avançada com tracing e error reporting centralizado
- dashboard visual separado da API e do Swagger


## Sugestões de evolução usando esses e-mails
Com base nos novos e-mails analisados, estes próximos passos passam a fazer bastante sentido:

- adicionar um campo opcional de contexto da vaga no e-mail, por exemplo `email_job_role`
  - `primary_saved_job`
  - `saved_related_job`
  - `application_confirmed_job`
  - `application_recommended_job`
- criar filtros na API para `linkedin_template`
- criar score/regras por template para priorizar vagas mais relevantes
- separar no dashboard futuro as vagas capturadas de:
  - vaga salva
  - vaga recomendada
  - vaga já candidata

Na versão atual, esse contexto ainda pode ser inferido por `linkedin_template` e `parser_used`, e também pode ser armazenado no `raw_metadata_json` se você quiser evoluir isso depois.



## Filtro de segurança para e-mails genéricos do LinkedIn

O projeto **mantém** a busca genérica `linkedin newer_than:Xd` como último fallback, mas agora aplica um funil rígido antes do parsing/persistência:

- só processa e-mails de remetentes do ecossistema LinkedIn
- ignora templates conhecidos que não são de vaga, como convites, mensagens, analytics e grupos
- só persiste registros em `jobs` quando existe `linkedin_job_id` ou `linkedin_job_url`
- mensagens não elegíveis são marcadas em `processed_gmail_messages` com `outcome` de ignoradas e registradas em `unknown_email_templates` com o motivo

### Filtro inicial de remetente
O pipeline só processa mensagens cujo `From` contenha algum fragmento configurado em `ALLOWED_SENDER_CONTAINS`.

Exemplo recomendado:

```env
ALLOWED_SENDER_CONTAINS=linkedin.com
```

### Templates de vaga aceitos
- `email_jobs_viewed_job_reminder_01`
- `email_jobs_saved_job_reminder_01`
- `email_application_confirmation_with_nba_01`
- `email_job_alert_digest_01`

### Templates não-vaga ignorados
- `email_pymk_02`
- `email_m2m_invite_single_01`
- `email_member_message_v2`
- `email_groups_recommended_by_admin_01`
- `email_weekly_analytics_recap_v2`


## E-mails ignorados

O projeto agora expõe endpoints para auditar mensagens descartadas antes do parser/persistência. Isso ajuda a verificar ruído trazido pela busca genérica `linkedin newer_than:Xd` sem poluir a tabela `jobs`.

Endpoints:
- `GET /api/v1/ignored-emails`
- `GET /api/v1/ignored-emails/by-reason`

Exemplos de motivo:
- `unsupported_sender`
- `non_job_template`
- `missing_job_link`
- `missing_job_signal`

Uso sugerido:
1. rode um sync
2. consulte `GET /api/v1/ignored-emails/by-reason`
3. veja quais tipos de e-mail estão sendo descartados
4. só promova um template novo para parser de vaga quando houver evidência real de job link e estrutura consistente


## Fallback amplo do Gmail

O projeto tenta primeiro queries restritas por remetente permitido (`ALLOWED_SENDER_CONTAINS`).
O fallback amplo `linkedin newer_than:Xd` só roda quando essas queries retornam zero resultados **e** `ENABLE_BROAD_LINKEDIN_FALLBACK=true`.

Exemplo no `.env`:

```env
ALLOWED_SENDER_CONTAINS=linkedin.com
ENABLE_BROAD_LINKEDIN_FALLBACK=true
```

Para desligar totalmente o fallback amplo:

```env
ENABLE_BROAD_LINKEDIN_FALLBACK=false
```
