"""Envia para a Shopify os SKUs marcados pelo usuario (cria produtos)."""

from __future__ import annotations

from . import db
from .shopify_client import ShopifyClient, ShopifyError


def send_skus(integration: str, skus: list[str]) -> dict[str, object]:
    """Cria na Shopify um produto por SKU marcado (que ainda nao exista la).

    Retorna {'created': [...], 'skipped': [...], 'errors': [{sku, error}]}.
    """
    result: dict[str, object] = {"created": [], "skipped": [], "errors": []}
    if not skus:
        return result

    client = ShopifyClient()  # levanta ShopifyError se faltar credencial

    for sku in skus:
        st = db.get_status(integration, sku)
        if st is None:
            result["errors"].append({"sku": sku, "error": "SKU nao encontrado no status."})
            continue
        if st["in_shopify"] or st["sent"]:
            result["skipped"].append(sku)  # ja existe / ja enviado
            continue

        title = st.get("product_name") or sku
        price = st.get("price")
        try:
            gid = client.create_product(title=title, sku=sku, price=price)
            db.mark_sent(integration, sku, gid)
            result["created"].append({"sku": sku, "shopify_id": gid})
        except ShopifyError as exc:
            result["errors"].append({"sku": sku, "error": str(exc)})

    return result
