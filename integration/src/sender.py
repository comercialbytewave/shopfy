"""Envia para a Shopify os SKUs marcados pelo usuario (cria produtos)."""

from __future__ import annotations

from . import db
from .shopify_client import ShopifyClient, ShopifyError

_SALE_MULTIPLIER = 8
_COMPARE_MULTIPLIER = 10


def _calc_prices(cost: str | float | None) -> tuple[str | None, str | None]:
    """Retorna (preco_venda, preco_comparacao) a partir do custo.

    preco_venda       = custo * 8
    preco_comparacao  = custo * 10
    """
    if cost is None:
        return None, None
    try:
        c = float(cost)
        if c <= 0:
            return None, None
        return f"{c * _SALE_MULTIPLIER:.2f}", f"{c * _COMPARE_MULTIPLIER:.2f}"
    except (TypeError, ValueError):
        return None, None


def send_skus(integration: str, skus: list[str]) -> dict[str, object]:
    """Cria na Shopify produtos para os SKUs marcados.

    Retorna {'created': [...], 'skipped': [...], 'errors': [{sku, error}]}.
    """
    result: dict[str, object] = {"created": [], "skipped": [], "errors": []}
    if not skus:
        return result

    client = ShopifyClient()

    if integration == "ecomhub":
        _send_ecomhub(client, skus, result)
    else:
        _send_primecod(client, skus, result)

    return result


# --------------------------------------------------------------------------- #
# Primecod: 1 SKU = 1 produto (sem variantes multiplas)
# --------------------------------------------------------------------------- #
def _send_primecod(
    client: ShopifyClient,
    skus: list[str],
    result: dict[str, object],
) -> None:
    for sku in skus:
        st = db.get_status("primecod", sku)
        if st is None:
            result["errors"].append({"sku": sku, "error": "SKU nao encontrado no status."})
            continue
        if st["in_shopify"] or st["sent"]:
            result["skipped"].append(sku)
            continue

        product = db.get_product_by_pk("primecod", st["product_pk"])
        if not product:
            result["errors"].append({"sku": sku, "error": "Produto nao encontrado na tabela unificada."})
            continue

        cost = product.get("cost")
        sale_price, compare_price = _calc_prices(cost)

        try:
            gid = client.create_product(
                title=product.get("name") or sku,
                variants=[{
                    "sku": sku,
                    "price": sale_price,
                    "compare_price": compare_price,
                    "cost": cost,
                    "label": sku,
                }],
                description=product.get("description"),
                image_url=product.get("image"),
            )
            db.mark_sent("primecod", sku, gid)
            result["created"].append({"sku": sku, "shopify_id": gid})
        except ShopifyError as exc:
            result["errors"].append({"sku": sku, "error": str(exc)})


# --------------------------------------------------------------------------- #
# Ecomhub: agrupa variantes por product_pk, cria 1 produto com N variantes
# --------------------------------------------------------------------------- #
def _send_ecomhub(
    client: ShopifyClient,
    skus: list[str],
    result: dict[str, object],
) -> None:
    # Mapear product_pk -> primeiro sku do grupo (para rastreamento de erros)
    groups: dict[int, str] = {}
    for sku in skus:
        st = db.get_status("ecomhub", sku)
        if st is None:
            result["errors"].append({"sku": sku, "error": "SKU nao encontrado no status."})
            continue
        pk = st.get("product_pk")
        if pk is not None:
            groups.setdefault(pk, sku)

    for product_pk, first_sku in groups.items():
        product = db.get_product_by_pk("ecomhub", product_pk)
        if not product:
            result["errors"].append({"sku": first_sku, "error": f"Produto pk={product_pk} nao encontrado."})
            continue

        variants_raw = product.get("variants") or []
        if not variants_raw:
            result["errors"].append({"sku": first_sku, "error": "Produto sem variantes validas."})
            continue

        # Se qualquer variante deste produto ja foi enviada, pula o produto inteiro
        if any(_is_sent("ecomhub", v["sku"]) for v in variants_raw):
            for v in variants_raw:
                result["skipped"].append(v["sku"])
            continue

        # Para ecomhub, o `price` da variante E o custo do fornecedor
        shopify_variants = []
        for v in variants_raw:
            cost = v.get("price")
            sale_price, compare_price = _calc_prices(cost)
            shopify_variants.append({
                "sku": v["sku"],
                "price": sale_price,
                "compare_price": compare_price,
                "cost": cost,
                "label": v.get("label") or v["sku"],
            })

        try:
            gid = client.create_product(
                title=product.get("name") or first_sku,
                variants=shopify_variants,
                description=product.get("description"),
                image_url=product.get("image"),
            )
            db.mark_all_variants_sent("ecomhub", product_pk, gid)
            for v in variants_raw:
                result["created"].append({"sku": v["sku"], "shopify_id": gid})
        except ShopifyError as exc:
            result["errors"].append({"sku": first_sku, "error": str(exc)})


def _is_sent(integration: str, sku: str) -> bool:
    st = db.get_status(integration, sku)
    return bool(st and (st.get("in_shopify") or st.get("sent")))
