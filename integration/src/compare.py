"""Sincroniza: compara os SKUs do catalogo (tabela unificada) com a Shopify.

Resultado gravado em shopify_sku_status: cada SKU marcado como cadastrado
(in_shopify) ou nao na loja.
"""

from __future__ import annotations

from . import config, db
from .shopify_client import ShopifyClient, ShopifyError


def run_sync(integration: str) -> dict[str, int]:
    if integration not in config.INTEGRATIONS:
        raise ValueError(f"Integracao invalida: {integration!r}. Use uma de {config.INTEGRATIONS}.")

    db.ensure_status_table()
    items = db.read_catalog_skus(integration)

    shopify_index: dict[str, str] = {}
    warning = None
    if config.has_shopify_credentials():
        try:
            shopify_index = ShopifyClient().fetch_all_skus()
        except ShopifyError as exc:
            warning = f"Falha ao consultar a Shopify: {exc}"
    else:
        warning = (
            "Sem credenciais da Shopify (.env): marcando todos como NAO cadastrados. "
            "Preencha SHOPIFY_STORE_DOMAIN e SHOPIFY_ACCESS_TOKEN e sincronize de novo."
        )

    total, present = db.upsert_statuses(integration, items, shopify_index)

    current_skus = [it["sku"] for it in items]
    deleted = db.remove_stale_skus(integration, current_skus)
    if deleted:
        print(f"  [sync] {integration}: {deleted} SKU(s) obsoleto(s) removido(s).")

    if warning:
        print(f"  [aviso] {warning}")
    print(
        f"  [sync] {integration}: {total} SKU(s) no catalogo, "
        f"{present} ja na Shopify, {total - present} faltando."
    )
    return {"total": total, "present": present, "missing": total - present}
