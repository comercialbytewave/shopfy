# 📋 Estrutura do Projeto Primecod

## 🗂️ Diretórios

```
primecod/
│
├── 📄 main.py                    # Arquivo principal - execute este para rodar o pipeline
│
├── 🔧 .env                       # Configurações (NÃO COMPARTILHE - contém token)
├── 📋 .env.example              # Template do .env
│
├── 📚 requirements.txt           # Dependências Python
├── 📖 README.md                 # Documentação completa
├── 🚀 QUICKSTART.md             # Guia de início rápido
├── 📝 STRUCTURE.md              # Este arquivo
│
├── 🗂️ prisma/                   # Configuração Prisma ORM
│   └── 📄 schema.prisma         # Schema do banco PostgreSQL (GERADO AUTOMATICAMENTE)
│
├── 📦 src/                      # Código fonte Python
│   ├── 📄 __init__.py           # Inicialização do módulo
│   ├── 📄 config.py             # Carrega .env e configurações
│   ├── 📄 api_client.py         # Cliente HTTP - acessa API Primecod
│   ├── 📄 schema_generator.py   # Gera schema.prisma automaticamente
│   └── 📄 importer.py           # Importa JSON para PostgreSQL
│
├── 📊 data/                     # Dados processados (GERADOS AUTOMATICAMENTE)
│   ├── 📄 products.json         # JSON de produtos processados (501 registros)
│   ├── 📄 products_raw.json     # Última resposta bruta da API
│   └── 📄 products.json.example # Exemplo de estrutura
│
├── 🐛 debug/                    # Arquivos de debug (se houver erros)
│
└── 🚀 init.sh                   # Script de inicialização (Linux/Mac)
```

## 🔄 Pipeline de Execução

```
main.py all
    ↓
[1/4] CAPTURA
    ├─ Conecta à API Primecod
    ├─ Faz paginação (42 páginas de 12 produtos)
    ├─ Obtém 501 produtos total
    └─ Salva em data/products.json

[2/4] SCHEMA
    ├─ Lê data/products.json
    ├─ Analisa tipos de cada campo
    ├─ Gera prisma/schema.prisma
    └─ Cria modelo Product com 47 campos

[3/4] PUSH
    ├─ `prisma db push` aplica schema no PostgreSQL
    ├─ Cria tabela "products"
    └─ Gera cliente Python do Prisma

[4/4] IMPORT
    ├─ Lê data/products.json
    ├─ Conecta ao PostgreSQL via Prisma
    ├─ Insere/atualiza (upsert) cada produto
    └─ Finaliza com 501 registros importados
```

## 📊 Estrutura de Dados

### Campos Principais do Produto

```python
Product {
  id: Int (chave primária)
  name: String
  description: String
  sku: String
  price: Float
  cost: Float
  quantity: Int
  weight: Float
  status: String
  category_id: Int
  category_name: String
  stock: String (High/Medium/Low)
  
  # Dados complexos (JSON)
  images: Json (array de objetos)
  countries: Json (array com info de país)
  country_ids: Json (array de IDs)
}
```

## 🔑 Variáveis de Ambiente (.env)

| Variável | Exemplo | Descrição |
|----------|---------|-----------|
| PRIMECOD_API_URL | `https://api.primecod.app/api/catalog/products` | URL da API |
| PRIMECOD_API_TOKEN | `369\|MrP5nb...` | Token Bearer de autenticação |
| PRIMECOD_API_TOKEN_TYPE | `Bearer` | Tipo de autenticação |
| PRIMECOD_COUNTRY_CODE | `es` | Código do país (es=Spain, pt=Portugal) |
| PRIMECOD_PAGE_SIZE | `12` | Itens por página (máx. 50) |
| DATABASE_URL | `postgresql://user:pass@localhost:5432/primecod` | Conexão PostgreSQL |

## 🛠️ Dependências Python

```
python-dotenv==1.0.1    # Carrega .env
prisma==0.15.0          # ORM e cliente PostgreSQL
requests==2.31.0        # HTTP client para API
```

## 🎯 Fluxo de Dados

```
API Primecod
    ↓
requests.get()
    ↓
JSON Response (paginated)
    ↓
data/products.json
    ↓
schema_generator.py (analisa tipos)
    ↓
prisma/schema.prisma
    ↓
prisma db push (cria tabelas)
    ↓
importer.py (Prisma Client)
    ↓
PostgreSQL Database
```

## 📝 Exemplos de Uso

### Executar tudo
```bash
python main.py all
```

### Apenas capturar dados
```bash
python main.py capture
# Gera: data/products.json
```

### Apenas gerar schema
```bash
python main.py schema
# Gera: prisma/schema.prisma
```

### Apenas criar tabelas
```bash
python main.py push
# Executa: prisma db push
```

### Apenas importar
```bash
python main.py import
# Insere em: PostgreSQL
```

## 🔍 Arquivos Importantes

### main.py
Orquestrador que coordena todas as etapas:
- Define os 4 passos do pipeline
- Valida pré-requisitos
- Gerencia venv do Prisma

### src/config.py
Carrega configurações:
- Lê arquivo `.env`
- Define caminhos de pastas
- Valida variáveis necessárias

### src/api_client.py
Acessa a API Primecod:
- Faz requisições HTTP com token Bearer
- Implementa paginação automática
- Salva JSON em `data/products.json`

### src/schema_generator.py
Infere schema do banco:
- Analisa tipos de dados de cada campo
- Detecta campos nulos/obrigatórios
- Gera `prisma/schema.prisma` dinâmico

### src/importer.py
Importa dados para PostgreSQL:
- Lê `data/products.json`
- Converte tipos de dados
- Faz upsert no banco (sem duplicatas)
- Usa Prisma Client Python

## 🔄 Ciclo de Vida

```
1ª Execução:
  ✓ Cria data/products.json
  ✓ Cria prisma/schema.prisma
  ✓ Cria tabela no PostgreSQL
  ✓ Insere 501 produtos

2ª Execução (update):
  ✓ Captura dados novamente
  ✓ Regera schema.prisma (mesma estrutura)
  ✓ Tabela já existe (push é idempotente)
  ✓ Atualiza produtos existentes (upsert)

Nª Execução:
  ✓ Sempre sincroniza os dados
  ✓ Sem duplicatas (chave: id do produto)
  ✓ Pode rodar periodicamente (ex: cron job)
```

## 📈 Estatísticas da API

- **Total de Produtos**: 501
- **Páginas**: 42
- **Itens por Página**: 12
- **Campos por Produto**: ~47
- **País Padrão**: Espanha (es)

## 🗄️ Consultas SQL Úteis

```sql
-- Ver estrutura
SELECT * FROM products LIMIT 1;

-- Contar produtos
SELECT COUNT(*) FROM products;

-- Agrupar por categoria
SELECT category_name, COUNT(*) as qty FROM products GROUP BY category_name;

-- Produtos com estoque alto
SELECT name, stock, quantity FROM products WHERE stock = 'High';

-- Top 10 mais caros
SELECT name, price, cost FROM products ORDER BY price DESC LIMIT 10;
```

## 🚨 Troubleshooting

### Erro: DATABASE_URL não definido
✓ Adicione ao .env

### Erro: Conexão recusada
✓ Verifique se PostgreSQL está rodando

### Erro: Token inválido (401)
✓ Copie token correto do .env.example

### Erro: Prisma não encontrado
✓ Execute: `python -m prisma generate`

### Erro: Arquivo não encontrado
✓ Execute sempre a partir da pasta `primecod/`

## 📚 Recursos

- [README.md](README.md) - Documentação completa
- [QUICKSTART.md](QUICKSTART.md) - Guia de início rápido
- [Prisma Docs](https://www.prisma.io/docs/orm/overview/introduction) - ORM documentation
- [API Primecod](https://api.primecod.app/api/catalog/products) - API endpoint

---

**Versão**: 1.0  
**Última atualização**: 3 de junho de 2026  
**Status**: ✅ Produção
