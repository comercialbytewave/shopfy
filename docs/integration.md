# Módulos de Integração (`integration/src/`)

## Mapa de responsabilidades

| Arquivo | Responsabilidade |
|---------|-----------------|
| `config.py` | Lê `.env`: credenciais Shopify, DB URL, ECOMHUB_BASE_URL, PORT |
| `db.py` | Lê `products`, gerencia `shopify_sku_status` |
| `compare.py` | Compara SKUs do catálogo vs Shopify → atualiza status |
| `shopify_client.py` | Cliente GraphQL: fetch SKUs, criar produtos |
| `sender.py` | Orquestra criação de produtos com cálculo de preços |
| `web.py` | Flask: rotas `/`, `/sync`, `/send` |

---

## Banco de dados

### Tabela `products` (unified_catalog)

Colunas relevantes para integração:

| Coluna | Tipo | Fonte |
|--------|------|-------|
| `pk` | int | PK interna |
| `integration` | text | `"ecomhub"` ou `"primecod"` |
| `name` | text | nome do produto |
| `description` | text | descrição HTML |
| `sku` | text | SKU direto (primecod); null para ecomhub |
| `price` | text | preço (primecod); null para ecomhub |
| `cost` | text | custo (primecod); null para ecomhub |
| `image` | text | URL da imagem (primecod) |
| `featuredimage` | text | URL relativa da imagem (ecomhub): `/public/products/XXX.png` |
| `productsvariants` | jsonb | variantes (ecomhub); null para primecod |

**EcomHub**: sku/price/cost ficam null no produto raiz — vivem dentro de `productsvariants`.
Imagem: `featuredimage` é path relativo → `_build_image_url()` transforma em `{ECOMHUB_CDN_URL}/public/products/XXX__w-800.png` (DigitalOcean Spaces).
**Primecod**: todos os campos são colunas diretas; imagem vem de `images` (JSON array: `[{path: "https://..."}]`) — coluna `image` pode ser null. `get_product_by_pk` usa `COALESCE(image, featuredimage)` e cai em `images[0].path` se ainda null.

### Estrutura `productsvariants` (EcomHub)

```json
[
  {
    "id": "54368e3a-5c83-4aef-bdf2-0a98e00803aa",  // variant UUID → SKU Shopify = "V:{id}"
    "price": "3.70",                                 // custo do fornecedor
    "attributes": "PRETO FOSCO",                    // label da variante (opção Shopify)
    "isRemoved": false,
    "stockItems": {
      "sku": "masajeled_15477",                     // SKU do fornecedor (referência apenas)
      "featuredImage": "/public/products/..."
    }
  }
]
```

**Convenção de SKU na Shopify para EcomHub:** `V:{productsVariants[].id}`
- Garante rastreamento único independente de mudanças no SKU do fornecedor
- `fetch_all_skus()` retorna `{"V:54368e3a-...": "gid://shopify/Product/..."}` → match correto
- `stockItems.sku` fica em `supplier_sku` (campo auxiliar, não usado como chave)

### Tabela `shopify_sku_status`

Chave única: `(integration, sku)`. Campos principais:
`product_pk`, `product_name`, `price`, `in_shopify`, `sent`, `created_shopify_id`, `shopify_product_id`

---

## db.py — funções-chave

```python
read_catalog_skus(integration)       # → [{sku, product_pk, product_name, price}]
get_product_by_pk(integration, pk)   # → {name, description, image, cost, variants[]}
upsert_statuses(integration, items, shopify_index)
get_status(integration, sku)         # → dict da linha na status table
mark_sent(integration, sku, gid)     # marca 1 SKU como enviado
mark_all_variants_sent(integration, product_pk, gid)  # marca todas variantes do produto
```

`get_product_by_pk` faz `COALESCE(image, featuredimage)` e converte URL relativa em absoluta via `_build_image_url()`.

---

## shopify_client.py — fluxo de criação

```python
client.create_product(
    title="...",
    variants=[{sku, price, compare_price, cost, label}],
    description="...",   # vai para descriptionHtml
    image_url="...",
)
```

**1 variante** (primecod):
1. `productCreate` (title, descriptionHtml, status)
2. `productVariantsBulkUpdate` → seta sku, price, compareAtPrice, inventoryItem.cost
3. `productCreateMedia` → imagem (falha silenciosa)

**N variantes** (ecomhub) — API 2026-04+, `options` saiu do `ProductCreateInput`:
1. `productCreate` (só title, descriptionHtml, status)
2. `productOptionsCreate` → cria a opção "Variante" com os valores possíveis
3. `productVariantsBulkCreate` com `strategy: REMOVE_STANDALONE_VARIANT`
   - cada variante: `optionValues [{name, optionName}]`, `inventoryItem.sku`, `price`, `compareAtPrice`, `inventoryItem.cost`
4. `productCreateMedia` → imagem

---

## sender.py — lógica de envio

**Primecod** (`_send_primecod`):
- 1 SKU → busca produto via `get_product_by_pk` → calcula preços → `create_product`

**EcomHub** (`_send_ecomhub`):
- Agrupa SKUs selecionados por `product_pk`
- Para cada grupo: busca produto completo → verifica se já enviado → cria 1 produto com todas as variantes → `mark_all_variants_sent`

Cálculo de preços:
```python
sale_price    = custo × 8
compare_price = custo × 10
```
