"""Categorias do Primecod.

Mesmo padrao usado no projeto ecomhub: mantemos uma lista de categorias
({id, name}) em data/categories.json e a importamos para a tabela `Category`
via upsert (sem duplicar).

Fonte: os campos category_id / category_name de cada produto. Fazemos um
group by distinto (sem repeticao) por category_id.
"""

from __future__ import annotations

import json
from typing import Any

from . import config

CATEGORIES_JSON = config.DATA_DIR / "categories.json"

# Modelo Prisma da tabela de categorias. IDENTICO ao do projeto ecomhub para
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


def categories_from_products() -> list[dict[str, str]]:
    """Group by distinto de (category_id, category_name) dos produtos."""
    if not config.PRODUCTS_JSON.exists():
        return []
    records = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        cid = rec.get("category_id")
        if cid is None:
            continue
        out[str(cid)] = {"id": str(cid), "name": str(rec.get("category_name") or "")}
    return list(out.values())


def save_categories(cats: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Salva categorias deduplicadas (por id) em data/categories.json."""
    if cats is None:
        cats = categories_from_products()
    dedup: dict[str, dict[str, str]] = {}
    for cat in cats:
        if isinstance(cat, dict) and cat.get("id") is not None:
            cid = str(cat["id"])
            dedup[cid] = {"id": cid, "name": str(cat.get("name") or "")}
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
        if isinstance(cat, dict) and cat.get("id") is not None:
            cid = str(cat["id"])
            out[cid] = {"id": cid, "name": str(cat.get("name") or "")}
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
