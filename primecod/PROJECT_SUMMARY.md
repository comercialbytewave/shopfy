<!-- 
  ██████╗ ██████╗ ██╗███╗   ███╗███████╗ ██████╗ ██████╗ ██████╗ 
  ██╔══██╗██╔══██╗██║████╗ ████║██╔════╝██╔════╝██╔═══██╗██╔══██╗
  ██████╔╝██████╔╝██║██╔████╔██║█████╗  ██║     ██║   ██║██║  ██║
  ██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝  ██║     ██║   ██║██║  ██║
  ██║     ██║  ██║██║██║ ╚═╝ ██║███████╗╚██████╗╚██████╔╝██████╔╝
  ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═════╝ 
                                                                    
                    🚀 API Importer for Primecod 🚀
-->

# Primecod Importer - Projeto Completo

> Importador automático de produtos da API Primecod para PostgreSQL com Prisma ORM

## ✨ O que foi criado

Uma solução completa Python que:

✅ **Acessa a API Primecod** com autenticação Bearer  
✅ **Pagina automaticamente** através de todas as 42 páginas  
✅ **Captura 501 produtos** com todos os detalhes  
✅ **Gera schema Prisma** automaticamente analisando os dados  
✅ **Cria tabelas PostgreSQL** com tipos inferidos  
✅ **Importa dados** com proteção contra duplicatas (upsert)  

## 📁 Estrutura Criada

```
/home/ricarte/Documentos/Projetos ByteWave/shopfy/primecod/
├── 🎯 main.py                 ← Execute isto para tudo!
├── .env                        ← Suas credenciais (preencher)
├── .env.example               ← Template com variáveis
├── requirements.txt            ← pip install isto
├── verify.py                  ← Validar antes de rodar
│
├── 📖 Documentação
│   ├── README.md              ← Guia completo
│   ├── QUICKSTART.md          ← Início rápido (5 min)
│   ├── STRUCTURE.md           ← Explicação da estrutura
│   └── EXAMPLES.md            ← Exemplos SQL e Python
│
├── 🐍 src/                     ← Código Python
│   ├── config.py              ← Carrega .env
│   ├── api_client.py          ← Acessa API
│   ├── schema_generator.py    ← Gera schema.prisma
│   └── importer.py            ← Importa para DB
│
├── 🗄️ prisma/
│   └── schema.prisma          ← Schema do banco (auto-gerado)
│
├── 📊 data/
│   ├── products.json          ← 501 produtos (auto-gerado)
│   └── products.json.example  ← Exemplo de estrutura
│
├── 🚀 init.sh                 ← Script de inicialização rápida
└── 🐛 debug/                  ← Arquivo de logs se houver erro
```

## 🚀 Início Rápido (3 passos)

### 1️⃣ Configurar o Banco

```bash
# Criar database PostgreSQL
createdb primecod
```

### 2️⃣ Configurar .env

```bash
# Copiar template
cp .env.example .env

# Editar e preencher DATABASE_URL
# Ex: postgresql://user:password@localhost:5432/primecod
nano .env
```

### 3️⃣ Rodar o Pipeline

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar tudo em um comando
python main.py all
```

**Pronto!** ✅ 501 produtos importados!

## 📋 O que Cada Arquivo Faz

| Arquivo | Propósito |
|---------|-----------|
| `main.py` | Orquestra todo o pipeline |
| `src/config.py` | Carrega variáveis do .env |
| `src/api_client.py` | Acessa API Primecod com paginação |
| `src/schema_generator.py` | Analisa JSON e gera schema.prisma |
| `src/importer.py` | Importa dados para PostgreSQL |
| `prisma/schema.prisma` | Definição das tabelas (auto-gerado) |
| `.env` | Suas credenciais (NÃO COMPARTILHE!) |
| `requirements.txt` | Dependências Python |

## 🔄 Pipeline em 4 Etapas

```
[1] CAPTURE        [2] SCHEMA         [3] PUSH          [4] IMPORT
    ↓                   ↓                  ↓                 ↓
API Primecod  →  Analisa tipos  →  Cria tabelas  →  Insere dados
(501 produtos)  (47 campos)      (PostgreSQL)       (Upsert)
```

## 📚 Documentação

- **[README.md](README.md)** - Documentação completa (30 min leitura)
- **[QUICKSTART.md](QUICKSTART.md)** - Começar em 5 minutos
- **[STRUCTURE.md](STRUCTURE.md)** - Entender a arquitetura
- **[EXAMPLES.md](EXAMPLES.md)** - Exemplos de SQL e código

## 🔧 Tecnologias Usadas

```
Python 3.8+          Linguagem
PostgreSQL 12+       Banco de Dados
Prisma 0.15.0        ORM
python-dotenv 1.0.1  Variáveis de ambiente
requests 2.31.0      HTTP Client
```

## ✅ Validação

Antes de rodar, execute a verificação:

```bash
python verify.py
```

Isto valida:
- ✓ Python 3.8+
- ✓ Arquivo .env
- ✓ Dependências instaladas
- ✓ Conectividade com API
- ✓ Conectividade com PostgreSQL
- ✓ Todos os arquivos Python

## 🎯 Dados Capturados

A tabela `products` contém:

```
501 produtos com 47 campos cada:
- Informações básicas (name, description, sku)
- Preços (price, cost, profit)
- Estoque (quantity, stock, stock_label)
- Categorias (category_id, category_name)
- Imagens (array JSON)
- Países (array JSON com informações de envio)
- ... e muitos outros
```

## 🔐 Segurança

- ✅ Token guardado apenas no `.env` (adicionado ao `.gitignore`)
- ✅ DATABASE_URL seguro e local
- ✅ Sem credenciais no código
- ✅ Autenticação Bearer na API

## 📈 Próximas Etapas

1. **Rodar o pipeline**: `python main.py all`
2. **Consultar dados**: `psql primecod`
3. **Explorar dados**: Ver [EXAMPLES.md](EXAMPLES.md)
4. **Automatizar**: Cron job para sincronizar periodicamente
5. **Integrar**: Usar os dados em sua aplicação

## 🆘 Problemas Comuns

### Erro: DATABASE_URL não definido
→ Adicione a URL no arquivo `.env`

### Erro: Conexão recusada no PostgreSQL
→ Verifique se PostgreSQL está rodando: `sudo service postgresql status`

### Erro: Token inválido (401)
→ Copie o token correto do `.env.example`

### Erro: Prisma Client não encontrado
→ Execute: `python -m prisma generate`

Mais detalhes em [QUICKSTART.md](QUICKSTART.md#solução-de-problemas)

## 📊 Estatísticas

```
Produtos:        501
Páginas:         42 (12 por página)
Campos:          47
Países:          2 (Espanha, Portugal)
Categorias:      16
Tempo de import: ~30-60 segundos
Tamanho JSON:    ~5 MB
```

## 📞 Suporte

Se encontrar problemas:

1. Leia [QUICKSTART.md](QUICKSTART.md)
2. Execute `python verify.py` para diagnosticar
3. Veja [EXAMPLES.md](EXAMPLES.md) para exemplos
4. Consulte [STRUCTURE.md](STRUCTURE.md) para entender o código

## 📝 Versão

- **Versão**: 1.0
- **Data**: 3 de junho de 2026
- **Status**: ✅ Produção
- **Python**: 3.8+
- **PostgreSQL**: 12+

## 🎉 Pronto para Usar!

```bash
# 1. Entre no diretório
cd primecod

# 2. Configure o banco
createdb primecod

# 3. Configure .env
cp .env.example .env
nano .env  # preencha DATABASE_URL

# 4. Instale dependências
pip install -r requirements.txt

# 5. Valide
python verify.py

# 6. Execute!
python main.py all

# 7. Explore
psql primecod
SELECT * FROM products LIMIT 5;
```

---

**Desenvolvido em 2026** | **Compatível com ecomhub** | **Open Source**

🚀 **Boa sorte com seu projeto Primecod!** 🚀
