"""Acesso ao Postgres: le a tabela unificada e mantem a tabela de comparacao.

A tabela `shopify_sku_status` vive no mesmo banco da tabela unificada
(unified_catalog) e guarda, por SKU/integracao, se ele ja existe na Shopify e
o que ja foi enviado.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

import psycopg2
import psycopg2.extras

from . import config

STATUS_TABLE = "shopify_sku_status"


@contextmanager
def get_conn() -> Iterator["psycopg2.extensions.connection"]:
    conn = psycopg2.connect(**config.db_connect_kwargs())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_status_table() -> None:
    """Cria a tabela de comparacao se ainda nao existir (nao-destrutivo)."""
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {STATUS_TABLE} (
        id                  serial PRIMARY KEY,
        integration         text NOT NULL,
        sku                 text NOT NULL,
        product_pk          integer,
        product_id          text,
        product_name        text,
        price               text,
        in_shopify          boolean NOT NULL DEFAULT false,
        shopify_product_id  text,
        selected            boolean NOT NULL DEFAULT false,
        sent                boolean NOT NULL DEFAULT false,
        sent_at             timestamptz,
        created_shopify_id  text,
        last_checked_at     timestamptz DEFAULT now(),
        UNIQUE (integration, sku)
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(ddl)


# --------------------------------------------------------------------------- #
# Leitura da tabela unificada -> SKUs do catalogo
# --------------------------------------------------------------------------- #
def _variant_skus(productsvariants: Any) -> list[dict[str, Any]]:
    """Extrai (sku, price) de cada variante do ecomhub.

    O campo productsvariants e uma lista de variantes; o SKU fica em
    variante.stockItems.sku e o preco em variante.price.
    """
    if isinstance(productsvariants, str):
        try:
            productsvariants = json.loads(productsvariants)
        except (TypeError, ValueError):
            return []
    if not isinstance(productsvariants, list):
        return []

    out: list[dict[str, Any]] = []
    for var in productsvariants:
        if not isinstance(var, dict):
            continue
        stock = var.get("stockItems") or {}
        sku = stock.get("sku") if isinstance(stock, dict) else None
        if sku:
            out.append({"sku": str(sku), "price": var.get("price")})
    return out


def read_catalog_skus(integration: str) -> list[dict[str, Any]]:
    """Le os produtos da integracao na tabela unificada e devolve uma linha por SKU.

    Cada item: {sku, product_pk, product_id, product_name, price}.
    - primecod: SKU vem da coluna `sku`.
    - ecomhub: SKU(s) vem de productsvariants[].stockItems.sku (1+ por produto).
    """
    sql = """
        SELECT pk, id, name, price, sku, productsvariants
        FROM products
        WHERE integration = %s
    """
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration,))
        for row in cur.fetchall():
            base = {
                "product_pk": row["pk"],
                "product_id": row["id"],
                "product_name": row["name"],
            }
            top_sku = row.get("sku")
            if top_sku:
                variants = [{"sku": str(top_sku), "price": row.get("price")}]
            else:
                variants = _variant_skus(row.get("productsvariants"))

            for v in variants:
                sku = v["sku"]
                if sku in seen:
                    continue  # mesmo SKU repetido entre produtos -> 1 linha so
                seen.add(sku)
                items.append({**base, "sku": sku, "price": v.get("price")})

    return items


# --------------------------------------------------------------------------- #
# Tabela de comparacao
# --------------------------------------------------------------------------- #
def upsert_statuses(
    integration: str,
    items: Iterable[dict[str, Any]],
    shopify_index: dict[str, str],
) -> tuple[int, int]:
    """Insere/atualiza o status de cada SKU. Preserva `selected`/`sent`.

    shopify_index: mapa sku -> shopify_product_id (gid) dos que JA existem na loja.
    Retorna (total, quantos_em_shopify).
    """
    rows = list(items)
    in_shopify_count = 0
    sql = f"""
        INSERT INTO {STATUS_TABLE}
            (integration, sku, product_pk, product_id, product_name, price,
             in_shopify, shopify_product_id, last_checked_at)
        VALUES (%(integration)s, %(sku)s, %(product_pk)s, %(product_id)s,
                %(product_name)s, %(price)s, %(in_shopify)s,
                %(shopify_product_id)s, now())
        ON CONFLICT (integration, sku) DO UPDATE SET
            product_pk         = EXCLUDED.product_pk,
            product_id         = EXCLUDED.product_id,
            product_name       = EXCLUDED.product_name,
            price              = EXCLUDED.price,
            in_shopify         = EXCLUDED.in_shopify,
            shopify_product_id = EXCLUDED.shopify_product_id,
            last_checked_at    = now();
    """
    with get_conn() as conn, conn.cursor() as cur:
        for it in rows:
            gid = shopify_index.get(it["sku"])
            in_shopify = gid is not None
            if in_shopify:
                in_shopify_count += 1
            cur.execute(
                sql,
                {
                    "integration": integration,
                    "sku": it["sku"],
                    "product_pk": it.get("product_pk"),
                    "product_id": it.get("product_id"),
                    "product_name": it.get("product_name"),
                    "price": None if it.get("price") is None else str(it.get("price")),
                    "in_shopify": in_shopify,
                    "shopify_product_id": gid,
                },
            )
    return len(rows), in_shopify_count


def fetch_statuses(integration: str, only: str | None = None) -> list[dict[str, Any]]:
    """Lista o status. only: None=todos, 'missing'=nao cadastrados, 'present'=cadastrados."""
    clause = ""
    if only == "missing":
        clause = "AND in_shopify = false"
    elif only == "present":
        clause = "AND in_shopify = true"
    sql = f"""
        SELECT * FROM {STATUS_TABLE}
        WHERE integration = %s {clause}
        ORDER BY in_shopify ASC, sent ASC, product_name ASC
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration,))
        return [dict(r) for r in cur.fetchall()]


def counts(integration: str) -> dict[str, int]:
    sql = f"""
        SELECT
            count(*)                                   AS total,
            count(*) FILTER (WHERE in_shopify)         AS present,
            count(*) FILTER (WHERE NOT in_shopify)     AS missing,
            count(*) FILTER (WHERE sent)               AS sent
        FROM {STATUS_TABLE} WHERE integration = %s
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration,))
        return dict(cur.fetchone())


def get_status(integration: str, sku: str) -> dict[str, Any] | None:
    sql = f"SELECT * FROM {STATUS_TABLE} WHERE integration = %s AND sku = %s"
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration, sku))
        row = cur.fetchone()
        return dict(row) if row else None


def mark_sent(integration: str, sku: str, created_shopify_id: str) -> None:
    sql = f"""
        UPDATE {STATUS_TABLE}
        SET sent = true, sent_at = now(), selected = false,
            in_shopify = true, created_shopify_id = %s,
            shopify_product_id = COALESCE(shopify_product_id, %s)
        WHERE integration = %s AND sku = %s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (created_shopify_id, created_shopify_id, integration, sku))
