# 🔧 Guia de Instalação Detalhado

## Pré-requisitos

### 1. Python 3.8+

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.8-venv python3-pip
python3 --version
```

**Mac:**
```bash
brew install python@3.9
python3 --version
```

**Windows:**
- Baixe em https://www.python.org/downloads/
- Instale e marque "Add Python to PATH"

### 2. PostgreSQL 12+

**Linux (Ubuntu/Debian):**
```bash
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

**Mac:**
```bash
brew install postgresql
brew services start postgresql
```

**Windows:**
- Baixe em https://www.postgresql.org/download/
- Instale com pgAdmin incluído

## Passo 1: Preparar o Banco

### Criar database e usuário

**Linux/Mac:**
```bash
# Conectar como admin
sudo -u postgres psql

# Dentro do psql:
CREATE DATABASE primecod;
CREATE USER primecod_user WITH PASSWORD 'sua_senha_forte';
GRANT ALL PRIVILEGES ON DATABASE primecod TO primecod_user;
\q
```

**Verificar:**
```bash
psql -U primecod_user -d primecod -c "SELECT 1;"
```

**Windows (pgAdmin):**
1. Abra pgAdmin
2. Login com credenciais
3. Clique em "Servers" → "PostgreSQL" → "Databases"
4. Clique direito → "Create" → "Database"
5. Nome: `primecod`
6. Create!

## Passo 2: Clonar ou Preparar o Projeto

```bash
# Se o projeto já foi criado, entre nele
cd /home/ricarte/Documentos/Projetos\ ByteWave/shopfy/primecod

# Verificar estrutura
ls -la
```

Estrutura esperada:
```
main.py
requirements.txt
.env
.env.example
README.md
src/
prisma/
data/
```

## Passo 3: Configurar o Arquivo .env

### Copiar template
```bash
cp .env.example .env
```

### Editar .env
```bash
# Linux/Mac
nano .env

# Windows (abrir em qualquer editor)
```

### Preencher as variáveis

```env
# ✅ Essas já estão preenchidas com o token correto:
PRIMECOD_API_URL=https://api.primecod.app/api/catalog/products
PRIMECOD_API_TOKEN=369|MrP5nbIaxH6qIXCtnrAeCRkCJO1bxWGqgUMM5BBZ84f76b16
PRIMECOD_API_TOKEN_TYPE=Bearer
PRIMECOD_COUNTRY_CODE=es

# ⚠️ VOCÊ PRECISA PREENCHER ISTO:
# Formato: postgresql://usuario:senha@host:porta/database
DATABASE_URL=postgresql://primecod_user:sua_senha_forte@localhost:5432/primecod
```

**Exemplo prático:**
```env
DATABASE_URL=postgresql://primecod_user:MinhaSenh@123@localhost:5432/primecod
```

## Passo 4: Criar e Ativar Virtual Environment

### Criar venv

**Linux/Mac:**
```bash
python3 -m venv venv
```

**Windows:**
```cmd
python -m venv venv
```

### Ativar venv

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

Deve aparecer `(venv)` no início do terminal.

## Passo 5: Instalar Dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Aguarde enquanto instala:
- ✓ python-dotenv
- ✓ prisma
- ✓ requests

## Passo 6: Validar Instalação

```bash
python verify.py
```

Deve mostrar:
```
✓ Python 3.x.x
✓ Arquivo .env
✓ Dependências Python
✓ Diretórios
✓ Arquivos Python
✓ API Primecod (conectada)
✓ Banco PostgreSQL

✅ Tudo pronto! Execute: python main.py all
```

Se houver erros ❌:
1. Leia a mensagem de erro
2. Corrija o problema
3. Execute `python verify.py` novamente

## Passo 7: Executar o Pipeline

### Opção A: Tudo de uma vez

```bash
python main.py all
```

### Opção B: Passo a passo

```bash
# 1. Capturar
python main.py capture

# 2. Gerar schema
python main.py schema

# 3. Criar tabelas
python main.py push

# 4. Importar
python main.py import
```

### Saída esperada

```
=== ETAPA 1: CAPTURA DA API ===
[1/4] Capturando produtos da API Primecod...
  [api] Total de paginas: 42
  [api] Pagina 1/42: 12 produto(s)
  [api] Pagina 2/42: 12 produto(s)
  ...
  [api] Pagina 42/42: 9 produto(s)
OK! 501 produto(s) capturado(s)

=== ETAPA 2: GERAR SCHEMA PRISMA ===
OK! Schema gerado com 47 campo(s)

=== ETAPA 3: CRIAR TABELAS ===
[Database] ✓ Completed in 123ms
✔ Prisma Client Python generated

=== ETAPA 4: IMPORTAR PARA O BANCO ===
OK! 501 produto(s) gravado(s) na tabela 'products'.

>>> Pipeline completa com sucesso!
```

## Passo 8: Verificar os Dados

### Conectar ao banco

```bash
psql -U primecod_user -d primecod
```

### Consultas de verificação

```sql
-- Ver quantos produtos foram importados
SELECT COUNT(*) FROM products;

-- Ver alguns produtos
SELECT id, name, price, stock FROM products LIMIT 5;

-- Ver tabela de estrutura
\d products

-- Sair
\q
```

## Troubleshooting

### ❌ Erro: psql: command not found

**Solução:**
```bash
# Linux
sudo apt install postgresql-client

# Mac
brew install postgresql
```

### ❌ Erro: FATAL: database "primecod" does not exist

**Solução:**
```bash
# Criar database
createdb primecod

# Ou via psql
psql -U postgres -c "CREATE DATABASE primecod;"
```

### ❌ Erro: role "primecod_user" does not exist

**Solução:**
```bash
psql -U postgres

-- Dentro do psql:
CREATE USER primecod_user WITH PASSWORD 'senha';
GRANT ALL PRIVILEGES ON DATABASE primecod TO primecod_user;
\q
```

### ❌ Erro: connection refused (server refused our connection attempt)

**Solução:**
```bash
# Verificar se PostgreSQL está rodando
sudo service postgresql status

# Se não, inicie
sudo service postgresql start

# Mac
brew services start postgresql
```

### ❌ Erro: module 'requests' has no attribute 'get'

**Solução:**
```bash
# Reinstalar pacotes
pip install --upgrade -r requirements.txt
```

### ❌ Erro: ModuleNotFoundError: No module named 'dotenv'

**Solução:**
```bash
# Verificar se venv está ativado
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Reinstalar
pip install -r requirements.txt
```

## ✅ Checklist de Conclusão

- [ ] Python 3.8+ instalado
- [ ] PostgreSQL rodando
- [ ] Database `primecod` criada
- [ ] `.env` preenchido com DATABASE_URL correto
- [ ] Virtual environment criado
- [ ] Virtual environment ativado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] `python verify.py` passou em todos os testes
- [ ] `python main.py all` executou com sucesso
- [ ] `psql primecod -c "SELECT COUNT(*) FROM products;"` retorna 501

## 🎉 Pronto!

Se tudo acima foi completado com sucesso, você tem um importador Primecod totalmente funcional!

### Próximas etapas:

1. **Explorar dados**: Veja [EXAMPLES.md](EXAMPLES.md)
2. **Integrar**: Use os dados em sua aplicação
3. **Automatizar**: Configure cron job usando [sync.sh](sync.sh)
4. **Monitorar**: Acompanhe os logs

---

**Precisa de ajuda?** Consulte:
- [README.md](README.md) - Documentação completa
- [QUICKSTART.md](QUICKSTART.md) - Início rápido
- [EXAMPLES.md](EXAMPLES.md) - Exemplos práticos
