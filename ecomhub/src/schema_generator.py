"""Gera o arquivo prisma/schema.prisma a partir do JSON capturado.

A ideia e inspecionar TODOS os registros capturados, descobrir cada campo,
inferir o tipo Prisma adequado e montar um model "Product" com todos eles.
Campos aninhados (objetos/listas) viram colunas do tipo Json.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from . import config

MODEL_NAME = "Product"
ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)
RESERVED = {"id", "model", "datasource", "generator", "enum", "type"}


class FieldInfo:
    """Acumula o que sabemos sobre um campo ao longo de todos os registros."""

    def __init__(self) -> None:
        self.types: set[str] = set()
        self.nullable: bool = False
        self.seen: int = 0

    def observe(self, value: Any) -> None:
        self.seen += 1
        if value is None:
            self.nullable = True
            return
        self.types.add(_py_to_prisma(value))

    def resolve(self) -> str:
        """Decide o tipo Prisma final do campo."""
        if not self.types:
            return "String"  # so vimos null -> tratamos como String opcional
        if self.types == {"Int"}:
            return "Int"
        if self.types == {"Float"} or self.types == {"Int", "Float"}:
            return "Float"
        if self.types == {"Boolean"}:
            return "Boolean"
        if self.types == {"DateTime"}:
            return "DateTime"
        if self.types == {"Json"}:
            return "Json"
        if "Json" in self.types:
            return "Json"
        # Tipos mistos (ex.: ora numero, ora texto) -> String e mais seguro
        return "String"


def _py_to_prisma(value: Any) -> str:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Int"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, (dict, list)):
        return "Json"
    if isinstance(value, str):
        if ISO_DATE_RE.match(value):
            return "DateTime"
        return "String"
    return "String"


def _sanitize(name: str) -> str:
    """Transforma a chave do JSON num nome de campo Prisma valido."""
    clean = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not clean or not re.match(r"[A-Za-z_]", clean[0]):
        clean = f"f_{clean}"
    return clean


def _load_records() -> list[dict[str, Any]]:
    if not config.PRODUCTS_JSON.exists():
        raise RuntimeError(
            f"Arquivo {config.PRODUCTS_JSON} nao encontrado. "
            f"Rode a captura primeiro (python main.py capture)."
        )
    data = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise RuntimeError("O JSON capturado nao contem uma lista de registros.")
    return [r for r in data if isinstance(r, dict)]


class Column:
    """Descreve uma coluna final do model (chave original -> campo Prisma)."""

    def __init__(self, key: str, field: str, ptype: str, nullable: bool, is_id: bool) -> None:
        self.key = key            # chave original no JSON
        self.field = field        # nome do campo Prisma (saneado)
        self.ptype = ptype        # tipo Prisma (Int, String, Json, ...)
        self.nullable = nullable
        self.is_id = is_id


def analyze() -> tuple[list[Column], bool, int]:
    """Inspeciona o JSON e devolve (colunas, tem_id_natural, total_registros).

    Compartilhado entre a geracao do schema e o importador para garantir que
    os nomes de campo coincidam exatamente.
    """
    records = _load_records()

    fields: dict[str, FieldInfo] = {}
    order: list[str] = []
    for rec in records:
        for key, value in rec.items():
            if key not in fields:
                fields[key] = FieldInfo()
                order.append(key)
            fields[key].observe(value)

    total = len(records)
    for key, info in fields.items():
        if info.seen < total:
            info.nullable = True

    has_natural_id = "id" in fields and not fields["id"].nullable

    columns: list[Column] = []
    name_counts: dict[str, int] = {}
    for key in order:
        info = fields[key]
        field_name = _sanitize(key)
        if field_name in name_counts:
            name_counts[field_name] += 1
            field_name = f"{field_name}_{name_counts[field_name]}"
        else:
            name_counts[field_name] = 0

        is_id = has_natural_id and key == "id"
        nullable = info.nullable and not is_id
        columns.append(Column(key, field_name, info.resolve(), nullable, is_id))

    return columns, has_natural_id, total


def build_schema() -> str:
    columns, has_natural_id, total = analyze()

    lines: list[str] = []
    lines.append("// Arquivo gerado automaticamente por src/schema_generator.py")
    lines.append(f"// Gerado em {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"// Baseado em {total} registro(s) de productsWorkspaces")
    lines.append("")
    lines.append("generator client {")
    lines.append('  provider             = "prisma-client-py"')
    lines.append("  recursive_type_depth = 5")
    lines.append("}")
    lines.append("")
    lines.append("datasource db {")
    lines.append('  provider = "postgresql"')
    lines.append('  url      = env("DATABASE_URL")')
    lines.append("}")
    lines.append("")
    lines.append(f"model {MODEL_NAME} {{")

    # Se nao houver id natural, criamos um id autoincrement interno
    if not has_natural_id:
        lines.append("  pk Int @id @default(autoincrement())")

    for col in columns:
        attrs: list[str] = []
        if col.is_id:
            attrs.append("@id")
        if col.field != col.key:
            attrs.append(f'@map("{col.key}")')

        optional = "?" if col.nullable else ""
        type_str = f"{col.ptype}{optional}"
        attr_str = (" " + " ".join(attrs)) if attrs else ""
        lines.append(f"  {col.field} {type_str}{attr_str}")

    lines.append("")
    lines.append('  @@map("products")')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def run_generate() -> None:
    schema = build_schema()
    config.PRISMA_DIR.mkdir(parents=True, exist_ok=True)
    target = config.PRISMA_DIR / "schema.prisma"
    target.write_text(schema, encoding="utf-8")
    print(f"OK! Schema Prisma gerado em {target}")
    print("\n----- schema.prisma -----")
    print(schema)


if __name__ == "__main__":
    run_generate()
