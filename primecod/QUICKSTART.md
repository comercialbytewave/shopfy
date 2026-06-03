# 🚀 Guia de Início Rápido - Primecod Importer

## Pré-requisitos

- Python 3.8+
- PostgreSQL 12+
- pip (gerenciador de pacotes Python)

## Passo 1: Configurar o Banco de Dados

### Criar banco PostgreSQL (Linux/Mac)

```bash
# Criar database
createdb primecod

# Conectar para verificar
psql primecod
```

### Ou no Windows/pgAdmin

1. Abra pgAdmin
2. Clique em "Create" → "Database"
3. Nome: `primecod`
4. Clique em "Save"

## Passo 2: Configurar Variáveis de Ambiente

```bash
# Copiar .env.example para .env
cp .env.example .env

# Editar .env com seus dados
nano .env  # ou use seu editor favorito
```

### Configuração necessária no .env

```env
# Essas já estão preenchidas:
PRIMECOD_API_URL=https://api.primecod.app/api/catalog/products
PRIMECOD_API_TOKEN=369|MrP5nbIaxH6qIXCtnrAeCRkCJO1bxWGqgUMM5BBZ84f76b16
PRIMECOD_API_TOKEN_TYPE=Bearer

# Essas você precisa preencher:
# Exemplo:
DATABASE_URL=postgresql://seu_usuario:sua_senha@localhost:5432/primecod
```

## Passo 3: Instalar Dependências

```bash
# Criar virtual environment
python -m venv venv

# Ativar (Linux/Mac)
source venv/bin/activate

# Ativar (Windows)
venv\Scripts\activate

# Instalar pacotes
pip install -r requirements.txt
```

## Passo 4: Executar o Pipeline

### Opção 1: Rodar tudo de uma vez (recomendado)

```bash
python main.py all
```

### Opção 2: Rodar passo a passo

```bash
# 1. Capturar dados da API
python main.py capture

# 2. Gerar schema automático
python main.py schema

# 3. Criar tabelas no banco
python main.py push

# 4. Importar dados para o banco
python main.py import
```

### Opção 3: Usar o script de inicialização (Linux/Mac)

```bash
chmod +x init.sh
./init.sh
```

## Passo 5: Verificar os Dados

### Conectar ao banco e consultar

```bash
psql primecod

# Ver tabelas
\dt

# Ver primeiros produtos
SELECT id, name, price, stock FROM products LIMIT 5;

# Contar total de produtos
SELECT COUNT(*) FROM products;
```

## Solução de Problemas

### ❌ Erro: `psycopg2.OperationalError`

**Causa**: Não conseguiu conectar ao PostgreSQL

**Solução**:
1. Verificar se PostgreSQL está rodando: `sudo service postgresql status`
2. Verificar DATABASE_URL no .env
3. Testar conexão: `psql primecod -U seu_usuario`

### ❌ Erro: `ModuleNotFoundError: No module named 'requests'`

**Solução**: Instalar dependências novamente
```bash
pip install -r requirements.txt
```

### ❌ Erro: `Prisma Client Python não encontrado`

**Solução**: Gerar o cliente Prisma
```bash
python -m prisma generate --schema prisma/schema.prisma
```

### ❌ Erro: `DATABASE_URL não definido`

**Solução**: Adicionar DATABASE_URL ao arquivo .env

### ❌ A API retorna erro 401 (Unauthorized)

**Solução**: Verificar se o token está correto no .env

## 📊 Resultado Esperado

Após a execução bem-sucedida, você terá:

- ✅ **501 produtos** importados da API
- ✅ Tabela **products** criada no PostgreSQL
- ✅ Campos incluindo: nome, preço, descrição, imagens, categorias, etc.
- ✅ Dados prontos para consulta SQL

### Exemplo de consulta útil

```sql
-- Produtos mais caros
SELECT name, price, cost FROM products ORDER BY price DESC LIMIT 10;

-- Produtos em estoque alto
SELECT name, quantity, stock FROM products WHERE stock = 'High' LIMIT 10;

-- Contagem por categoria
SELECT category_name, COUNT(*) as total FROM products GROUP BY category_name;

-- Produtos com mais de uma imagem
SELECT name, (images ->> 'length')::int as img_count FROM products 
WHERE images IS NOT NULL LIMIT 10;
```

## 🔄 Próximas Execuções

Para importar dados novamente (atualizar):

```bash
python main.py all
```

Os produtos com o mesmo ID serão atualizados (upsert), evitando duplicatas.

## 📝 Arquivos Gerados

Após a execução, você terá:

- `data/products.json` - JSON processado de produtos (501 registros)
- `data/products_raw.json` - Resposta bruta da última página da API
- `prisma/schema.prisma` - Schema gerado automaticamente

## 💡 Dicas

1. **Fazer backup**: Antes de rodar novamente, faça backup do banco
   ```bash
   pg_dump primecod > backup.sql
   ```

2. **Filtrar por país**: Para mudar o país, altere no .env:
   ```env
   PRIMECOD_COUNTRY_CODE=pt  # Portugal em vez de Espanha
   ```

3. **Aumentar página size**: Para capturar mais rápido (máximo 50):
   ```env
   PRIMECOD_PAGE_SIZE=50
   ```

## ✨ Estrutura Final do Projeto

```
primecod/
├── main.py                 # Execute isto: python main.py all
├── .env                    # Suas configurações (NÃO COMPARTILHE)
├── requirements.txt        # Dependências
├── README.md              # Documentação completa
├── QUICKSTART.md          # Este arquivo
├── init.sh                # Script de inicialização
├── prisma/
│   └── schema.prisma      # Schema do banco (gerado)
├── src/
│   ├── config.py          # Carrega .env
│   ├── api_client.py      # Acessa a API
│   ├── schema_generator.py # Gera schema.prisma
│   └── importer.py        # Importa para o banco
├── data/
│   ├── products.json      # Dados processados (gerado)
│   └── products_raw.json  # Dados brutos (gerado)
└── debug/                 # Arquivos de debug (se houver erros)
```

## 🎉 Pronto!

Parabéns! Você tem um importador automático de produtos Primecod funcionando!

Para perguntas ou problemas, consulte o README.md ou veja os logs de erro.

**Bom trabalho! 🚀**
