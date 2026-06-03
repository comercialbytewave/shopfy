# Robo EcomHub

Robo em Python que faz login no portal [EcomHub](https://go.ecomhub.app/login),
navega ate a guia **Produtos**, captura a resposta JSON da API
`https://api.ecomhub.app/api/productsWorkspaces` e grava os dados num banco
**PostgreSQL** modelado com **Prisma**.

O schema do Prisma e gerado **automaticamente** a partir do JSON capturado, de
modo que ele contera todos os campos retornados pela API.

## Como funciona (pipeline)

```
capture  ->  schema  ->  push  ->  import
(login &     (JSON ->    (cria as   (grava os
 captura)    schema.prisma) tabelas)  produtos)
```

| Etapa     | O que faz                                                               |
|-----------|-------------------------------------------------------------------------|
| `capture` | Abre o navegador (Playwright), loga, vai em Produtos e captura o JSON.   |
| `schema`  | Inspeciona o JSON e gera `prisma/schema.prisma` com todos os campos.     |
| `push`    | Roda `prisma db push` (cria tabelas no Postgres) e `prisma generate`.    |
| `import`  | Le o JSON capturado e grava cada produto na tabela `products`.           |

## Pre-requisitos

- Python **3.10 a 3.13** (o Prisma Client Python e o Playwright ainda nao tem
  wheels para o 3.14)
- Um servidor PostgreSQL acessivel
- Conexao com a internet (login no portal + download do Chromium e dos engines)

## Instalacao

### Opcao A — com `uv` (recomendada nesta maquina)

O Python do sistema aqui e o 3.14 (sem `ensurepip` e sem wheels), entao usamos o
[uv](https://docs.astral.sh/uv/) para baixar um Python 3.12 isolado:

```bash
# instala o uv (uma vez)
curl -LsSf https://astral.sh/uv/install.sh | sh

# cria o venv com Python 3.12 e instala tudo
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# ativa o venv (importante: deixa o gerador prisma-client-py no PATH)
source .venv/bin/activate

# navegador do Playwright + variaveis de ambiente
python -m playwright install chromium
cp .env.example .env   # edite: ECOMHUB_EMAIL, ECOMHUB_PASSWORD, DATABASE_URL
```

### Opcao B — venv padrao (Python 3.10–3.13)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

> Sempre rode os comandos com o venv **ativado** (`source .venv/bin/activate`).
> O `prisma generate` precisa enxergar o executavel `prisma-client-py` no PATH.

## Configuracao (`.env`)

| Variavel             | Descricao                                              |
|----------------------|--------------------------------------------------------|
| `ECOMHUB_EMAIL`      | E-mail/usuario do portal                               |
| `ECOMHUB_PASSWORD`   | Senha do portal                                        |
| `DATABASE_URL`       | String de conexao PostgreSQL                           |
| `HEADLESS`           | `true` (sem janela) ou `false` (mostra o navegador)    |

## Uso

```bash
# Executa a pipeline inteira
python main.py all

# Ou rode etapa por etapa (util para depurar)
python main.py capture
python main.py schema
python main.py push
python main.py import
```

Os dados capturados ficam em:
- `data/products_raw.json` — resposta bruta da API
- `data/products.json` — apenas a lista de produtos

Em caso de falha no login/captura, screenshots e HTML sao salvos em `debug/`.

## Estrutura

```
ecohub/
├── main.py                  # orquestrador (CLI)
├── requirements.txt
├── .env.example
├── prisma/
│   └── schema.prisma        # gerado automaticamente
└── src/
    ├── config.py            # carrega o .env
    ├── robot.py             # login + captura (Playwright)
    ├── schema_generator.py  # JSON -> schema.prisma
    └── importer.py          # JSON -> PostgreSQL (Prisma Client)
```

## Observacoes

- A captura usa **interceptacao de rede**: pegamos exatamente o JSON que o portal
  recebe da API, sem depender de como a tela renderiza os produtos.
- Os seletores de login usam heuristicas (email/senha/botao). Se o portal mudar o
  layout e o login falhar, confira os arquivos em `debug/` e ajuste os seletores
  em `src/robot.py`.
- Se a API for paginada, pode ser necessario percorrer as paginas; o ponto de
  ajuste e a funcao `capture()` em `src/robot.py`.
