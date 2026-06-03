# integration — catálogo unificado → Shopify

Lê a tabela unificada (`unified_catalog.products`) **por integração** (`ecomhub`
ou `primecod`), compara os SKUs com os já cadastrados na sua loja **Shopify** e
mostra numa interface web quais SKUs **estão** e **não estão** na Shopify. O
usuário marca os que quiser e envia para a loja via API.

## Como funciona o SKU por integração
- **primecod**: SKU vem da coluna `sku` (ex.: `PMLD-322`).
- **ecomhub**: não há SKU no topo — é extraído de
  `productsvariants[].stockItems.sku` (um produto pode ter vários SKUs).

A comparação é **por SKU**. O resultado fica na tabela `shopify_sku_status`
(criada no mesmo banco `unified_catalog`), com `in_shopify`, `sent`, etc.

## Shopify API
Usa a **Admin GraphQL API** (versão atual, configurável em `SHOPIFY_API_VERSION`,
default `2025-10`). A REST Admin API virou legada em out/2024, por isso **não**
usamos o modelo antigo do GitHub (`kamalber/shopify-products-api`, REST 2021-04).

Autenticação por **app custom**: na sua loja → *Settings → Apps and sales
channels → Develop apps → criar app → API credentials → Admin API access token*
(`shpat_...`). Dê os escopos `read_products` e `write_products`.

Ao enviar, cada SKU marcado vira um **produto** na Shopify com **uma variante**
carregando o SKU e o preço. Por padrão é criado como **DRAFT** (rascunho), para
você revisar antes de publicar (mude `SHOPIFY_CREATE_STATUS=ACTIVE` se quiser).

## Setup
```bash
cd integration
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # preencha as credenciais da Shopify
```

## Uso
```bash
# 1) comparar SKUs do catalogo com a Shopify (grava em shopify_sku_status)
python main.py sync ecomhub
python main.py sync primecod      # ou: python main.py sync-all

# 2) interface web para marcar e enviar
python main.py web                # abre http://127.0.0.1:5005

# (opcional) enviar SKUs por linha de comando
python main.py send primecod PMLD-322 PMLD-321
```

Na web: escolha a integração (abas), clique **Sincronizar com a Shopify**,
filtre por **Não cadastrados**, marque os desejados e clique **Enviar
selecionados para a Shopify**.

> Sem credenciais no `.env`, o `sync` ainda roda e marca tudo como “não
> cadastrado” (útil para revisar o catálogo); o envio fica desabilitado.
