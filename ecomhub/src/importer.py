"""Importa o JSON capturado para o PostgreSQL usando o Prisma Client Python.

Pre-requisitos (feitos pelo main.py):
  1. O schema ja foi gerado (src/schema_generator).
  2. `prisma db push` criou as tabelas no banco.
  3. `prisma generate` gerou o client Python.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from . import config
from .categories import import_categories, product_category_fields
from .schema_generator import Column, analyze


def _coerce(value: Any, ptype: str) -> Any:
    """Converte o valor do JSON para o tipo que o Prisma Client espera."""
    if value is None:
        return None

    if ptype == "DateTime" and isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None  # nao conseguimos converter -> grava nulo

    if ptype == "Json":
        from prisma import Json

        return Json(value)

    if ptype == "Int" and isinstance(value, bool):
        return int(value)

    if ptype == "String" and not isinstance(value, str):
        # tipos mistos foram normalizados para String no schema
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)

    return value


def _build_payload(record: dict[str, Any], columns: list[Column]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for col in columns:
        if col.key not in record:
            continue
        coerced = _coerce(record[col.key], col.ptype)
        if coerced is None and col.nullable:
            payload[col.field] = None
        elif coerced is not None:
            payload[col.field] = coerced
    return payload


async def _import() -> int:
    if not config.PRODUCTS_JSON.exists():
        raise RuntimeError(
            f"{config.PRODUCTS_JSON} nao encontrado. Rode a captura primeiro."
        )

    records = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise RuntimeError("JSON capturado nao e uma lista de registros.")

    columns, has_natural_id, _ = analyze()

    try:
        from prisma import Prisma
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Prisma Client Python nao encontrado/gerado. "
            "Rode `python -m prisma generate` antes de importar."
        ) from exc

    db = Prisma()
    await db.connect()
    inserted = 0
    errors = 0
    try:
        for record in records:
            if not isinstance(record, dict):
                continue
            # Deriva category_id/category_name de products_productsCategories.
            cat_id, cat_name = product_category_fields(record)
            record["category_id"] = cat_id
            record["category_name"] = cat_name
            payload = _build_payload(record, columns)
            try:
                if has_natural_id and "id" in record and record["id"] is not None:
                    # upsert para nao duplicar em reimportacoes
                    id_col = next(c for c in columns if c.is_id)
                    id_value = _coerce(record["id"], id_col.ptype)
                    await db.product.upsert(
                        where={"id": id_value},
                        data={"create": payload, "update": payload},
                    )
                else:
                    await db.product.create(data=payload)
                inserted += 1
            except Exception as exc:
                errors += 1
                if errors <= 5:
                    print(f"  [erro] registro nao importado: {exc}")

        # Importa as categorias na tabela Category (sem duplicar).
        cat_count = await import_categories(db)
        print(f"  {cat_count} categoria(s) na tabela 'Category'.")
    finally:
        await db.disconnect()

    if errors:
        print(f"  [aviso] {errors} registro(s) falharam na importacao.")
    return inserted


def run_import() -> None:
    count = asyncio.run(_import())
    print(f"OK! {count} produto(s) gravado(s) na tabela 'products'.")


if __name__ == "__main__":
    run_import()
