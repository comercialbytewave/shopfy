"""Categorias do EcomHub.

Mesmo padrao usado no projeto primecod: mantemos uma lista de categorias
({id, name}) em data/categories.json e a importamos para a tabela `Category`
via upsert (sem duplicar).

Fontes (nesta ordem de preferencia):
  1. A API https://api.ecomhub.app/api/productsCategories, capturada pelo
     robot.py reutilizando a mesma sessao autenticada.
  2. Como reforco, derivamos as categorias do campo
     products_productsCategories de cada produto.
"""

from __future__ import annotations

import json
from typing import Any

from . import config

CATEGORIES_JSON = config.DATA_DIR / "categories.json"

# Modelo Prisma da tabela de categorias. IDENTICO ao do projeto primecod para
# que as duas integracoes sigam exatamente o mesmo padrao.
CATEGORY_MODEL = "\n".join(
    [
        "model Category {",
        "  id   String @id @db.VarChar(250)",
        "  name String @db.VarChar(250)",
        "",
        '  @@map("Category")',
        "}",
    ]
)


def _norm(cat: dict[str, Any]) -> dict[str, str] | None:
    """Normaliza uma categoria para {id, name} (ambos string)."""
    cid = cat.get("id")
    if cid is None:
        return None
    return {"id": str(cid), "name": str(cat.get("name") or "")}


def product_categories(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Retorna a lista de objetos productsCategories de um produto.

    O campo products_productsCategories vem como uma lista de itens no formato
    {"productsCategories": {"id": ..., "name": ...}}. Tambem aceita o caso em
    que o campo foi serializado como string JSON.
    """
    raw = record.get("products_productsCategories")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    cats: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            cat = item.get("productsCategories")
            if isinstance(cat, dict):
                cats.append(cat)
    return cats


def product_category_fields(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """Escolhe a categoria mais especifica (a ultima) do produto.

    Um produto pode ter varias categorias (ex.: ['Saude', 'Suplementos e
    Vitaminas']); usamos a ultima, que e a mais especifica.
    """
    cats = product_categories(record)
    if not cats:
        return None, None
    chosen = cats[-1]
    cid = chosen.get("id")
    name = chosen.get("name")
    return (str(cid) if cid is not None else None,
            str(name) if name is not None else None)


def categories_from_products() -> list[dict[str, str]]:
    """Deriva categorias (deduplicadas) do products_productsCategories."""
    if not config.PRODUCTS_JSON.exists():
        return []
    records = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for cat in product_categories(rec):
            norm = _norm(cat)
            if norm:
                out[norm["id"]] = norm
    return list(out.values())


def save_categories(cats: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Salva categorias deduplicadas (por id) em data/categories.json."""
    if cats is None:
        cats = categories_from_products()
    dedup: dict[str, dict[str, str]] = {}
    for cat in cats:
        norm = _norm(cat) if isinstance(cat, dict) else None
        if norm:
            dedup[norm["id"]] = norm
    result = list(dedup.values())
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    CATEGORIES_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def load_categories() -> list[dict[str, str]]:
    """Le data/categories.json; se nao existir, deriva dos produtos."""
    if not CATEGORIES_JSON.exists():
        return categories_from_products()
    data = json.loads(CATEGORIES_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for cat in data:
        norm = _norm(cat) if isinstance(cat, dict) else None
        if norm:
            out[norm["id"]] = norm
    return list(out.values())


async def import_categories(db: Any) -> int:
    """Upsert das categorias na tabela Category (sem duplicar)."""
    cats = load_categories()
    count = 0
    for cat in cats:
        cid = str(cat["id"])
        name = str(cat.get("name") or "")
        try:
            await db.category.upsert(
                where={"id": cid},
                data={"create": {"id": cid, "name": name}, "update": {"name": name}},
            )
            count += 1
        except Exception as exc:  # pragma: no cover - best effort
            print(f"  [erro] categoria nao importada ({cid}): {exc}")
    return count
