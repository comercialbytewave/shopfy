"""Cliente da Shopify Admin API (GraphQL, versao atual).

Usa o Admin API access token de um app custom (header X-Shopify-Access-Token).
A REST Admin API virou legada em out/2024; por isso usamos GraphQL.

Operacoes disponiveis:
  - check()              : valida as credenciais.
  - fetch_all_skus()     : lista todos os SKUs de variantes ja existentes na loja.
  - create_product()     : cria um produto com variante(s), descricao, imagem e precos.
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
        variants: list[dict[str, Any]],
        description: str | None = None,
        image_url: str | None = None,
        status: str | None = None,
    ) -> str:
        """Cria um produto na Shopify. Retorna o product gid.

        variants: lista de dicts com chaves sku, price, compare_price, cost, label.
          - produtos com 1 variante: usa productVariantsBulkUpdate na variante default.
          - produtos com N variantes: define opcoes + productVariantsBulkCreate
            com strategy REMOVE_STANDALONE_VARIANT.
        """
        status = (status or config.SHOPIFY_CREATE_STATUS or "DRAFT").upper()
        has_multi = len(variants) > 1

        # ---- Passo 1: criar o produto (sem options — API 2026-04+) ---- #
        product_input: dict[str, Any] = {"title": title, "status": status}
        if description:
            product_input["descriptionHtml"] = description

        create = """
        mutation($product: ProductCreateInput!) {
          productCreate(product: $product) {
            product { id variants(first: 1) { nodes { id } } }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(create, {"product": product_input})
        res = data["productCreate"]
        if res["userErrors"]:
            raise ShopifyError(f"productCreate: {res['userErrors']}")
        product_id = res["product"]["id"]
        default_variant_id = res["product"]["variants"]["nodes"][0]["id"]

        # ---- Passo 2: configurar variante(s) ---- #
        if has_multi:
            self._bulk_create_variants(product_id, variants)
        else:
            self._update_single_variant(product_id, default_variant_id, variants[0])

        # ---- Passo 3: anexar imagem ---- #
        if image_url:
            self._attach_image(product_id, image_url)

        return product_id

    def _build_variant_input(self, v: dict[str, Any]) -> dict[str, Any]:
        vi: dict[str, Any] = {"inventoryItem": {"sku": v["sku"]}}
        if v.get("price"):
            vi["price"] = str(v["price"])
        if v.get("compare_price"):
            vi["compareAtPrice"] = str(v["compare_price"])
        if v.get("cost"):
            vi["inventoryItem"]["cost"] = str(v["cost"])
        return vi

    def _update_single_variant(
        self, product_id: str, variant_id: str, v: dict[str, Any]
    ) -> None:
        """Atualiza a variante default (produto com SKU unico)."""
        variant_input = {"id": variant_id, **self._build_variant_input(v)}
        update = """
        mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $productId, variants: $variants) {
            productVariants { id }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(update, {"productId": product_id, "variants": [variant_input]})
        res = data["productVariantsBulkUpdate"]
        if res["userErrors"]:
            raise ShopifyError(f"productVariantsBulkUpdate: {res['userErrors']}")

    def _bulk_create_variants(
        self, product_id: str, variants: list[dict[str, Any]]
    ) -> None:
        """Cria opcoes e variantes para produto multi-variante (API 2026-04+).

        Fluxo separado porque ProductCreateInput nao aceita `options` nessa versao:
          A) productOptionsCreate — define a opcao "Variante" com todos os valores
          B) productVariantsBulkCreate — cria as variantes e remove a standalone default
        """
        # Passo A: criar a opcao com os valores possiveis
        option_values = [{"name": v.get("label") or v["sku"]} for v in variants]
        options_mut = """
        mutation($productId: ID!, $options: [OptionCreateInput!]!) {
          productOptionsCreate(productId: $productId, options: $options) {
            product { options { id name } }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(options_mut, {
            "productId": product_id,
            "options": [{"name": "Variante", "values": option_values}],
        })
        res = data["productOptionsCreate"]
        if res["userErrors"]:
            raise ShopifyError(f"productOptionsCreate: {res['userErrors']}")

        # Passo B: criar as variantes vinculadas a opcao
        variant_inputs = []
        for v in variants:
            vi = self._build_variant_input(v)
            vi["optionValues"] = [
                {"name": v.get("label") or v["sku"], "optionName": "Variante"}
            ]
            variant_inputs.append(vi)

        bulk_create = """
        mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!, $strategy: ProductVariantsBulkCreateStrategy) {
          productVariantsBulkCreate(productId: $productId, variants: $variants, strategy: $strategy) {
            productVariants { id }
            userErrors { field message }
          }
        }
        """
        data = self.graphql(bulk_create, {
            "productId": product_id,
            "variants": variant_inputs,
            "strategy": "REMOVE_STANDALONE_VARIANT",
        })
        res = data["productVariantsBulkCreate"]
        if res["userErrors"]:
            raise ShopifyError(f"productVariantsBulkCreate: {res['userErrors']}")

    def _attach_image(self, product_id: str, image_url: str) -> None:
        """Anexa uma imagem ao produto via productCreateMedia."""
        mutation = """
        mutation($productId: ID!, $media: [CreateMediaInput!]!) {
          productCreateMedia(productId: $productId, media: $media) {
            media { ... on MediaImage { id status } }
            mediaUserErrors { field message }
            product { id }
          }
        }
        """
        data = self.graphql(
            mutation,
            {
                "productId": product_id,
                "media": [{"originalSource": image_url, "mediaContentType": "IMAGE"}],
            },
        )
        errors = (data.get("productCreateMedia") or {}).get("mediaUserErrors", [])
        if errors:
            # Aviso apenas — nao falha o produto por causa da imagem
            print(f"  [aviso] Imagem nao anexada ({image_url}): {errors}")
