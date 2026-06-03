"""Carrega as configuracoes do projeto a partir do arquivo .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Raiz do projeto (pasta que contem este arquivo .env)
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEBUG_DIR = ROOT_DIR / "debug"
PRISMA_DIR = ROOT_DIR / "prisma"

# Carrega variaveis do .env
load_dotenv(ROOT_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variavel de ambiente '{name}' nao encontrada. "
            f"Preencha os valores em .env."
        )
    return value


# API Primecod
PRIMECOD_API_URL = _require("PRIMECOD_API_URL")
PRIMECOD_API_TOKEN = _require("PRIMECOD_API_TOKEN")
PRIMECOD_API_TOKEN_TYPE = os.getenv("PRIMECOD_API_TOKEN_TYPE", "Bearer")
PRIMECOD_COUNTRY_CODE = os.getenv("PRIMECOD_COUNTRY_CODE", "es")
PRIMECOD_PAGE_SIZE = int(os.getenv("PRIMECOD_PAGE_SIZE", "12"))

# Banco
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Caminhos de dados
PRODUCTS_JSON = DATA_DIR / "products.json"
PRODUCTS_RAW_JSON = DATA_DIR / "products_raw.json"
