# Mural de Ideias Distribuido

Aplicacao simples para demonstrar premissas de sistemas distribuidos usando tecnologias open-source:

- **Frontend estatico**: tela web em HTML, CSS e JavaScript.
- **API REST stateless**: FastAPI recebe as ideias e conversa com banco/cache/fila.
- **Banco de dados distribuido**: PostgreSQL guarda os dados de forma persistente.
- **Fila e cache**: Redis/Key Value desacopla a API do processamento e acelera leituras.
- **Worker separado**: outro servico processa tarefas em segundo plano.
- **Containerizacao**: Docker facilita executar localmente e publicar na nuvem.
- **Observabilidade basica**: endpoints de health check mostram banco, Redis, fila e worker.

## Como funciona

1. O usuario cadastra uma ideia no navegador.
2. A API grava a ideia no PostgreSQL com status `queued`.
3. A API envia o ID da ideia para uma fila Redis.
4. O worker consome a fila, simula uma analise e atualiza a ideia para `done`.
5. A tela consulta a API periodicamente e mostra status, tags e metricas.

## Rodando localmente

Requisitos:

- Docker
- Docker Compose

Comando:

```bash
docker compose up --build
```

Acesse:

- Sistema: http://localhost:8000
- Health da API: http://localhost:8000/api/health
- Health do worker: http://localhost:8001/health

Para parar:

```bash
docker compose down
```

### Se o Docker Desktop nao iniciar

Se aparecer `Docker Desktop is unable to start`, o problema esta no Docker/WSL do Windows, nao no codigo do projeto.

No PowerShell como **Administrador**, rode:

```powershell
wsl --shutdown
wsl --update --web-download
wsl --set-default-version 2
Start-Service com.docker.service
```

Depois abra o Docker Desktop, espere ficar com status de iniciado e tente novamente:

```bash
docker compose up --build
```

Se o comando `wsl --update --web-download` falhar, atualize o WSL pela Microsoft Store ou reinstale/atualize o Docker Desktop.

## Publicando na nuvem Render

A nuvem escolhida foi a **Render**, porque ela permite subir web services, PostgreSQL e Key Value/Redis por Blueprint, mantendo a infraestrutura declarada no arquivo `render.yaml`.

Passos:

1. Crie um repositorio no GitHub e envie estes arquivos.
2. Entre no painel da Render.
3. Clique em **New > Blueprint**.
4. Conecte o repositorio do GitHub.
5. Confirme os recursos listados pelo `render.yaml`.
6. Clique em **Deploy Blueprint**.
7. Abra a URL gerada para o servico `mural-distribuido-api`.
8. Se estiver usando plano gratuito, abra tambem `/health` no servico `mural-distribuido-worker` antes da demonstracao para acordar o worker caso ele esteja dormindo.

Depois do deploy, use este formato na entrega:

```text
PPT: docs/apresentacao_mural_distribuido.pptx
Link do sistema: https://URL-GERADA-PELA-RENDER
```

## Roteiro curto para apresentar

- **Arquitetura**: navegador -> API REST -> PostgreSQL; API -> Redis; worker -> Redis/PostgreSQL.
- **Sistemas distribuidos**: servicos independentes, comunicacao por rede, fila assincrona, persistencia externa, cache, stateless API e health checks.
- **Nuvem**: Render com Blueprint, containers, Postgres gerenciado e Redis/Key Value.
- **Beneficio**: se o processamento ficar lento, a API continua respondendo e o worker processa em segundo plano.
