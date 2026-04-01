# LinkedIn Gmail Jobs Hub

API em Python para centralizar, sincronizar e consultar vagas do LinkedIn recebidas por e-mail no Gmail.

O projeto lê mensagens via Gmail API, identifica templates do LinkedIn, extrai uma ou várias vagas por e-mail, persiste em SQLite e expõe tudo por API com FastAPI.

## Principais capacidades
- FastAPI com documentação automática em `/docs`
- proteção simples via header `X-API-Key`
- autenticação Gmail com OAuth2 (`credentials.json` + `token.json`)
- sync assíncrono com `BackgroundTasks`
- parsing de templates reais do LinkedIn
- suporte a **múltiplas vagas no mesmo e-mail**
- deduplicação por `linkedin_job_id` e URL normalizada
- persistência em SQLite com SQLAlchemy
- trilha de auditoria para e-mails ignorados e templates desconhecidos
- filtro opcional por `is_easy_apply` (`Candidatura simplificada`) na listagem de vagas
- testes unitários para parser, API, sync, queries Gmail e deduplicação

## Stack
- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite
- BeautifulSoup + lxml
- Gmail API
- Pytest

## Estrutura resumida
- `app/api/`: rotas da API
- `app/services/`: parsing, sync, normalização, retry e deduplicação
- `app/persistence/`: banco e repositórios
- `app/tests/`: testes automatizados
- `scripts/bootstrap_gmail_token.py`: geração do `token.json`
- `scripts/seed_demo_data.py`: carga de dados de exemplo

## Endpoints principais
- `GET /api/v1/health`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/sync`
- `GET /api/v1/sync/runs`
- `GET /api/v1/sync/runs/{run_id}`
- `GET /api/v1/sync/runs/{run_id}/events`
- `GET /api/v1/stats/summary`
- `GET /api/v1/ignored-emails`
- `GET /api/v1/ignored-emails/by-reason`

## Pré-requisitos
- Python 3.11 ou superior
- credenciais OAuth do Google para Gmail API
- arquivo `credentials.json`
- ambiente virtual recomendado

## Configuração rápida
### 1. Criar e ativar o ambiente virtual
```bash
python -m venv .venv
```

Linux/macOS:
```bash
source .venv/bin/activate
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

Windows CMD:
```bat
.venv\Scripts\activate.bat
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Criar o arquivo `.env`
```bash
cp .env.example .env
```

Ajuste pelo menos:
- `API_KEY`
- `GOOGLE_CREDENTIALS_FILE`
- `GOOGLE_TOKEN_FILE`
- `GMAIL_NEWER_THAN_DAYS`
- `GMAIL_MAX_RESULTS`
- `ALLOWED_SENDER_CONTAINS`
- `ENABLE_BROAD_LINKEDIN_FALLBACK`

Exemplo importante:
```env
ALLOWED_SENDER_CONTAINS=linkedin.com
ENABLE_BROAD_LINKEDIN_FALLBACK=true
```

## Geração do token do Gmail
1. Crie um projeto no Google Cloud.
2. Habilite a Gmail API.
3. Crie credenciais OAuth para aplicativo desktop.
4. Salve o arquivo em `./secrets/credentials.json`.
5. Rode:

```bash
python -m scripts.bootstrap_gmail_token
```

Isso gera `./secrets/token.json`, usado nas próximas execuções.

## Como iniciar a API
```bash
uvicorn app.main:app --reload
```

Depois acesse:
- Swagger: `http://127.0.0.1:8000/docs`
- Healthcheck: `http://127.0.0.1:8000/api/v1/health`

## Seed de dados para testar sem Gmail
Para subir a API e testar endpoints sem depender de sync real:

```bash
python -m scripts.seed_demo_data
```

## Fluxo atual de sincronização
A estratégia atual prioriza segurança e redução de ruído:
1. tenta queries restritas com remetente permitido
2. agrega os `gmail_message_id` encontrados
3. remove mensagens já processadas
4. faz parsing e deduplicação por vaga
5. usa fallback amplo `linkedin newer_than:Xd` **somente** quando as queries restritas retornam zero e quando `ENABLE_BROAD_LINKEDIN_FALLBACK=true`

Isso evita que buscas amplas tragam e-mails externos ou ruído desnecessário na maioria dos runs.

## Templates do LinkedIn suportados
### `email_jobs_viewed_job_reminder_01`
- vagas semelhantes / vagas visualizadas
- extrai múltiplas vagas no mesmo e-mail

### `email_jobs_saved_job_reminder_01`
- vaga salva ainda disponível + vagas relacionadas
- extrai a vaga principal e vagas adicionais

### `email_application_confirmation_with_nba_01`
- confirmação de candidatura + vagas semelhantes
- extrai a vaga confirmada e recomendações do corpo

### `email_job_alert_digest_01`
- alerta/digest de vagas
- usa parser dedicado para melhorar `title`, `company` e `location_raw`

Quando chega um template diferente, o sistema registra o caso em `unknown_email_templates` para evolução futura.

## Campo `is_easy_apply`
O projeto agora suporta o campo `is_easy_apply: bool | null` por vaga.

Regra atual:
- `True` quando o parser HTML identifica explicitamente o texto **`Candidatura simplificada`**
- `False` quando a vaga foi analisada no HTML e esse marcador não aparece no bloco correspondente
- `None` quando não há base suficiente para inferência

Esse campo pode variar dentro do mesmo e-mail, então ele é salvo **por vaga**, não por mensagem.

### Filtro no endpoint `GET /api/v1/jobs`
Exemplos:
```bash
curl -H "X-API-Key: SUA_CHAVE" "http://127.0.0.1:8000/api/v1/jobs?is_easy_apply=true"
```

```bash
curl -H "X-API-Key: SUA_CHAVE" "http://127.0.0.1:8000/api/v1/jobs?is_easy_apply=false"
```

## Header obrigatório
```text
X-API-Key: <valor definido no .env>
```

## Exemplo de resposta do `POST /api/v1/sync`
```json
{
  "run_id": 1,
  "status": "queued"
}
```

## Logs e observabilidade
O projeto grava logs no console e também em `logs/app.log`.

O sync registra, entre outros pontos:
- query Gmail efetiva
- assunto do e-mail
- template do LinkedIn
- quantidade de vagas extraídas por e-mail
- inserções, duplicatas e falhas
- templates desconhecidos

## E-mails ignorados e templates desconhecidos
Quando uma mensagem não deve virar vaga, o sistema pode auditá-la em estruturas de apoio para investigação posterior.

Isso ajuda a responder perguntas como:
- por que um e-mail foi descartado?
- qual motivo aparece com mais frequência?
- quais templates novos ainda precisam de parser dedicado?

## Banco local e atualização de schema
Se você já tinha um banco SQLite anterior, a aplicação tenta adicionar automaticamente colunas novas em `jobs` no startup, incluindo `is_easy_apply`.

Em ambiente local, se quiser resetar o banco:

Windows PowerShell:
```powershell
Remove-Item .\data\jobs_hub.db
```

Linux/macOS:
```bash
rm -f ./data/jobs_hub.db
```

Depois, opcionalmente:
```bash
python -m scripts.seed_demo_data
```

## Como executar os testes
### Rodar toda a suíte
```bash
pytest
```

### Rodar com mais detalhes
```bash
pytest -vv
```

### Rodar um arquivo específico
```bash
pytest app/tests/test_parser.py -vv
```

```bash
pytest app/tests/test_api.py -vv
```

### Rodar um teste específico
```bash
pytest app/tests/test_parser.py -k easy_apply -vv
```

### Rodar com cobertura
Se você instalar as dependências de desenvolvimento do `pyproject.toml`:
```bash
pip install -e .[dev]
pytest --cov=app --cov-report=term-missing
```

## O que os testes cobrem hoje
- parsing dos principais templates reais do LinkedIn
- extração de múltiplas vagas por e-mail
- detecção de `is_easy_apply`
- normalização de URL
- deduplicação
- filtros e autenticação básica da API
- queries Gmail e partes centrais do sync

## Limitações atuais e próximos passos recomendados
- adicionar teste de persistência do `is_easy_apply` no SQLite
- adicionar teste de migração/schema para bancos antigos
- continuar refinando o parser de `email_job_alert_digest_01`
- expandir fixtures reais para novos templates do LinkedIn

## Arquivos que não devem subir para o GitHub
- `secrets/credentials.json`
- `secrets/token.json`
- `.env`
- `data/jobs_hub.db`

O `.gitignore` já está configurado para isso.

## Comandos mais usados
```bash
python -m scripts.bootstrap_gmail_token
python -m scripts.seed_demo_data
uvicorn app.main:app --reload
pytest
```
