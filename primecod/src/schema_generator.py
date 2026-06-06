"""Gera o schema Prisma a partir da analise do JSON de produtos.

Le o JSON capturado e infere os tipos de dados para cada campo,
gerando um arquivo schema.prisma otimizado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from . import config
from .categories import CATEGORY_MODEL


@dataclass
class Column:
    """Representa uma coluna da tabela."""
    key: str           # chave no JSON
    field: str         # nome do campo no Prisma (snake_case)
    ptype: str         # tipo Prisma (String, Int, Boolean, DateTime, Json, etc.)
    nullable: bool     # pode ser nulo?
    is_id: bool = False


def _infer_type(value: Any, path: str = "") -> str:
    """Infere o tipo Prisma para um valor."""
    if value is None:
        return "String"  # tipo padrao para nulos
    
    if isinstance(value, bool):
        return "Boolean"
    
    if isinstance(value, int):
        return "Int"
    
    if isinstance(value, float):
        return "Float"
    
    if isinstance(value, str):
        # Tenta detectar datas ISO
        if "date" in path.lower() or "created" in path.lower() or "updated" in path.lower():
            if "T" in value or "-" in value:
                return "DateTime"
        return "String"
    
    if isinstance(value, (dict, list)):
        return "Json"
    
    return "String"


def _normalize_field_name(key: str) -> str:
    """Converte camelCase para snake_case."""
    result = []
    for i, char in enumerate(key):
        if char.isupper() and i > 0:
            result.append("_")
            result.append(char.lower())
        else:
            result.append(char.lower())
    return "".join(result)


def analyze() -> tuple[list[Column], bool, int]:
    """Analisa o JSON e retorna as colunas inferidas.
    
    Retorna:
        (lista de colunas, tem_id_natural, total_registros)
    """
    if not config.PRODUCTS_JSON.exists():
        raise RuntimeError(
            f"{config.PRODUCTS_JSON} nao encontrado. Rode a captura primeiro."
        )
    
    records = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    
    if not isinstance(records, list):
        raise RuntimeError("JSON capturado nao e uma lista de registros.")
    
    if not records:
        raise RuntimeError("JSON capturado esta vazio.")
    
    # Analisa todos os registros para descobrir campos e tipos
    field_types: dict[str, set[str]] = {}
    field_nullability: dict[str, bool] = {}
    has_id = False
    
    for record in records:
        if not isinstance(record, dict):
            continue
        
        for key, value in record.items():
            if key not in field_types:
                field_types[key] = set()
                field_nullability[key] = False  # Começa como False
            
            if value is None:
                # Se encontra um valor nulo, o campo é nullable
                field_nullability[key] = True
            else:
                field_types[key].add(_infer_type(value, key))
            
            if key == "id" and value is not None:
                has_id = True
    
    # Normaliza os tipos (se um campo tem multiplos tipos, usa Json)
    columns = []
    for key in sorted(field_types.keys()):
        types = field_types[key]
        field_name = _normalize_field_name(key)
        
        # Escolhe o tipo
        if len(types) > 1 or "Json" in types:
            ptype = "Json"
        elif types:
            ptype = list(types)[0]
        else:
            ptype = "String"
        
        is_id = key == "id"
        nullable = field_nullability.get(key, True)
        
        columns.append(Column(
            key=key,
            field=field_name,
            ptype=ptype,
            nullable=nullable,
            is_id=is_id,
        ))
    
    return columns, has_id, len(records)


def _generate_schema(columns: list[Column], total_records: int) -> str:
    """Gera o conteudo do schema.prisma."""
    lines = [
        "// Arquivo gerado automaticamente por src/schema_generator.py",
        "// Baseado em {:d} registro(s) de produtos".format(total_records),
        "",
        "generator client {",
        '  provider             = "prisma-client-py"',
        "  recursive_type_depth = 5",
        "}",
        "",
        "datasource db {",
        '  provider = "postgresql"',
        '  url      = env("DATABASE_URL")',
        "}",
        "",
        "model Product {",
    ]
    
    # Rastrear campos já adicionados para evitar duplicatas
    added_fields = set()
    
    for col in columns:
        # Pular se o campo já foi adicionado
        if col.field in added_fields:
            continue
        
        added_fields.add(col.field)
        
        # Monta a declaracao do campo
        decl = f"  {col.field} {col.ptype}"
        
        # Adiciona modificadores
        if col.is_id:
            decl += " @id"
        
        if not col.nullable and not col.is_id:
            pass  # ja nao e nullable por padrao
        else:
            if col.nullable and not col.is_id:
                decl += "?"
        
        lines.append(decl)
    
    lines.extend([
        "",
        '  @@map("products")',
        "}",
        "",
        # Tabela de categorias (mesmo modelo em ecomhub e primecod).
        CATEGORY_MODEL,
    ])

    return "\n".join(lines)


def run_generate() -> None:
    """Gera o schema Prisma e salva em prisma/schema.prisma."""
    print("[2/4] Gerando schema Prisma...")
    
    columns, has_id, total_records = analyze()
    schema_content = _generate_schema(columns, total_records)
    
    schema_path = config.PRISMA_DIR / "schema.prisma"
    schema_path.write_text(schema_content, encoding="utf-8")
    
    print(f"OK! Schema gerado com {len(columns)} campo(s)")
    print(f"  Salvo em: {schema_path}")


if __name__ == "__main__":
    run_generate()
