# Primecod API Importer

Importador automático de produtos da API Primecod para banco de dados PostgreSQL usando Prisma.

## Estrutura do Projeto

```
primecod/
├── main.py                 # Orquestrador principal
├── .env                    # Variáveis de ambiente
├── requirements.txt        # Dependências Python
├── prisma/
│   └── schema.prisma       # Schema do banco (gerado automaticamente)
├── src/
│   ├── __init__.py
│   ├── config.py           # Carregamento de configurações
│   ├── api_client.py       # Cliente HTTP para a API
│   ├── schema_generator.py # Gerador do schema Prisma
│   └── importer.py         # Importador para o banco
├── data/
│   ├── products.json       # Produtos capturados (gerado)
│   └── products_raw.json   # Resposta bruta da API (gerado)
└── debug/                  # Arquivos de debug (se houver)
```

## Configuração

### 1. Variáveis de Ambiente (.env)

```env
# API Primecod
PRIMECOD_API_URL=https://api.primecod.app/api/catalog/products
PRIMECOD_API_TOKEN=369|MrP5nbIaxH6qIXCtnrAeCRkCJO1bxWGqgUMM5BBZ84f76b16
PRIMECOD_API_TOKEN_TYPE=Bearer
PRIMECOD_COUNTRY_CODE=es
PRIMECOD_PAGE_SIZE=12

# Banco de dados
DATABASE_URL=postgresql://user:password@localhost:5432/primecod
```

### 2. Instalação de Dependências

```bash
pip install -r requirements.txt
```

### 3. Preparar o Banco PostgreSQL

Certifique-se de que o PostgreSQL está rodando e crie o banco:

```bash
createdb primecod
```

## Uso

### Executar Todo o Pipeline

```bash
python main.py all
```

### Executar Etapas Individuais

```bash
# 1. Capturar produtos da API
python main.py capture

# 2. Gerar schema Prisma baseado nos dados
python main.py schema

# 3. Criar tabelas no banco (prisma db push)
python main.py push

# 4. Importar dados para o banco
python main.py import
```

## O que Cada Etapa Faz

### Capture (Captura)
- Acessa a API Primecod com paginação
- Faz requisições com token Bearer
- Salva todos os produtos em `data/products.json`
- Salva resposta bruta em `data/products_raw.json`

### Schema (Gerar Schema)
- Analisa o JSON de produtos
- Infere tipos de dados para cada campo
- Gera `prisma/schema.prisma` automaticamente

### Push (Criar Tabelas)
- Usa `prisma db push` para criar as tabelas no PostgreSQL
- Gera o cliente Python do Prisma

### Import (Importar)
- Lê o JSON de produtos
- Converte tipos de dados apropriadamente
- Insere ou atualiza registros no banco (upsert)
- Exibe contagem de registros inseridos

## Exemplo de Saída

```
[1/4] Capturando produtos da API Primecod...
  [api] Total de paginas: 42
  [api] Pagina 1/42: 12 produto(s)
  [api] Pagina 2/42: 12 produto(s)
  ...
OK! 501 produto(s) capturado(s)
  Salvos em: /path/to/data/products.json

[2/4] Gerando schema Prisma...
OK! Schema gerado com 47 campo(s)
  Salvo em: /path/to/prisma/schema.prisma

[3/4] Criar tabelas no banco (prisma db push)...
[Database] ✓ Completed in 123ms
✔ Prisma Client Python generated successfully

[4/4] Importar para o banco...
OK! 501 produto(s) gravado(s) na tabela 'products'.

>>> Pipeline completa com sucesso!
```

## Estrutura de Dados

Os produtos são importados da API com os seguintes campos principais:

- `id` (Int) - ID único do produto
- `name` (String) - Nome do produto
- `description` (String) - Descrição completa
- `sku` (String) - SKU do produto
- `price` (Float) - Preço
- `cost` (Float) - Custo
- `quantity` (Int) - Quantidade em estoque
- `status` (String) - Status (published, draft, etc.)
- `category_id` (Int) - ID da categoria
- `category_name` (String) - Nome da categoria
- `stock` (String) - Nível de estoque (High, Medium, Low)
- `images` (Json) - Array de imagens
- `countries` (Json) - Informações de países

E muitos outros campos conforme o JSON da API.

## Solução de Problemas

### Erro: DATABASE_URL não definido
Adicione `DATABASE_URL` ao arquivo `.env` com a URL de conexão ao PostgreSQL.

### Erro: Conexão recusada ao banco
Verifique se o PostgreSQL está rodando:
```bash
sudo service postgresql status
```

### Erro: Não consegue conectar à API
Verifique:
- Token de autenticação está correto
- URL da API está acessível
- Conexão com internet disponível

### Erro: Prisma Client não encontrado
Execute:
```bash
python -m prisma generate
```

## Notas

- A API Primecod tem paginação de 12 produtos por página
- O filtro de país está configurado para `es` (Espanha)
- Dados são salvos em JSON antes de serem importados para o banco
- Reimportações usam upsert para não duplicar registros
