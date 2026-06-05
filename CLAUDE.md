# Belavion — Guia para Claude

## O que este projeto faz

Pipeline multi-fonte de produtos → banco unificado → Shopify:

**EcomHub** (scraper Playwright) + **Primecod** (REST API)
→ `unified_catalog.products` (PostgreSQL)
→ Flask UI (`integration/`)
→ Shopify Admin GraphQL API

## Estrutura de alto nível

```
belavion/
├── ecomhub/          # Captura EcomHub via Playwright
├── primecod/         # Captura Primecod via REST
├── integration/      # Sync UI + envio para Shopify  ← principal
├── unify_catalog.py  # Unifica os dois JSONs na tabela products
└── unified_catalog.sql
```

Documentação detalhada dos módulos: [`docs/integration.md`](docs/integration.md)

## Fluxo operacional

1. `ecomhub/src/robot.py` → `ecomhub/data/products.json`
2. `primecod/src/api_client.py` → `primecod/data/products.json`
3. `python unify_catalog.py` → popula `unified_catalog.products`
4. `python -m integration` → Flask na porta 5005
   - `/sync` compara catálogo vs Shopify
   - `/send` cria produtos selecionados na Shopify

## Regras de negócio importantes

- **Preço de venda** = custo × 8
- **Preço de comparação** = custo × 10
- **EcomHub multi-variante**: selecionar qualquer SKU do produto cria UM produto Shopify com TODAS as variantes
- **EcomHub**: `productsvariants[].price` é o custo do fornecedor (não preço de venda)
- **EcomHub SKU na Shopify**: sempre `V:{productsVariants[].id}` — nunca `stockItems.sku`
- **Imagens EcomHub**: no banco ficam como `/public/products/featuredImage-XXX.png` → transformar para `{ECOMHUB_CDN_URL}/public/products/featuredImage-XXX__w-800.png`

## Variáveis de ambiente (`integration/.env`)

```
UNIFIED_DATABASE_URL=postgresql://...
SHOPIFY_STORE_DOMAIN=xxxx.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_API_VERSION=2025-10
SHOPIFY_CREATE_STATUS=DRAFT
ECOMHUB_CDN_URL=https://dropstudio360.fra1.digitaloceanspaces.com
PORT=5005
```
