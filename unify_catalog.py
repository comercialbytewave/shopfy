"""Unifica os catalogos de produtos do EcomHub e do Primecod em UMA tabela.

Le os dois data/products.json capturados, monta um schema "uniao" com TODOS
os campos das duas origens (campos em comum compartilham coluna, campos
exclusivos viram colunas opcionais) e (re)cria a tabela `products` no banco
`unified_catalog`, marcando cada registro com a coluna `integration`
('ecomhub' ou 'primecod').

Nao depende de driver Python: gera SQL e aplica via `psql`.

Uso:
    python unify_catalog.py                 # reconstroi a tabela e importa tudo
    python unify_catalog.py --schema-only   # so imprime o SQL (DDL) e sai
    python unify_catalog.py --dry-run        # gera o .sql mas nao aplica

Variaveis de ambiente:
    UNIFIED_DATABASE_URL  conexao Postgres da tabela unificada.
        Default: postgresql://postgres:123456@localhost:5432/unified_catalog
        (NAO usa DATABASE_URL de proposito: cada projeto tem o seu DATABASE_URL
         apontando para o banco per-projeto; o unificado e independente.)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent

# (rotulo da integracao, caminho do products.json)
SOURCES: list[tuple[str, Path]] = [
    ("ecomhub", ROOT / "ecomhub" / "data" / "products.json"),
    ("primecod", ROOT / "primecod" / "data" / "products.json"),
]

TABLE = "products"
DEFAULT_DATABASE_URL = (
    "postgresql://postgres:123456@localhost:5432/unified_catalog?schema=public"
)

# Abre a transacao e silencia os NOTICE de "IF NOT EXISTS ... already exists,
# skipping" (sao esperados no modo nao-destrutivo e so poluem a saida).
_BEGIN = "BEGIN;\nSET LOCAL client_min_messages = warning;\n"


# --------------------------------------------------------------------------- #
# Inferencia de tipos
# --------------------------------------------------------------------------- #
def _kind(value: Any) -> str:
    """Classifica um valor Python num "tipo" interno."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "str"  # strings (inclusive datas ISO) tratadas como texto


def _resolve_pg_type(kinds: set[str]) -> str:
    """Decide o tipo Postgres final de uma coluna a partir dos tipos vistos."""
    if not kinds:
        return "text"
    if "json" in kinds:
        return "jsonb"
    if kinds == {"bool"}:
        return "boolean"
    if kinds == {"int"}:
        return "integer"
    if kinds <= {"int", "float"}:
        return "double precision"
    # qualquer mistura com str (ex.: id texto x id int) -> texto e lossless
    return "text"


def _sanitize(name: str) -> str:
    """Nome de coluna Postgres valido (minusculo, sem aspas)."""
    clean = re.sub(r"[^a-z0-9_]", "_", name.lower())
    if not clean or not re.match(r"[a-z_]", clean[0]):
        clean = f"f_{clean}"
    return clean


class Column:
    def __init__(self, key: str, field: str) -> None:
        self.key = key          # chave original no JSON
        self.field = field      # nome da coluna no Postgres
        self.kinds: set[str] = set()
        self.sources: set[str] = set()

    @property
    def pg_type(self) -> str:
        return _resolve_pg_type(self.kinds)


# --------------------------------------------------------------------------- #
# Carregamento e analise
# --------------------------------------------------------------------------- #
def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"[erro] {path} nao encontrado. Rode a captura primeiro.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"[erro] {path} nao e uma lista de registros.")
    return [r for r in data if isinstance(r, dict)]


def build_columns(
    datasets: list[tuple[str, list[dict[str, Any]]]],
) -> list[Column]:
    """Constroi a uniao de colunas das duas origens, na ordem de descoberta."""
    cols: dict[str, Column] = {}   # chave JSON -> Column
    used_fields: dict[str, str] = {}  # nome de coluna -> chave JSON (deteccao de colisao)
    order: list[str] = []

    for label, records in datasets:
        for rec in records:
            for key, value in rec.items():
                col = cols.get(key)
                if col is None:
                    field = _sanitize(key)
                    # resolve colisao de nomes entre chaves diferentes
                    if field in used_fields and used_fields[field] != key:
                        suffix = 2
                        while f"{field}_{suffix}" in used_fields:
                            suffix += 1
                        field = f"{field}_{suffix}"
                    used_fields[field] = key
                    col = Column(key, field)
                    cols[key] = col
                    order.append(key)
                col.sources.add(label)
                if value is not None:
                    col.kinds.add(_kind(value))

    return [cols[k] for k in order]


# --------------------------------------------------------------------------- #
# Geracao de SQL
# --------------------------------------------------------------------------- #
def _sql_literal(value: Any, pg_type: str) -> str:
    if value is None:
        return "NULL"

    if pg_type == "jsonb":
        text = json.dumps(value, ensure_ascii=False)
        return "'" + text.replace("'", "''") + "'::jsonb"

    if pg_type == "boolean":
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return "TRUE" if str(value).strip().lower() in ("1", "true", "t", "yes") else "FALSE"

    if pg_type == "integer":
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "NULL"

    if pg_type == "double precision":
        try:
            return repr(float(value))
        except (TypeError, ValueError):
            return "NULL"

    # text
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return "'" + text.replace("'", "''") + "'"


def build_rebuild_ddl(columns: list[Column]) -> str:
    """DDL destrutivo (DROP+CREATE). Usado apenas com --rebuild."""
    lines = [f'DROP TABLE IF EXISTS "{TABLE}";', f'CREATE TABLE "{TABLE}" (']
    defs = [
        '  "pk" serial PRIMARY KEY',
        '  "integration" text NOT NULL',
    ]
    for col in columns:
        not_null = ' NOT NULL' if col.field == "id" else ''
        defs.append(f'  "{col.field}" {col.pg_type}{not_null}')
    lines.append(",\n".join(defs))
    lines.append(");")
    lines.append(
        f'CREATE UNIQUE INDEX "{TABLE}_integration_id_key" '
        f'ON "{TABLE}" ("integration", "id");'
    )
    return "\n".join(lines)


def build_ensure_ddl(columns: list[Column]) -> str:
    """DDL nao-destrutivo: cria a tabela se faltar e garante TODAS as colunas.

    Nunca dropa nada. Colunas novas (de qualquer integracao) sao adicionadas
    com ADD COLUMN IF NOT EXISTS, entao a tabela vira sempre o superconjunto
    de todos os campos das duas origens.
    """
    lines = [
        f'CREATE TABLE IF NOT EXISTS "{TABLE}" (',
        '  "pk" serial PRIMARY KEY,',
        '  "integration" text NOT NULL,',
        '  "id" text NOT NULL',
        ");",
        f'CREATE UNIQUE INDEX IF NOT EXISTS "{TABLE}_integration_id_key" '
        f'ON "{TABLE}" ("integration", "id");',
    ]
    for col in columns:
        if col.field == "id":
            continue  # ja criada acima
        lines.append(
            f'ALTER TABLE "{TABLE}" ADD COLUMN IF NOT EXISTS '
            f'"{col.field}" {col.pg_type};'
        )
    return "\n".join(lines)


def build_inserts_all(
    columns: list[Column],
    datasets: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[str, int]:
    """INSERT de todos os registros de todas as origens (usado com --rebuild)."""
    col_names = ['"integration"'] + [f'"{c.field}"' for c in columns]
    header = f'INSERT INTO "{TABLE}" ({", ".join(col_names)}) VALUES'
    rows: list[str] = []
    for label, records in datasets:
        for rec in records:
            vals = ["'" + label + "'"]
            for col in columns:
                vals.append(_sql_literal(rec.get(col.key), col.pg_type))
            rows.append("(" + ", ".join(vals) + ")")
    return header + "\n" + ",\n".join(rows) + ";", len(rows)


def build_refresh(
    columns: list[Column],
    datasets: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[str, int, list[str], list[str]]:
    """Atualiza por integracao: apaga e reinsere SO as integracoes com registros.

    Integracoes sem registros (captura falha) sao PRESERVADAS intactas.
    Retorna (sql, total_inserido, atualizadas, preservadas).
    """
    col_names = ['"integration"'] + [f'"{c.field}"' for c in columns]
    blocks: list[str] = []
    total = 0
    refreshed: list[str] = []
    preserved: list[str] = []

    for label, records in datasets:
        if not records:
            preserved.append(label)
            continue
        refreshed.append(label)
        blocks.append(f"DELETE FROM \"{TABLE}\" WHERE \"integration\" = '{label}';")
        header = f'INSERT INTO "{TABLE}" ({", ".join(col_names)}) VALUES'
        rows: list[str] = []
        for rec in records:
            vals = ["'" + label + "'"]
            for col in columns:
                vals.append(_sql_literal(rec.get(col.key), col.pg_type))
            rows.append("(" + ", ".join(vals) + ")")
        blocks.append(header + "\n" + ",\n".join(rows) + ";")
        total += len(records)

    return "\n".join(blocks), total, refreshed, preserved


# --------------------------------------------------------------------------- #
# Execucao
# --------------------------------------------------------------------------- #
def _run_psql(database_url: str, sql_path: Path) -> None:
    parsed = urlparse(database_url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    dbname = parsed.path.lstrip("/") or "postgres"
    cmd = [
        "psql",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", unquote(parsed.username or "postgres"),
        "-d", dbname,
        "-v", "ON_ERROR_STOP=1",
        "-q",
        "-f", str(sql_path),
    ]
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    ap = argparse.ArgumentParser(description="Unifica catalogos ecomhub + primecod.")
    ap.add_argument("--schema-only", action="store_true", help="imprime so o DDL e sai")
    ap.add_argument("--dry-run", action="store_true", help="gera o SQL mas nao aplica")
    ap.add_argument(
        "--rebuild",
        action="store_true",
        help="DROP+CREATE a tabela do zero (destrutivo). Padrao: nao-destrutivo.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="com --rebuild, reconstroi mesmo com alguma origem vazia (PERIGOSO)",
    )
    args = ap.parse_args()

    database_url = os.getenv("UNIFIED_DATABASE_URL", DEFAULT_DATABASE_URL)
    datasets = [(label, _load(path)) for label, path in SOURCES]
    columns = build_columns(datasets)

    if args.schema_only:
        print(build_rebuild_ddl(columns) if args.rebuild else build_ensure_ddl(columns))
        return

    shared = [c.field for c in columns if len(c.sources) > 1]
    print(f"Colunas: {len(columns) + 2} (pk, integration, {len(columns)} de dados)")
    print(f"  compartilhadas entre as origens: {', '.join(shared)}")
    for label, records in datasets:
        print(f"  {label}: {len(records)} registro(s)")

    if args.rebuild:
        # Modo destrutivo: exige as duas origens com dados (salvo --force).
        empty = [label for label, records in datasets if not records]
        if empty and not args.force:
            raise SystemExit(
                f"[abortado] --rebuild com origem(ns) vazia(s): {', '.join(empty)}.\n"
                f"  A tabela existente foi PRESERVADA. Rode a captura de novo,\n"
                f"  ou use --force para reconstruir perdendo a origem vazia."
            )
        ddl = build_rebuild_ddl(columns)
        body, total = build_inserts_all(columns, datasets)
        sql = _BEGIN + ddl + "\n\n" + body + "\n\nCOMMIT;\n"
        action = f"reconstruida (DROP+CREATE) com {total} produto(s)"
    else:
        # Modo padrao NAO-destrutivo: garante schema e atualiza por integracao.
        ensure = build_ensure_ddl(columns)
        refresh, total, refreshed, preserved = build_refresh(columns, datasets)
        if not refreshed:
            raise SystemExit(
                "[abortado] nenhuma origem tem registros; nada a atualizar."
            )
        sql = _BEGIN + ensure + "\n\n" + refresh + "\n\nCOMMIT;\n"
        msg = f"atualizada (sem drop); {total} produto(s) em {', '.join(refreshed)}"
        if preserved:
            msg += f"; PRESERVADAS sem alterar: {', '.join(preserved)}"
        action = msg

    out = ROOT / "unified_catalog.sql"
    out.write_text(sql, encoding="utf-8")
    print(f"SQL gravado em {out}")

    if args.dry_run:
        print("--dry-run: nada foi aplicado no banco.")
        return

    print(f"Aplicando em {urlparse(database_url).path.lstrip('/')} ...")
    _run_psql(database_url, out)
    print(f"OK! Tabela '{TABLE}' {action}.")


if __name__ == "__main__":
    main()
