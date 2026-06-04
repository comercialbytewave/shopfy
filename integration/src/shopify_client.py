"""Cliente da Shopify Admin API (GraphQL, versao atual).

Usa o Admin API access token de um app custom (header X-Shopify-Access-Token).
A REST Admin API virou legada em out/2024; por isso usamos GraphQL.

Faz duas coisas:
  - fetch_all_skus(): lista todos os SKUs de variantes ja existentes na loja.
  - create_product(): cria um produto com uma variante carregando o SKU/preco.
"""

from __future__ import annotations

from typing import Any

import requests

from . import config


class ShopifyError(RuntimeError):
    pass


class ShopifyClient:
    def __init__(
        self,
        domain: str | None = None,
        token: str | None = None,
        version: str | None = None,
    ) -> None:
        self.domain = (domain or config.SHOPIFY_STORE_DOMAIN).strip()
        self.token = (token or config.SHOPIFY_ACCESS_TOKEN).strip()
        self.version = (version or config.SHOPIFY_API_VERSION).strip()
        if not self.domain or not self.token:
            raise ShopifyError(
                "Credenciais da Shopify ausentes. Preencha SHOPIFY_STORE_DOMAIN e "
                "SHOPIFY_ACCESS_TOKEN no .env."
            )
        self.endpoint = f"https://{self.domain}/admin/api/{self.version}/graphql.json"

    # --------------------------------------------------------------------- #
    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = requests.post(
            self.endpoint,
            json={"query": query, "variables": variables or {}},
            headers={
                "X-Shopify-Access-Token": self.token,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise ShopifyError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        if payload.get("errors"):
            raise ShopifyError(f"GraphQL errors: {payload['errors']}")
        return payload["data"]

    # --------------------------------------------------------------------- #
    def check(self) -> dict[str, Any]:
        """Valida as credenciais com uma consulta minima. Levanta ShopifyError se invalidas."""
        data = self.graphql("{ shop { name myshopifyDomain } }")
        return data["shop"]

    # --------------------------------------------------------------------- #
    def fetch_all_skus(self) -> dict[str, str]:
        """Devolve um mapa {sku: product_gid} de todas as variantes da loja."""
        query = """
        query($cursor: String) {
          productVariants(first: 250, after: $cursor) {
            nodes { sku product { id } }
            pageInfo { hasNextPage endCursor }
          }
        }
        """
        index: dict[str, str] = {}
        cursor: str | None = None
        while True:
            data = self.graphql(query, {"cursor": cursor})
            block = data["productVariants"]
            for node in block["nodes"]:
                sku = (node.get("sku") or "").strip()
                if sku:
                    prod = node.get("product") or {}
                    index[sku] = prod.get("id", "")
            page = block["pageInfo"]
            if not page["hasNextPage"]:
                break
            cursor = page["endCursor"]
        return index

    # --------------------------------------------------------------------- #
    def create_product(
        self,
        title: str,
        sku: str,
        price: str | None = None,
        status: str | None = None,
    ) -> str:
        """Cria um produto com 1 variante (SKU + preco). Retorna o product gid.

        Fluxo atual da Admin API:
          1) productCreate cria o produto + a variante default.
          2) productVariantsBulkUpdate seta SKU (em inventoryItem) e preco.
        """
        status = (status or config.SHOPIFY_CREATE_STATUS or "DRAFT").upper()

        create = """
        mutation($product: ProductCreateInput!) {
          productCreate(product: $product) {
            product { id variants(first: 1) { nodes { id } } }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(create, {"product": {"title": title, "status": status}})
        res = data["productCreate"]
        if res["userErrors"]:
            raise ShopifyError(f"productCreate: {res['userErrors']}")
        product = res["product"]
        product_id = product["id"]
        variant_id = product["variants"]["nodes"][0]["id"]

        variant_input: dict[str, Any] = {
            "id": variant_id,
            "inventoryItem": {"sku": sku},
        }
        if price is not None and str(price).strip() != "":
            variant_input["price"] = str(price)

        update = """
        mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants { id }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(
            update, {"productId": product_id, "variants": [variant_input]}
        )
        res = data["productVariantsBulkUpdate"]
        if res["userErrors"]:
            raise ShopifyError(f"productVariantsBulkUpdate: {res['userErrors']}")
        return product_id
