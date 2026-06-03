"""Orquestrador do Primecod Importer.

Uso:
    python main.py capture   # acessa a API e captura o JSON de produtos
    python main.py schema    # gera prisma/schema.prisma a partir do JSON
    python main.py push      # cria as tabelas no Postgres (prisma db push) + gera o client
    python main.py import    # importa o JSON capturado para o banco
    python main.py all       # executa todas as etapas em sequencia (padrao)

Exemplo com variáveis de ambiente:
    DATABASE_URL=postgresql://user:pass@localhost:5432/primecod python main.py all
"""

from __future__ import annotations

import os
import subprocess
import sys

from src import config
from src.api_client import run_capture
from src.importer import run_import
from src.schema_generator import run_generate


def _env_with_venv_bin() -> dict[str, str]:
    """Garante que a pasta bin do venv esteja no PATH.

    O `prisma generate` chama o executavel `prisma-client-py`, que fica na
    mesma pasta do interpretador atual. Sem isto, o gerador nao e encontrado.
    """
    env = os.environ.copy()
    bin_dir = os.path.dirname(sys.executable)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def step_capture() -> None:
    print("\n=== ETAPA 1: CAPTURA DA API ===")
    run_capture()


def step_schema() -> None:
    print("\n=== ETAPA 2: GERAR SCHEMA PRISMA ===")
    run_generate()


def step_push() -> None:
    print("\n=== ETAPA 3: CRIAR TABELAS NO BANCO (prisma db push) ===")
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL nao definido no .env.")
    schema_path = str(config.PRISMA_DIR / "schema.prisma")
    env = _env_with_venv_bin()
    # `prisma db push` aplica o schema no Postgres e ja gera o client
    subprocess.run(
        [sys.executable, "-m", "prisma", "db", "push", "--schema", schema_path],
        check=True,
        env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "prisma", "generate", "--schema", schema_path],
        check=True,
        env=env,
    )


def step_import() -> None:
    print("\n=== ETAPA 4: IMPORTAR PARA O BANCO ===")
    run_import()


STEPS = {
    "capture": step_capture,
    "schema": step_schema,
    "push": step_push,
    "import": step_import,
}


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "all":
        step_capture()
        step_schema()
        step_push()
        step_import()
        print("\n>>> Pipeline completa com sucesso!")
    elif arg in STEPS:
        STEPS[arg]()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
