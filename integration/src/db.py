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
# Helpers internos
# --------------------------------------------------------------------------- #
def _extract_first_image(images: Any) -> str | None:
    """Extrai o path da primeira imagem do campo images (primecod JSON array).

    Formato: [{"id": 2659, "path": "https://...", "catalog_product_id": 1027}]
    """
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except (TypeError, ValueError):
            return None
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            return first.get("path")
    return None


def _build_image_url(raw: str | None) -> str | None:
    """Constroi URL absoluta para imagens do ecomhub.

    Entrada : /public/products/featuredImage-1742318156191-23565957.png
    Saída   : https://dropstudio360.fra1.digitaloceanspaces.com/public/products/featuredImage-1742318156191-23565957__w-800.png
    """
    if not raw:
        return None
    if raw.startswith("http"):
        return raw
    base = config.ECOMHUB_CDN_URL.rstrip("/")
    # Remove a extensao e adiciona o sufixo __w-800 exigido pelo CDN
    if "." in raw.rsplit("/", 1)[-1]:
        stem, dot, ext = raw.rpartition(".")
        return f"{base}{stem}__w-800.{ext}"
    return f"{base}{raw}"


def _variant_skus(productsvariants: Any) -> list[dict[str, Any]]:
    """Extrai variantes do ecomhub.

    SKU na Shopify segue o padrao  V:{ecomhub_variant_id}
    (ex: V:54368e3a-5c83-4aef-bdf2-0a98e00803aa).
    Isso garante rastreamento correto independente do SKU do fornecedor.

    - sku          : "V:{variant.id}"  — chave usada na Shopify
    - supplier_sku : stockItems.sku    — referencia do fornecedor
    - price        : variante.price    — custo do fornecedor
    - label        : attributes → supplier_sku → id  (exibido como opcao)
    """
    if isinstance(productsvariants, str):
        try:
            productsvariants = json.loads(productsvariants)
        except (TypeError, ValueError):
            return []
    if not isinstance(productsvariants, list):
        return []

    out: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for var in productsvariants:
        if not isinstance(var, dict):
            continue
        variant_id = var.get("id")
        if not variant_id:
            continue

        shopify_sku = f"V:{variant_id}"
        stock = var.get("stockItems") or {}
        supplier_sku = (stock.get("sku") if isinstance(stock, dict) else None) or ""

        raw_label = str(var.get("attributes") or supplier_sku or variant_id).strip()
        # Deduplica labels — Shopify rejeita valores de opcao duplicados
        label = raw_label
        suffix = 1
        while label in seen_labels:
            suffix += 1
            label = f"{raw_label} ({suffix})"
        seen_labels.add(label)

        out.append({
            "sku": shopify_sku,
            "supplier_sku": supplier_sku,
            "price": var.get("price"),  # custo do fornecedor
            "label": label,
        })
    return out


# --------------------------------------------------------------------------- #
# Leitura da tabela unificada -> SKUs do catalogo
# --------------------------------------------------------------------------- #
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
                    continue
                seen.add(sku)
                items.append({**base, "sku": sku, "price": v.get("price")})

    return items


def get_product_by_pk(integration: str, product_pk: int) -> dict[str, Any] | None:
    """Retorna o produto completo (com todas as variantes) para o pk dado.

    Usa as colunas cost, description, image/featuredimage, images da tabela products.
    """
    sql = """
        SELECT pk, id, name, description,
               cost,
               COALESCE(image, featuredimage) AS image_url,
               images,
               productsvariants, sku, price
        FROM products
        WHERE integration = %s AND pk = %s
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration, product_pk))
        row = cur.fetchone()
        if not row:
            return None
        row = dict(row)
        # Tenta image/featuredimage; se null, cai no array images (primecod)
        raw_image = row.get("image_url") or _extract_first_image(row.get("images"))
        image = _build_image_url(raw_image)

        top_sku = row.get("sku")
        if top_sku:
            variants = [{"sku": str(top_sku), "price": row.get("price"), "label": str(top_sku)}]
        else:
            variants = _variant_skus(row.get("productsvariants"))

        return {
            "pk": row["pk"],
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description"),
            "image": image,
            "cost": row.get("cost"),
            "variants": variants,
        }


# --------------------------------------------------------------------------- #
# Traducao de descricao
# --------------------------------------------------------------------------- #
def get_product_description(integration: str, product_id: str) -> dict[str, Any] | None:
    """Retorna a descricao (e a traducao ja salva, se houver) de um produto.

    Usa a chave natural `id` (estavel) em vez de `pk` (serial que muda quando o
    unify_catalog.py reconstroi a tabela products).
    """
    sql = """
        SELECT pk, id, name, description,
               description_translate, language_translate,
               description_upgrade, description_upgrade_translate
        FROM products
        WHERE integration = %s AND id = %s
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration, product_id))
        row = cur.fetchone()
        return dict(row) if row else None


def get_products_text(
    integration: str, product_ids: Iterable[str]
) -> dict[str, dict[str, Any]]:
    """Retorna {id: {description, description_translate, language_translate}}.

    Usado para exibir a descricao e a traducao direto na listagem. Indexado por
    `id` (chave natural estavel), nao por `pk`.
    """
    ids = [pid for pid in {p for p in product_ids} if pid]
    if not ids:
        return {}
    sql = """
        SELECT id, description,
               description_translate, language_translate,
               description_upgrade, description_upgrade_translate
        FROM products
        WHERE integration = %s AND id = ANY(%s)
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sql, (integration, ids))
        return {row["id"]: dict(row) for row in cur.fetchall()}


def save_translation(
    integration: str,
    product_id: str,
    description_translate: str | None,
    language_translate: str,
    description_upgrade_translate: str | None = None,
) -> None:
    """Grava a traducao da descricao (e da descricao melhorada, se houver).

    Chave: id (estavel). `description_upgrade_translate` so e gravado quando o
    produto tem uma descricao melhorada para traduzir.
    """
    sql = """
        UPDATE products
        SET description_translate = %s,
            language_translate = %s,
            description_upgrade_translate = %s
        WHERE integration = %s AND id = %s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                description_translate,
                language_translate,
                description_upgrade_translate,
                integration,
                product_id,
            ),
        )


def save_description_upgrade(
    integration: str, product_id: str, description_upgrade: str
) -> None:
    """Grava a descricao melhorada na coluna products.description_upgrade (chave: id)."""
    sql = """
        UPDATE products
        SET description_upgrade = %s
        WHERE integration = %s AND id = %s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (description_upgrade, integration, product_id))


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
            -- Se o produto foi removido da Shopify, libera para reenvio
            sent               = CASE WHEN EXCLUDED.in_shopify THEN {STATUS_TABLE}.sent        ELSE false END,
            sent_at            = CASE WHEN EXCLUDED.in_shopify THEN {STATUS_TABLE}.sent_at     ELSE NULL  END,
            created_shopify_id = CASE WHEN EXCLUDED.in_shopify THEN {STATUS_TABLE}.created_shopify_id ELSE NULL END,
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
    """Retorna contagens em dois niveis:
    - Por SKU  : cada variante conta separadamente (total, present, missing, sent).
    - Por produto: variantes do mesmo produto_pk contam como 1 (total_p, present_p,
                   missing_p, sent_p). Produto e "present" so se TODAS as variantes
                   estiverem na Shopify.
    """
    sku_sql = f"""
        SELECT
            count(*)                                   AS total,
            count(*) FILTER (WHERE in_shopify)         AS present,
            count(*) FILTER (WHERE NOT in_shopify)     AS missing,
            count(*) FILTER (WHERE sent)               AS sent
        FROM {STATUS_TABLE} WHERE integration = %s
    """
    prod_sql = f"""
        SELECT
            count(*)                                    AS total_p,
            count(*) FILTER (WHERE all_in_shopify)      AS present_p,
            count(*) FILTER (WHERE NOT all_in_shopify)  AS missing_p,
            count(*) FILTER (WHERE any_sent)            AS sent_p
        FROM (
            SELECT
                product_pk,
                bool_and(in_shopify) AS all_in_shopify,
                bool_or(sent)        AS any_sent
            FROM {STATUS_TABLE}
            WHERE integration = %s
            GROUP BY product_pk
        ) sub
    """
    with get_conn() as conn, conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:
        cur.execute(sku_sql, (integration,))
        result = dict(cur.fetchone())
        cur.execute(prod_sql, (integration,))
        result.update(cur.fetchone())
    return result


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


def remove_stale_skus(integration: str, current_skus: list[str]) -> int:
    """Remove da status table SKUs que nao existem mais no catalogo atual.

    Chamado apos upsert_statuses para limpar SKUs obsoletos (ex: mudanca de formato).
    Retorna o numero de linhas removidas.
    """
    if not current_skus:
        return 0
    sql = f"""
        DELETE FROM {STATUS_TABLE}
        WHERE integration = %s
        AND sku != ALL(%s)
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (integration, current_skus))
        return cur.rowcount


def mark_all_variants_sent(integration: str, product_pk: int, shopify_gid: str) -> None:
    """Marca todas as variantes de um product_pk como enviadas."""
    sql = f"""
        UPDATE {STATUS_TABLE}
        SET sent = true, sent_at = now(), selected = false,
            in_shopify = true, created_shopify_id = %s,
            shopify_product_id = COALESCE(shopify_product_id, %s)
        WHERE integration = %s AND product_pk = %s
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (shopify_gid, shopify_gid, integration, product_pk))
